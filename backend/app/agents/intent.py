"""Deterministic natural-language understanding — built from scratch.

Converts an ambiguous English question into structured intent (spec §12) with
no external LLM: regex + keyword heuristics over domain/time/dimension/
metric/analysis patterns. Confidence per field drives clarifying questions.
An optional OpenAI key upgrades phrasing/edge cases but is never required.
"""
from __future__ import annotations

import re
from typing import Any

MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"

TOPIC_PATTERNS: list[tuple[str, str, list[str]]] = [
    # (topic_key, display, regex alternatives)
    ("ev_sales", "EV sales", [r"\bev\b", r"electric\s+vehicle", r"electric\s+car", r"\bev sales\b"]),
    ("rainfall", "rainfall", [r"rainfall", r"\brain\b", r"precipitation", r"monsoon"]),
    ("crop_production", "crop production", [r"crop", r"wheat", r"rice", r"production\s+of\s+(wheat|rice|crop)"]),
    ("sales", "sales", [r"\bsales\b", r"revenue", r"turnover"]),
    ("customer_churn", "customer churn", [r"churn", r"attrition"]),
    ("price", "price", [r"\bprice", r"\bcost\b"]),
]

REGION_PATTERNS: list[tuple[str, str]] = [
    (r"\bharyana\b", "Haryana"),
    (r"\bpunjab\b", "Punjab"),
    (r"\bindia\b", "India"),
    (r"\bdelhi\b", "Delhi"),
    (r"\bmumbai\b|\bmaharashtra\b", "Maharashtra"),
    (r"\bup\b|\buttar\s+pradesh\b", "Uttar Pradesh"),
]

# Analysis intents, priority-ordered
ANALYSIS_PATTERNS: list[tuple[str, list[str]]] = [
    ("relationship", [r"relationship", r"correlat", r"\bvs\.?\b", r"\bversus\b", r"impact\s+of", r"influence", r"affect", r"depend"]),
    ("anomaly", [r"unusual", r"anomal", r"spike", r"outlier", r"sudden\s+(drop|increase|change)", r"irregular"]),
    ("growth_comparison", [r"growth", r"fastest", r"fastest-growing", r"fastest\s+growing", r"compared?\s+to", r"compare"]),
    ("trend", [r"trend", r"over\s+time", r"year\s+on\s+year", r"yoy", r"growth\s+rate", r"\bgrew\b", r"increase"]),
    ("distribution", [r"distribution", r"spread", r"histogram", r"variance"]),
    ("summary", [r"average", r"\bmean\b", r"total", r"\bsum\b", r"how\s+much", r"how\s+many"]),
]

DIMENSION_HINTS: list[tuple[str, str]] = [
    (r"\bdistricts?\b", "district"),
    (r"\bmanufactur|\bmaker|carmaker|automaker|\bbrands?\b", "manufacturer"),
    (r"\bstates?\b", "state"),
    (r"\bregions?\b", "region"),
    (r"\byears?\b|\byearly\b|\bannually\b", "year"),
]

WHY_PATTERN = re.compile(r"\bwhy\b", re.I)


