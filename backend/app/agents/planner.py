"""Workflow planner — turns structured intent into a dynamic step graph.

This is what makes workflows change with the question (spec §8): a
relationship question inserts normalization + join steps; an anomaly question
inserts anomaly detection; a growth comparison inserts per-group ranking.
Steps map 1:1 to the controlled tool layer (agents/tools.py).
"""
from __future__ import annotations

from typing import Any


def plan_workflow(intent: dict[str, Any], available_datasets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compose an ordered step list tailored to the intent.

    available_datasets: [{id, name, source_type, ...}] already matched to the
    intent by the orchestrator.
    """
    steps: list[dict[str, Any]] = []
    analysis = set(intent.get("analysis") or [])
    topic = intent.get("topic")

    steps.append(
        {
            "step_type": "intent",
            "title": "Understand request",
            "params": {},
        }
    )
    steps.append(
        {
            "step_type": "source_discovery",
            "title": "Find permitted sources",
            "params": {"topic": topic},
        }
    )

    # One collection step per matched dataset (dynamic fan-out, spec §49)
    for ds in available_datasets:
        steps.append(
            {
                "step_type": "collect",
                "title": f"Collect: {ds['name']}",
                "params": {"dataset_id": ds["id"]},
            }
        )

    steps.append({"step_type": "process", "title": "Clean & normalize data", "params": {}})

    # --- Dynamic branches ---

    # Relationship across two different datasets → join with key normalization
    if "relationship" in analysis and len(available_datasets) >= 2:
        steps.append({"step_type": "normalize_join_keys", "title": "Normalize join keys", "params": {}})
        steps.append({"step_type": "join", "title": "Join datasets", "params": {}})

    # Growth comparisons on a dimension → group ranking
    if "growth_comparison" in analysis:
        steps.append({"step_type": "aggregate", "title": "Aggregate by dimension", "params": {}})

    # Trend/anomaly need strict time-series ordering
    if ("trend" in analysis or "anomaly" in analysis) and intent.get("start_year"):
        steps.append(
            {
                "step_type": "filter_period",
                "title": f"Filter {intent.get('start_year')}–{intent.get('end_year')}",
                "params": {"start": intent.get("start_year"), "end": intent.get("end_year")},
            }
        )

    steps.append({"step_type": "validate", "title": "Validate data quality", "params": {}})
    steps.append({"step_type": "analysis", "title": "Run analyses", "params": {"analysis": sorted(analysis)}})
    steps.append({"step_type": "visualize", "title": "Generate visualizations", "params": {}})
    steps.append({"step_type": "insights", "title": "Generate insights", "params": {}})
    steps.append({"step_type": "evidence", "title": "Assemble evidence trail", "params": {}})

    return steps


STEP_GRAPH_NODES = [
    "USER QUERY",
    "UNDERSTAND",
    "PLAN",
    "SOURCES",
    "COLLECT",
    "PROCESS",
    "VALIDATE",
    "ANALYZE",
    "VISUALIZE",
    "INSIGHTS",
    "EVIDENCE",
]
