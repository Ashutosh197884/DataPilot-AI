"""Analysis engine — deterministic numeric truth (NumPy/Pandas).

The LLM decides WHAT to analyze; this engine computes the numbers, each with
an exact calculation string so insights can show their work (evidence).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def kpis(df: pd.DataFrame, value_col: str, label: str = "Total") -> dict[str, Any]:
    total = float(df[value_col].sum())
    return {
        "label": label,
        "value": total,
        "calculation": f"SUM({value_col}) over {len(df)} rows = {total:,.2f}",
        "calculation_expr": f"Σ {value_col}",
    }


def growth_rate(
    df: pd.DataFrame, period_col: str, value_col: str, start: int | None = None, end: int | None = None
) -> dict[str, Any]:
    """Overall growth between first and last (or explicit) periods."""
    d = df[[period_col, value_col]].dropna().groupby(period_col)[value_col].sum().sort_index()
    if start is not None and end is not None:
        s, e = d.get(start), d.get(end)
        label = f"{start} → {end}"
    else:
        s, e = d.iloc[0], d.iloc[-1]
        label = f"{d.index[0]} → {d.index[-1]}"
    if not s:
        raise ValueError(f"Base-period value is zero/missing for growth ({label})")
    g = (e - s) / s * 100.0
    return {
        "period_from": (start if start is not None else int(d.index[0])),
        "period_to": (end if end is not None else int(d.index[-1])),
        "from_value": float(s),
        "to_value": float(e),
        "growth_pct": round(float(g), 1),
        "calculation": f"({e:,.0f} − {s:,.0f}) / {s:,.0f} × 100 = {g:.1f}%  [{label}]",
    }


def yoy_trend(df: pd.DataFrame, period_col: str, value_col: str) -> dict[str, Any]:
    """Year-over-year series with per-period growth."""
    d = df.groupby(period_col)[value_col].sum().sort_index()
    yoy = d.pct_change() * 100.0
    return {
        "periods": [int(p) for p in d.index],
        "values": [round(float(v), 2) for v in d.values],
        "yoy_pct": [None if pd.isna(y) else round(float(y), 1) for y in yoy.values],
        "calculation": f"SUM({value_col}) grouped by {period_col}; YoY = (Vt − Vt−1)/Vt−1 × 100",
    }


def group_growth_comparison(
    df: pd.DataFrame, group_col: str, period_col: str, value_col: str, top: int = 10
) -> dict[str, Any]:
    """Per-group growth between first and last period, ranked (fastest growing first)."""
    piv = df.pivot_table(index=group_col, columns=period_col, values=value_col, aggfunc="sum").dropna(
        how="any"
    )
    if piv.shape[1] < 2:
        raise ValueError("Need at least two periods for growth comparison")
    first, last = piv.iloc[:, 0], piv.iloc[:, -1]
    g = ((last - first) / first.replace(0, np.nan) * 100.0).dropna()
    g = g.sort_values(ascending=False).head(top)
    return {
        "group_column": group_col,
        "period_from": int(piv.columns[0]),
        "period_to": int(piv.columns[-1]),
        "growth_pct_by_group": {str(k): round(float(v), 1) for k, v in g.items()},
        "calculation": (
            f"(Σ {period_col}={int(piv.columns[-1])} − Σ {period_col}={int(piv.columns[0])}) / Σ {period_col}={int(piv.columns[0])} × 100, per {group_col}"
        ),
    }


def correlation(df: pd.DataFrame, col_a: str, col_b: str) -> dict[str, Any]:
    """Pearson correlation with explicit association (not causation) framing."""
    d = df[[col_a, col_b]].dropna()
    if len(d) < 3:
        raise ValueError("Need at least 3 paired observations")
    r = float(d[col_a].corr(d[col_b]))
    strength = (
        "strong positive" if r >= 0.7 else "moderate positive" if r >= 0.4 else "weak" if r >= 0.1 else "negligible" if r > -0.1 else "negative"
    )
    return {
        "columns": [col_a, col_b],
        "pearson_r": round(r, 3),
        "n": int(len(d)),
        "strength": strength,
        "interpretation": f"Columns show a {strength} association (r={r:.3f}, n={len(d)}). Association, not causation.",
        "calculation": f"Pearson r({col_a}, {col_b}) over {len(d)} paired rows = {r:.3f}",
    }


def detect_anomalies(df: pd.DataFrame, period_col: str, value_col: str, z_threshold: float = 2.5) -> dict[str, Any]:
    """Robust z-score anomaly detection on aggregated periods (IQR fallback flagging)."""
    d = df.groupby(period_col)[value_col].sum().sort_index()
    vals = d.values.astype(float)
    median = float(np.median(vals))
    mad = float(np.median(np.abs(vals - median))) or 1e-9
    rz = 0.6745 * (vals - median) / mad
    anomalies = [
        {"period": int(p), "value": round(float(v), 2), "robust_z": round(float(z), 2)}
        for p, v, z in zip(d.index, vals, rz)
        if abs(z) >= z_threshold
    ]
    return {
        "method": "robust z-score (median/MAD)",
        "threshold": z_threshold,
        "anomalies": anomalies,
        "n_periods": int(len(d)),
        "calculation": f"robust_z = 0.6745·(x − median)/MAD; flag |z| ≥ {z_threshold}",
    }


def distribution_summary(df: pd.DataFrame, col: str) -> dict[str, Any]:
    s = df[col].dropna()
    return {
        "min": round(float(s.min()), 2),
        "max": round(float(s.max()), 2),
        "mean": round(float(s.mean()), 2),
        "median": round(float(s.median()), 2),
        "std": round(float(s.std()), 2),
        "calculation": f"descriptive stats of {col} over {len(s)} rows",
    }
