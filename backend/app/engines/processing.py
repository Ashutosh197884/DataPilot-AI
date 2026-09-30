"""Data processing engine — deterministic cleaning/transformation (Pandas).

Every transformation returns a human-readable summary used by the evidence
trail. The LLM never touches data; it only chooses which tools run here.
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

_CURRENCY_RE = re.compile(r"(?:[₹$€])?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakh|crore|cr|k|m|million|bn)?", re.I)
_MULTIPLIERS = {"lakh": 1e5, "crore": 1e7, "cr": 1e7, "k": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9}


def _coerce_numeric(col: pd.Series) -> tuple[pd.Series, int]:
    """Coerce a column to numeric; parse '₹5 lakh'-style strings; count conversions."""
    converted = 0

    def parse(v: Any) -> Any:
        nonlocal converted
        if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v)):
            return v
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return np.nan
        s = str(v).strip()
        if s == "" or s.lower() in {"na", "n/a", "-", "null", "none"}:
            return np.nan
        m = _CURRENCY_RE.fullmatch(s.replace(",", ""))
        if m:
            converted += 1
            val = float(m.group(1))
            mult = _MULTIPLIERS.get((m.group(2) or "").lower())
            return val * mult if mult else val
        try:
            converted += 1
            return float(s.replace(",", ""))
        except ValueError:
            return np.nan

    out = col.map(parse)
    return pd.to_numeric(out, errors="coerce"), converted


def _coerce_year(col: pd.Series) -> tuple[pd.Series, int]:
    """Normalize year-ish values (2024, '2024', 'FY2025', '2024-01-01', '01/01/2024')."""
    normalized = 0

    def parse(v: Any) -> Any:
        nonlocal normalized
        if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v)):
            y = int(v)
            if 1900 <= y <= 2100:
                return y
            return np.nan
        s = str(v).strip()
        m = re.search(r"(19|20)\d{2}", s)
        if m:
            if not re.fullmatch(r"(19|20)\d{2}", s):
                normalized += 1
            return int(m.group(0))
        return np.nan

    out = col.map(parse)
    return pd.to_numeric(out, errors="coerce").astype("Int64"), normalized


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Standard cleaning pass; returns (cleaned_df, transformation summaries)."""
    transformations: list[dict[str, Any]] = []
    original_rows = len(df)

    # 1. Exact duplicate removal
    dupes = int(df.duplicated().sum())
    if dupes:
        df = df.drop_duplicates().reset_index(drop=True)
    transformations.append(
        {"name": "duplicate_removal", "detail": f"Removed {dupes} duplicate rows", "rows_affected": dupes}
    )

    # 2. Column name normalization
    renamed = {c: re.sub(r"\s+", "_", str(c).strip().lower()) for c in df.columns}
    if any(k != v for k, v in renamed.items()):
        df = df.rename(columns=renamed)
    transformations.append({"name": "column_normalization", "detail": "Normalized column names"})

    # 3. Year/date columns -> normalized years
    for c in df.columns:
        if re.search(r"\b(year|yr|fy)\b", c, re.I):
            df[c], n = _coerce_year(df[c])
            if n:
                transformations.append(
                    {"name": "date_normalization", "detail": f"Normalized {n} year values in '{c}'", "column": c}
                )

    # 4. Numeric-looking columns -> numeric (incl. '₹5 lakh' parsing).
    # Covers both legacy object dtype and pandas 3.x default string dtype.
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c]):
            sample = df[c].dropna().astype(str).head(50)
            if len(sample) and pd.to_numeric(sample, errors="coerce").notna().mean() >= 0.5:
                before_nonnull = int(df[c].notna().sum())
                df[c], converted = _coerce_numeric(df[c].astype(object))
                if converted:
                    transformations.append(
                        {
                            "name": "type_conversion",
                            "detail": f"Converted '{c}' to numeric ({converted} values parsed, {before_nonnull} non-null)",
                            "column": c,
                        }
                    )
                # Unit-mismatch quarantine: a value >10,000x the column median is
                # a unit error (e.g. '₹480 lakh' in an mm-rainfall column).
                # It is recorded here and excluded from all downstream math.
                s = df[c].dropna()
                if len(s) >= 5:
                    med = float(s.median())
                    if med > 0:
                        outliers = df[c] > (med * 10_000)
                        n_out = int(outliers.sum())
                        if n_out:
                            df[c] = df[c].where(~outliers, np.nan)
                            transformations.append(
                                {
                                    "name": "unit_normalization",
                                    "detail": f"Quarantined {n_out} unit-mismatch value(s) in '{c}' (>10,000x median)",
                                    "column": c,
                                }
                            )
    return df, transformations


