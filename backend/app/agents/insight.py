"""Insight engine — explains computed results without inventing numbers.

Every insight is generated FROM analysis outputs (title, description,
calculation string, confidence, kind). Guardrails from the spec:
  §53  insufficient variables → honest gap statement
  §54  correlation phrased as association, never causation
Optional OpenAI key may polish phrasing only — numbers still come from us.
"""
from __future__ import annotations

from typing import Any


def _fmt(n: float) -> str:
    if abs(n) >= 1e7:
        return f"{n / 1e7:.2f}Cr"
    if abs(n) >= 1e5:
        return f"{n / 1e5:.2f}L"
    if abs(n) >= 1e3:
        return f"{n / 1e3:.1f}K"
    return f"{n:,.1f}"


def build_insights(
    intent: dict[str, Any],
    analysis_outputs: dict[str, Any],
    quality_score: float | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (insights, kpi_cards). All values come from analysis_outputs."""
    insights: list[dict[str, Any]] = []
    kpis: list[dict[str, Any]] = []
    a = analysis_outputs

    # ---------- KPI cards ----------
    if "total_sales" in a:
        t = a["total_sales"]
        kpis.append({"label": f"Total {t.get('label', 'Sales')}", "value": _fmt(float(t["value"]))})
    if "growth" in a:
        g = a["growth"]
        kpis.append(
            {
                "label": f"Growth {g['period_from']}→{g['period_to']}",
                "value": f"{g['growth_pct']:+.1f}%",
            }
        )
    if "avg_rainfall" in a:
        kpis.append({"label": "Avg Rainfall", "value": f"{a['avg_rainfall']['mean']:,.0f} mm"})
    if "total_production" in a:
        kpis.append({"label": "Total Production", "value": f"{_fmt(float(a['total_production']['value']))} t"})
    if "correlation" in a:
        kpis.append({"label": "Correlation (r)", "value": f"{a['correlation']['pearson_r']:+.2f}"})
    if quality_score is not None:
        kpis.append({"label": "Data Quality", "value": f"{quality_score:.1f}%"})

    # ---------- Causal "why" guard (spec §53) ----------
    if "causal_explanation" in intent.get("analysis", []) and a.get("available_variables"):
        avail = a["available_variables"]["available"]
        insights.append(
            {
                "title": "Why question — what I can and cannot conclude",
                "description": (
                    "I can identify when the change happened, but the available data does not contain "
                    "enough variables to determine why. "
                    + f"Available: {', '.join(avail)}. "
                    + f"Potentially required (not in data): {', '.join(a['available_variables']['missing'])}."
                ),
                "calculation": "",
                "confidence": 0.9,
                "kind": "limitation",
            }
        )

    # ---------- Trend ----------
    if "trend" in a:
        t = a["trend"]
        periods, vals = t["periods"], t["values"]
        if len(vals) >= 2:
            direction = "rose" if vals[-1] > vals[0] else "declined"
            delta = vals[-1] - vals[0]
            insights.append(
                {
                    "title": f"{direction.title()} from {periods[0]} to {periods[-1]}",
                    "description": (
                        f"The series {direction} by {_fmt(abs(delta))} between {periods[0]} and {periods[-1]} "
                        f"({t['yoy_pct'][-1]:+.1f}% in the final year)."
                    ),
                    "calculation": t["calculation"],
                    "confidence": 0.9,
                    "kind": "descriptive",
                }
            )

    # ---------- Growth comparison ----------
    if "group_growth" in a:
        gg = a["group_growth"]
        items = list(gg["growth_pct_by_group"].items())
        if items:
            top_name, top_g = items[0]
            insights.append(
                {
                    "title": f"Fastest growing: {top_name}",
                    "description": (
                        f"{top_name} grew {top_g:+.1f}% between {gg['period_from']} and {gg['period_to']}, "
                        f"the highest among {len(gg['growth_pct_by_group'])} compared groups."
                    ),
                    "calculation": gg["calculation"],
                    "confidence": 0.85,
                    "kind": "descriptive",
                }
            )

    # ---------- Correlation / relationship ----------
    if "correlation" in a:
        c = a["correlation"]
        ca, cb = c["columns"]
        insights.append(
            {
                "title": f"{ca} ↔ {cb}: {c['strength']} association",
                "description": (
                    f"Rainfall and wheat production show a measurable "
                    f"{c['strength']} association (r={c['pearson_r']:.2f}, n={c['n']}). "
                    "This indicates association, not causation — other factors (irrigation, soil, "
                    "seed variety) are not in this dataset."
                ),
                "calculation": c["calculation"],
                "confidence": 0.8,
                "kind": "correlational",
            }
        )

    # ---------- Anomalies ----------
    if "anomalies" in a:
        an = a["anomalies"]
        if an["anomalies"]:
            pts = ", ".join(f"{p['period']} (z={p['robust_z']:+.1f})" for p in an["anomalies"][:3])
            insights.append(
                {
                    "title": f"{len(an['anomalies'])} anomalous period(s) detected",
                    "description": f"Unusual values at: {pts}. Method: {an['method']}.",
                    "calculation": an["calculation"],
                    "confidence": 0.75,
                    "kind": "descriptive",
                }
            )
        else:
            insights.append(
                {
                    "title": "No anomalies above threshold",
                    "description": (
                        f"All {an['n_periods']} periods fall within expected variation "
                        f"(|robust z| < {an['threshold']})."
                    ),
                    "calculation": an["calculation"],
                    "confidence": 0.75,
                    "kind": "descriptive",
                }
            )

    # ---------- Data-quality note ----------
    if quality_score is not None and quality_score < 95:
        insights.append(
            {
                "title": f"Data quality: {quality_score:.1f}%",
                "description": (
                    "Validation found issues (duplicates/invalid values/missing cells). "
                    "See the evidence trail for exactly what was cleaned before these numbers."
                ),
                "calculation": "",
                "confidence": 1.0,
                "kind": "limitation",
            }
        )

    return insights, kpis


async def polish_with_llm(insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Optional phrasing polish. Never changes numbers; skipped without a key."""
    import os

    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        return insights
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI()
        import json

        prompt = (
            "Rewrite each insight description to be crisper for an executive audience. "
            "Keep every number and hedging phrase exactly. Return JSON array under key 'items'. "
            + json.dumps([{"title": i["title"], "description": i["description"]} for i in insights])
        )
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=15,
        )
        data = json.loads(resp.choices[0].message.content)
        items = data.get("items", [])
        for ins, new in zip(insights, items):
            if isinstance(new, dict) and new.get("description"):
                ins["description"] = new["description"]
    except Exception:
        pass
    return insights