def extract_intent(text: str) -> dict[str, Any]:
    """Extract structured intent from a natural-language question."""
    t = text.lower()
    intent: dict[str, Any] = {
        "raw_query": text,
        "topic": None,
        "secondary_topics": [],
        "region": None,
        "start_year": None,
        "end_year": None,
        "dimensions": [],
        "metrics": [],
        "analysis": [],
        "clarifying_questions": [],
        "confidence": {},
    }

    # --- Topic(s) ---
    found_topics: list[str] = []
    for key, display, patterns in TOPIC_PATTERNS:
        if any(re.search(p, t) for p in patterns):
            found_topics.append(key)
    if "rainfall" in found_topics and "crop_production" in found_topics:
        intent["topic"] = "rainfall_vs_crop"
        intent["secondary_topics"] = ["rainfall", "crop_production"]
    elif found_topics:
        intent["topic"] = found_topics[0]
        intent["secondary_topics"] = found_topics[1:4]
    else:
        intent["topic"] = "generic"
        intent["confidence"]["topic"] = 0.3
        intent["clarifying_questions"].append(
            "What kind of data should I analyze (sales, rainfall, production, churn...)?"
        )

    # --- Region ---
    for pat, name in REGION_PATTERNS:
        if re.search(pat, t):
            intent["region"] = name
            break

    # --- Years ---
    years = [int(m) for m in re.findall(r"\b((?:19|20)\d{2})\b", t)]
    if len(years) >= 2:
        intent["start_year"], intent["end_year"] = min(years), max(years)
    elif len(years) == 1:
        intent["end_year"] = years[0]
        intent["clarifying_questions"].append("Which start year should I use?")
        intent["confidence"]["time_range"] = 0.5
    elif re.search(r"last\s+(\d+)\s+years?", t):
        n = int(re.search(r"last\s+(\d+)\s+years?", t).group(1))
        intent["end_year"] = 2025
        intent["start_year"] = 2025 - n
    else:
        intent["confidence"]["time_range"] = 0.35
        intent["clarifying_questions"].append("Which time period should I analyze?")

    # --- Dimensions ---
    for pat, dim in DIMENSION_HINTS:
        if re.search(pat, t) and dim not in intent["dimensions"]:
            intent["dimensions"].append(dim)

    # --- Analysis types ---
    for key, patterns in ANALYSIS_PATTERNS:
        if any(re.search(p, t) for p in patterns):
            if key not in intent["analysis"]:
                intent["analysis"].append(key)

    # --- Causal "why" question guard (spec §53/54) ---
    if WHY_PATTERN.search(t):
        intent["analysis"] = [a for a in intent["analysis"] if a != "growth_comparison"]
        intent["analysis"].insert(0, "causal_explanation")

    # --- Two-variable topics imply relationship analysis (rainfall vs crop) ---
    if intent["topic"] == "rainfall_vs_crop" and "relationship" not in intent["analysis"]:
        intent["analysis"].insert(0, "relationship")

    # --- Two-variable topics imply relationship analysis (rainfall vs crop) ---
    if intent["topic"] == "rainfall_vs_crop" and "relationship" not in intent["analysis"]:
        intent["analysis"].insert(0, "relationship")

    # --- Metrics ---
    metric_set: set[str] = set()
    if intent["topic"] in ("rainfall_vs_crop", "rainfall"):
        metric_set.update(["rainfall_mm", "production_tonnes"])
    if intent["topic"] in ("ev_sales", "sales"):
        metric_set.update(["sales_units"])
    if "growth_comparison" in intent["analysis"] or "trend" in intent["analysis"]:
        metric_set.add("growth_rate")
    intent["metrics"] = sorted(metric_set)

    # --- Confidence ---
    intent["confidence"]["topic"] = intent["confidence"].get("topic", 0.9 if intent["topic"] != "generic" else 0.3)
    intent["confidence"]["region"] = 0.85 if intent["region"] else 0.2
    intent["confidence"]["analysis"] = 0.9 if intent["analysis"] else 0.3
    if not intent["analysis"]:
        intent["analysis"] = ["summary", "trend"]
        intent["clarifying_questions"].append(
            "Should I focus on trends, comparisons, or anomalies? (I'll start with a summary + trend.)"
        )

    return intent


def intent_summary(intent: dict[str, Any]) -> str:
    parts = [f"topic={intent['topic']}"]
    if intent["region"]:
        parts.append(f"region={intent['region']}")
    if intent["start_year"] and intent["end_year"]:
        parts.append(f"period={intent['start_year']}–{intent['end_year']}")
    if intent["dimensions"]:
        parts.append(f"dims={','.join(intent['dimensions'])}")
    parts.append(f"analysis={','.join(intent['analysis'])}")
    return ", ".join(parts)


# ---------------- Optional OpenAI enhancer ----------------

async def refine_intent_with_llm(intent: dict[str, Any], text: str) -> dict[str, Any]:
    """Optionally improve intent with OpenAI structured output. Never required."""
    import os

    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        return intent
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI()
        prompt = (
            "Extract analysis intent as JSON with keys topic, region, start_year, end_year, "
            "dimensions (list), metrics (list), analysis (subset of summary|trend|growth_comparison|"
            "relationship|anomaly|distribution), clarifying_questions (list). Question: " + text
        )
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=15,
        )
        import json

        data = json.loads(resp.choices[0].message.content)
        for k, v in data.items():
            if k in intent and v:
                intent[k] = v
    except Exception:
        pass  # enhancer only — deterministic intent stands
    return intent