_CANON_CACHE: dict[str, str] = {}


def canonicalize_entities(values: pd.Series, *, domain_hint: str | None = None) -> tuple[pd.Series, dict[str, str]]:
    """Map spelling/case variants ('TESLA', 'Tesla Inc.', 'tesla') to one canonical form.

    Groups by lowercase alnum token-prefix; the longest variant (richest form)
    becomes canonical, title-cased.
    """
    mapping: dict[str, str] = {}
    groups: dict[str, set[str]] = {}
    for raw in values.dropna().astype(str):
        s = raw.strip()
        if not s:
            continue
        key = re.sub(r"[^a-z0-9]", "", s.lower())
        # trim corporate suffixes for grouping key
        key = re.sub(r"(inc|corp|corporation|ltd|limited|llc|motors|pvt|private)$", "", key)
        groups.setdefault(key, set()).add(s)
    for key, variants in groups.items():
        if len(variants) > 1:
            canonical = max(variants, key=len)
            canonical = re.sub(r"\s+(Inc\.?|Corp\.?|Corporation|Ltd\.?|Limited|LLC|Pvt\.?|Private)$", "", canonical, flags=re.I)
            canonical = canonical.title()
            for v in variants:
                if v != canonical:
                    mapping[v] = canonical
    if mapping:
        out = values.astype(object).where(~values.isin(mapping.keys()), values.map(mapping))
        return out, mapping
    return values, mapping


def normalize_entities(df: pd.DataFrame, column: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Entity normalization step with evidence summary."""
    if column not in df.columns:
        return df, {"applied": False, "detail": f"Column '{column}' not found"}
    df = df.copy()
    df[column], mapping = canonicalize_entities(df[column])
    n = len(mapping)
    detail = (
        f"Normalized {n} entity variants in '{column}' (e.g. " + ", ".join(f"'{k}' → '{v}'" for k, v in list(mapping.items())[:3]) + ")"
        if n
        else f"No variants found in '{column}'"
    )
    return df, {"applied": bool(n), "detail": detail, "mapping": mapping}


def join_datasets(
    left: pd.DataFrame, right: pd.DataFrame, on: list[str], how: str = "inner"
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Join two datasets with join-coverage evidence."""
    left_keys = [c for c in on if c in left.columns]
    right_keys = [c for c in on if c in right.columns]
    if set(left_keys) != set(on) or set(right_keys) != set(on):
        raise ValueError(f"Join keys {on} missing. left has {list(left.columns)}, right has {list(right.columns)}")

    lkeys = left[on].astype(str).agg("§".join, axis=1)
    rkeys = right[on].astype(str).agg("§".join, axis=1)
    coverage = float(len(set(lkeys) & set(rkeys)) / max(1, len(set(lkeys))))

    merged = left.merge(right, on=on, how=how)
    summary = {
        "join_keys": on,
        "how": how,
        "left_rows": int(len(left)),
        "right_rows": int(len(right)),
        "joined_rows": int(len(merged)),
        "left_key_coverage": round(coverage, 4),
    }
    return merged, summary


def aggregate(
    df: pd.DataFrame,
    group_cols: list[str],
    value_col: str,
    agg: str = "sum",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Deterministic aggregation used by trend/comparison analyses."""
    valid_aggs = {"sum", "mean", "median", "min", "max", "count"}
    if agg not in valid_aggs:
        raise ValueError(f"agg must be one of {valid_aggs}")
    out = df.groupby(group_cols, dropna=False)[value_col].agg(agg).reset_index()
    summary = {
        "group_by": group_cols,
        "value": value_col,
        "agg": agg,
        "groups": int(len(out)),
    }
    return out, summary
