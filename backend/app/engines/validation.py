"""Validation engine — never trust data silently; report its quality state.

Checks per spec §21/51: completeness, duplicates, invalid values (negative
counts, non-numeric junk in numeric columns), type checks, schema checks,
unit consistency flags. Produces a transparent quality score.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def validate(
    df: pd.DataFrame,
    *,
    expected_schema: dict[str, str] | None = None,
    non_negative: list[str] | None = None,
    dataset_name: str = "dataset",
) -> dict[str, Any]:
    """Run all checks; returns a validation report dict (persisted as ValidationRun)."""
    total_rows = int(len(df))
    checks: list[dict[str, Any]] = []

    # --- Completeness ---
    if total_rows:
        missing_cells = int(df.isna().sum().sum())
        total_cells = int(df.size)
        completeness = round(100.0 * (1 - missing_cells / max(1, total_cells)), 2)
    else:
        missing_cells, completeness = 0, 0.0
    checks.append(
        {
            "name": "completeness",
            "status": "PASS" if completeness >= 95 else ("WARN" if completeness >= 85 else "FAIL"),
            "value": completeness,
            "detail": f"{missing_cells} missing cells of {total_rows} rows x {len(df.columns)} columns",
        }
    )

    # --- Duplicates ---
    dup_count = int(df.duplicated().sum())
    dup_pct = round(100.0 * dup_count / max(1, total_rows), 2)
    checks.append(
        {
            "name": "duplicates",
            "status": "PASS" if dup_pct < 0.5 else ("WARN" if dup_pct < 2 else "FAIL"),
        "detail": f"{dup_count} duplicate rows ({dup_pct}%)",
        }
    )

    # --- Invalid values in non-negative numeric columns ---
    invalid_total = 0
    invalid_examples: list[str] = []
    for col in non_negative or []:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        bad = (s < 0).sum()
        # count only values that failed numeric coercion but were non-null originally
        unparseable = int((s.isna() & df[col].notna()).sum())
        n_bad = int(bad)
        invalid_total += n_bad + unparseable
        if n_bad:
            example_val = s[s < 0].iloc[0] if n_bad else None
            invalid_examples.append(f"{col} has {n_bad} negative values (e.g. {example_val})")
        if unparseable:
            ex = df[col][s.isna() & df[col].notna()].iloc[0] if unparseable else None
            invalid_examples.append(f"{col} has {unparseable} non-numeric values (e.g. '{ex}')")
        checks.append(
            {
                "name": f"invalid_values:{col}",
                "status": "PASS" if (n_bad + unparseable) == 0 else "WARN",
                "value": n_bad + unparseable,
                "detail": f"{n_bad} negative, {unparseable} unparseable",
            }
        )

    # --- Unit consistency (order-of-magnitude outliers) ---
    for col in non_negative or []:
        if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
            continue
        s = df[col].dropna()
        if len(s) >= 10 and s.mean() > 0:
            ratio = s.max() / s.mean()
            if ratio > 1000:
                checks.append(
                    {
                        "name": f"unit_consistency:{col}",
                        "status": "WARN",
                        "detail": f"'{col}' max is {ratio:.0f}x the mean — check mixed units",
                    }
                )

    # --- Schema check ---
    schema_valid = True
    if expected_schema:
        missing_cols = [c for c in expected_schema if c not in df.columns]
        extra_cols = [c for c in df.columns if c not in expected_schema]
        type_mismatches = []
        for col, want in expected_schema.items():
            if col in df.columns:
                got = "numeric" if pd.api.types.is_numeric_dtype(df[col]) else "string"
                if want == "numeric" and got != "numeric":
                    type_mismatches.append(f"{col}: expected {want}, got {got}")
        schema_valid = not missing_cols and not type_mismatches
        checks.append(
            {
                "name": "schema",
                "status": "PASS" if schema_valid else "WARN",
                "detail": {
                    "missing_columns": missing_cols,
                    "unexpected_columns": extra_cols,
                    "type_mismatches": type_mismatches,
                },
            }
        )

    # --- Quality score: transparent, metric-based ---
    completeness_score = completeness
    dup_penalty = min(5.0, dup_pct)
    invalid_penalty = min(5.0, 100.0 * invalid_total / max(1, total_rows))
    schema_penalty = 0.0 if schema_valid else 2.0
    quality = round(max(0.0, completeness_score - dup_penalty - invalid_penalty - schema_penalty), 1)

    return {
        "dataset_name": dataset_name,
        "rows_checked": total_rows,
        "columns": list(df.columns),
        "completeness": completeness,
        "duplicate_count": dup_count,
        "invalid_count": invalid_total,
        "schema_valid": schema_valid,
        "quality_score": quality,
        "checks": checks,
        "invalid_examples": invalid_examples[:5],
    }


def summarize_for_step(report: dict[str, Any]) -> str:
    """One-line summary for the workflow step output."""
    return (
        f"Quality {report['quality_score']}% — {report['rows_checked']} rows, "
        f"completeness {report['completeness']}%, "
        f"{report['duplicate_count']} duplicates, {report['invalid_count']} invalid values, "
        f"schema {'PASS' if report['schema_valid'] else 'WARN'}"
    )
