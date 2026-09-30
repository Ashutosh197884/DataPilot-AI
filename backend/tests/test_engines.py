"""Engine tests: the deterministic truth layer must be provably correct."""
from __future__ import annotations

import pandas as pd
import pytest

from app.engines import analysis as an
from app.engines import processing as pr
from app.engines import validation as va


# ---------------- processing ----------------

def test_duplicate_removal():
    df = pd.DataFrame(
        {"a": ["Karnal", "Karnal", "Hisar"], "year": [2023, 2023, 2023], "v": [1.0, 1.0, 2.0]}
    )
    out, transformations = pr.clean_dataframe(df)
    assert len(out) == 2
    dup = next(t for t in transformations if t["name"] == "duplicate_removal")
    assert dup["rows_affected"] == 1


def test_currency_parsing():
    s = pd.Series(["₹5 lakh", "2 crore", "₹6.8k", "123"])
    out, _ = pr._coerce_numeric(s)
    assert out.iloc[0] == 500000.0
    assert out.iloc[1] == 20000000.0
    assert out.iloc[2] == 6800.0
    assert out.iloc[3] == 123.0


def test_year_normalization():
    s = pd.Series([2024, "2023-01-01", "FY2025", "01/01/2022", 1900])
    out, changed = pr._coerce_year(s)
    assert list(out.dropna().astype(int)) == [2024, 2023, 2025, 2022, 1900]  # 1900 is in valid range
    assert changed >= 3  # the non-plain formats were normalized


def test_entity_normalization_tesla_style():
    s = pd.Series(["Tesla", "TESLA", "Tesla Inc.", "tesla", "BYD"])
    out, mapping = pr.canonicalize_entities(s)
    assert set(out[:4]) == {out.iloc[0]}
    assert out.iloc[4] == "BYD"
    assert len(mapping) == 3


def test_join_coverage():
    left = pd.DataFrame({"district": ["A", "B", "C"], "year": [2020, 2020, 2020], "l": [1, 2, 3]})
    right = pd.DataFrame({"district": ["A", "B", "D"], "year": [2020, 2020, 2020], "r": [4, 5, 6]})
    merged, summary = pr.join_datasets(left, right, on=["district", "year"])
    assert len(merged) == 2
    # join coverage is rounded to 4dp by the engine
    assert summary["left_key_coverage"] == pytest.approx(2 / 3, abs=1e-3)


# ---------------- validation ----------------

def _dirty_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "district": ["Karnal", "Karnal", "HISAR", "hisar ", "Sirsa", "Jind", "Kaithal"],
            "year": [2023, 2023, 2023, 2024, 2021, 2024, 2022],
            "rainfall_mm": [800.0, 800.0, 610.2, 520.5, -45.0, 590.3, "₹480 lakh"],
            "wheat_production_t": [112340, 112340, 91500, 80200, 66500, None, 88000],
        }
    )


def test_validation_catches_planted_issues():
    report = va.validate(_dirty_frame(), non_negative=["rainfall_mm", "wheat_production_t"])
    assert report["duplicate_count"] >= 1
    assert report["invalid_count"] >= 2  # negative rainfall + '₹480 lakh' string
    assert report["completeness"] < 100.0  # the None production value
    assert 0 < report["quality_score"] < 100


def test_clean_data_passes():
    df = pd.DataFrame(
        {
            "district": ["A", "B", "C"],
            "year": [2020, 2021, 2022],
            "v": [1.0, 2.0, 3.0],
        }
    )
    report = va.validate(df, non_negative=["v"])
    assert report["quality_score"] == 100.0
    assert report["schema_valid"] is True


def test_schema_check_flags_missing_column():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    report = va.validate(df, expected_schema={"a": "numeric", "z": "numeric"})
    assert report["schema_valid"] is False


# ---------------- analysis ----------------

def test_growth_rate():
    df = pd.DataFrame({"year": [2023, 2024, 2025], "sales": [100, 120, 134.8]})
    g = an.growth_rate(df, "year", "sales")
    assert g["growth_pct"] == pytest.approx(34.8, abs=0.1)
    assert "34.8" in g["calculation"]


def test_correlation_known_sign():
    # strong positive relationship by construction
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [10, 21, 32, 40, 51]})
    c = an.correlation(df, "x", "y")
    assert c["pearson_r"] > 0.95
    assert "association" in c["interpretation"]
    # phrased as association, never as causation (spec §54)


def test_anomaly_detection_flags_spike():
    df = pd.DataFrame(
        {"year": list(range(2018, 2026)), "sales": [100, 105, 102, 108, 100, 104, 500, 103]}
    )
    result = an.detect_anomalies(df, "year", "sales")
    periods = [a["period"] for a in result["anomalies"]]
    assert 2024 in periods


def test_group_growth_ranking():
    df = pd.DataFrame(
        {
            "maker": ["A", "A", "B", "B"],
            "year": [2022, 2025, 2022, 2025],
            "sales": [100, 200, 100, 150],
        }
    )
    g = an.group_growth_comparison(df, "maker", "year", "sales")
    assert list(g["growth_pct_by_group"].items())[0][0] == "A"  # A grew 100% > B 50%
