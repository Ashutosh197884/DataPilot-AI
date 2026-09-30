"""Controlled tool layer (spec §13) — the ONLY capabilities the orchestrator
can invoke. Each tool executes a deterministic engine function, records an
evidence-friendly output, and mutates the workflow context. No shell, no
arbitrary code, no direct DB access from any LLM.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..engines import analysis as an
from ..engines import processing as pr
from ..engines import validation as va
from ..engines import visualization as vz
from ..models import Dataset


class ToolContext:
    """Per-workflow execution state shared across tool calls."""

    def __init__(self, db, workflow_id: str, intent: dict[str, Any], datasets: list[Dataset]):
        self.db = db
        self.workflow_id = workflow_id
        self.intent = intent
        self.datasets = datasets  # matched Dataset ORM rows
        self.frames: dict[str, pd.DataFrame] = {}
        self.transformations: list[dict[str, Any]] = []
        self.validation: dict[str, Any] | None = None
        self.joined: pd.DataFrame | None = None
        self.join_summary: dict[str, Any] | None = None
        self.analysis: dict[str, Any] = {}
        self.charts: list[dict[str, Any]] = []
        self.table: dict[str, Any] | None = None
        self.collect_summaries: list[str] = []

    # ---------------- tools ----------------

    def load_dataset(self, dataset: Dataset) -> dict[str, Any]:
        """read_cloudinary_asset()/get_dataset(): load bytes into a DataFrame."""
        from ..services.cloudinary import configured as cl_configured, fetch_asset_bytes

        path = dataset.local_path
        if not path and dataset.cloudinary_public_id and cl_configured():
            raw = fetch_asset_bytes(dataset.cloudinary_public_id)
            import io

            from ..services.cloudinary import store_local_copy

            tmp = store_local_copy_from_bytes(raw, dataset.name, dataset.file_type)
            path = str(tmp)
        if not path:
            raise ValueError(f"No readable storage for dataset '{dataset.name}'")

        if dataset.file_type in {"xlsx", "xls"}:
            df = pd.read_excel(path)
        else:
            df = pd.read_csv(path)
        self.frames[dataset.id] = df
        self.collect_summaries.append(f"{dataset.name}: {len(df):,} rows × {len(df.columns)} cols")
        return {"rows": int(len(df)), "columns": list(df.columns)}

    def clean(self) -> dict[str, Any]:
        """clean_dataset(): standard cleaning on every loaded frame."""
        details = []
        for ds_id, df in list(self.frames.items()):
            cleaned, transformations = pr.clean_dataframe(df)
            self.frames[ds_id] = cleaned
            details.append({ds_id: [t["detail"] for t in transformations]})
            self.transformations.extend(transformations)
        return {"cleaned_datasets": len(details), "details": details}

    def normalize_join_keys(self) -> dict[str, Any]:
        """normalize-locations/years before a join (spec Query B)."""
        details = []
        dims = [d for d in self.intent.get("dimensions", []) if d != "year"]
        dim_col_guesses = {
            "district": ["district", "district_name", "region"],
            "manufacturer": ["manufacturer", "maker", "brand"],
            "state": ["state", "state_name"],
            "region": ["region", "zone"],
        }
        for ds_id, df in self.frames.items():
            for dim in dims:
                for col in dim_col_guesses.get(dim, []):
                    if col in df.columns:
                        df, summary = pr.normalize_entities(df, col)
                        if summary.get("applied"):
                            self.transformations.append(
                                {"name": "entity_normalization", "detail": summary["detail"], "column": col}
                            )
                            details.append(summary["detail"])
                year_cols = [c for c in df.columns if "year" in c]
                for c in year_cols:
                    df[c], n = pr._coerce_year(df[c])
                    if n:
                        details.append(f"Normalized {n} year values in '{c}'")
        return {"details": details or ["Keys already normalized"]}

    def join(self, on: list[str]) -> dict[str, Any]:
        """join_datasets(): inner join of the two loaded frames."""
        ids = list(self.frames.keys())
        if len(ids) < 2:
            raise ValueError("Join needs two datasets")
        left, right = self.frames[ids[0]], self.frames[ids[1]]
        merged, summary = pr.join_datasets(left, right, on=on)
        self.joined = merged
        self.join_summary = summary
        self.transformations.append(
            {"name": "join", "detail": f"Joined on {on} — {summary['joined_rows']} rows, coverage {summary['left_key_coverage']:.1%}"}
        )
        return summary

    def filter_period(self, start: int, end: int) -> dict[str, Any]:
        removed = 0
        for ds_id, df in list(self.frames.items()):
            ycol = next((c for c in df.columns if "year" in c), None)
            if ycol:
                years = pd.to_numeric(df[ycol], errors="coerce")
                mask = (years >= start) & (years <= end)
                removed += int((~mask).sum())
                self.frames[ds_id] = df[mask]
        if self.joined is not None:
            ycol = next((c for c in self.joined.columns if "year" in c), None)
            if ycol:
                years = pd.to_numeric(self.joined[ycol], errors="coerce")
                self.joined = self.joined[(years >= start) & (years <= end)]
        self.transformations.append(
            {"name": "period_filter", "detail": f"Kept {start}–{end} ({removed} rows outside range removed)"}
        )
        return {"start": start, "end": end, "rows_removed": removed}

    def validate(self) -> dict[str, Any]:
        """validate_dataset(): quality report on the primary working frame."""
        df = self.joined if self.joined is not None else next(iter(self.frames.values()))
        metric_cols = [c for c in df.columns if c not in ("district", "state", "region", "manufacturer", "brand", "maker", "year")]
        numeric_metric_cols = [c for c in metric_cols if pd.api.types.is_numeric_dtype(df[c])]
        report = va.validate(df, non_negative=numeric_metric_cols, dataset_name="working set")
        self.validation = report
        return {
            "summary": va.summarize_for_step(report),
            "quality_score": report["quality_score"],
            "completeness": report["completeness"],
            "duplicates": report["duplicate_count"],
            "invalid": report["invalid_count"],
            "schema_valid": report["schema_valid"],
        }

    def aggregate(self) -> dict[str, Any]:
        """Aggregate step (also prepares frames for analysis)."""
        # Aggregation happens inside the analysis functions; this step records
        # that data is now grouped per intent dimensions.
        dims = self.intent.get("dimensions", [])
        return {"grouped_by": dims or ["(none)"]}

    def run_analysis(self) -> dict[str, Any]:
        """run_analysis(): deterministic computations driven by intent."""
        a = self.analysis
        start = self.intent.get("start_year")
        end = self.intent.get("end_year")
        topic = self.intent.get("topic")

        if topic in ("rainfall_vs_crop", "rainfall", "crop_production"):
            df = self.joined if self.joined is not None else next(iter(self.frames.values()))
            rain_col = self._find_col(["rainfall", "rain", "precip"])
            prod_col = self._find_col(["production", "output", "yield"])
            if rain_col and prod_col:
                # Exclude values validation flagged as invalid (negatives) from
                # all math — validation reports them, analysis does not use them.
                before = len(df)
                df = df[(df[rain_col] > 0) & (df[prod_col] > 0)]
                if before - len(df):
                    self.transformations.append(
                        {"name": "invalid_exclusion", "detail": f"Excluded {before - len(df)} invalid value(s) from analysis"}
                    )
                dist = a.get("_dim_col") or self._find_col(["district", "state", "region"])
                self._analysis_df = df  # filtered frame for chart building
                # correlation across district-years
                a["correlation"] = an.correlation(df, rain_col, prod_col)
                # yearly aggregates
                ycol = self._find_col(["year"])
                yearly = df.groupby(ycol).agg(rain=(rain_col, "mean"), prod=(prod_col, "sum")).reset_index()
                a["avg_rainfall"] = an.distribution_summary(df, rain_col)
                a["total_production"] = {"value": float(df[prod_col].sum())}
                a["trend"] = {
                    "periods": [int(p) for p in yearly[ycol]],
                    "values": [round(float(v), 1) for v in yearly["prod"]],
                    "yoy_pct": [None] + [round(float(x), 1) for x in (yearly["prod"].pct_change() * 100).dropna()],
                    "calculation": f"SUM({prod_col}) by year; mean {rain_col} by year",
                }
                a["_rain_col"], a["_prod_col"], a["_year_col"] = rain_col, prod_col, ycol
                a["_yearly"] = yearly.to_dict(orient="records")
                if dist and dist != ycol:
                    a["_dim_col"] = dist
        elif topic in ("ev_sales", "sales"):
            df = next(iter(self.frames.values()))
            val_col = self._find_col(["sales", "units", "registrations", "revenue", "quantity"])
            grp_col = self._find_col(["manufacturer", "maker", "brand", "product", "category"])
            ycol = self._find_col(["year", "date", "period"])
            if not val_col or not ycol:
                # Insufficient-data branch (spec §53): report honestly what is
                # available vs what a deeper answer would require.
                a["available_variables"] = {
                    "available": [c for c in df.columns],
                    "missing": ["marketing_spend", "price", "inventory", "customer_count"] if "why" in " ".join(self.intent.get("raw_query", "").lower().split()) else [],
                }
            else:
                before = len(df)
                df = df[df[val_col] > 0]
                if before - len(df):
                    self.transformations.append(
                        {"name": "invalid_exclusion", "detail": f"Excluded {before - len(df)} invalid value(s) from analysis"}
                    )
                a["total_sales"] = an.kpis(df, val_col, label="Sales (units)")
                if start and end:
                    try:
                        a["growth"] = an.growth_rate(df, ycol, val_col, start=start, end=end)
                    except (ValueError, KeyError):
                        a["growth"] = an.growth_rate(df, ycol, val_col)
                else:
                    a["growth"] = an.growth_rate(df, ycol, val_col)
                a["trend"] = an.yoy_trend(df, ycol, val_col)
                a["_val_col"], a["_year_col"] = val_col, ycol
                if "anomaly" in self.intent.get("analysis", []):
                    a["anomalies"] = an.detect_anomalies(df, ycol, val_col)
                if grp_col and "growth_comparison" in self.intent.get("analysis", []):
                    try:
                        a["group_growth"] = an.group_growth_comparison(df, grp_col, ycol, val_col)
                        a["_grp_col"] = grp_col
                    except ValueError:
                        pass
        return {"performed": [k for k in a if not k.startswith("_")]}

    def generate_charts(self) -> dict[str, Any]:
        """generate_chart(): build chart CONFIGS from analysis outputs."""
        a = self.analysis
        topic = self.intent.get("topic")
        if topic in ("rainfall_vs_crop", "rainfall", "crop_production") and "_yearly" in a:
            yearly = a["_yearly"]
            self.charts.append(
                vz.line_chart(
                    "Wheat Production by Year", "year", "prod",
                    [{"year": int(r["year"]), "prod": round(r["prod"], 1)} for r in yearly],
                )
            )
            self.charts.append(
                vz.line_chart(
                    "Average Rainfall by Year", "year", "rain",
                    [{"year": int(r["year"]), "rain": round(r["rain"], 1)} for r in yearly],
                )
            )
            if a.get("_rain_col"):
                work = getattr(self, "_analysis_df", None)
                if work is None:
                    work = self.joined if self.joined is not None else next(iter(self.frames.values()))
                pts = work[[a["_rain_col"], a["_prod_col"], a.get("_dim_col") or a["_year_col"]]].dropna()
                pt_label = a.get("_dim_col") or a["_year_col"]
                self.charts.append(
                    vz.scatter_chart(
                        f"Rainfall vs Production (per {pt_label})",
                        a["_rain_col"], a["_prod_col"],
                        [{a["_rain_col"]: round(float(r[0]), 1), a["_prod_col"]: round(float(r[1]), 1), "label": str(r[2])}
                         for r in pts.itertuples(index=False)],
                        point_label=pt_label,
                    )
                )
        elif "_year_col" in a and "trend" in a:
            t = a["trend"]
            self.charts.append(
                vz.line_chart(
                    "Sales by Year", "year", "sales",
                    [{"year": p, "sales": v} for p, v in zip(t["periods"], t["values"])],
                )
            )
            if "group_growth" in a:
                gg = a["group_growth"]
                self.charts.append(
                    vz.bar_chart(
                        f"Manufacturer growth {gg['period_from']}→{gg['period_to']} (%)",
                        "manufacturer", "growth_pct",
                        [{"manufacturer": k, "growth_pct": v} for k, v in gg["growth_pct_by_group"].items()],
                    )
                )
            if "anomalies" in a and a["anomalies"]["anomalies"]:
                marks = {p["period"] for p in a["anomalies"]["anomalies"]}
                self.charts.append(
                    vz.line_chart(
                        "Sales with anomaly flags", "year", "sales",
                        [{"year": p, "sales": v, "anomaly": p in marks} for p, v in zip(t["periods"], t["values"])],
                    )
                )
        return {"charts": len(self.charts)}

    def _find_col(self, keywords: list[str]) -> str | None:
        df = self.joined if self.joined is not None else next(iter(self.frames.values()), None)
        if df is None:
            return None
        for kw in keywords:
            for c in df.columns:
                if kw in c:
                    return c
        return None


def store_local_copy_from_bytes(raw: bytes, name: str, file_type: str):
    from pathlib import Path

    from ..services.cloudinary import store_local_copy
    import tempfile

    suffix = ".xlsx" if file_type in {"xlsx", "xls"} else ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="dp_") as f:
        f.write(raw)
        return Path(f.name)
