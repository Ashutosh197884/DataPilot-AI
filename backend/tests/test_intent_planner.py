"""Intent extraction + planner tests using the spec's example queries."""
from __future__ import annotations

from app.agents import intent as it
from app.agents import planner


def test_ev_sales_query():
    intent = it.extract_intent("Compare EV sales in India from 2022 to 2025 and identify the fastest-growing manufacturers.")
    assert intent["topic"] == "ev_sales"
    assert intent["region"] == "India"
    assert (intent["start_year"], intent["end_year"]) == (2022, 2025)
    assert "manufacturer" in intent["dimensions"]
    assert "growth_comparison" in intent["analysis"]


def test_rainfall_wheat_query():
    intent = it.extract_intent("Compare rainfall and wheat production across Haryana districts from 2020 to 2025.")
    assert intent["topic"] == "rainfall_vs_crop"
    assert intent["region"] == "Haryana"
    assert (intent["start_year"], intent["end_year"]) == (2020, 2025)
    assert "district" in intent["dimensions"]
    assert "relationship" in intent["analysis"]


def test_anomaly_query():
    intent = it.extract_intent("Find unusual sales spikes in the last 5 years")
    assert "anomaly" in intent["analysis"]
    assert intent["start_year"] == 2020


def test_ambiguous_query_asks_clarification():
    intent = it.extract_intent("Show me sales in Delhi.")
    assert intent["region"] == "Delhi"
    assert len(intent["clarifying_questions"]) >= 1  # missing time period


def test_why_query_triggers_causal_guard():
    intent = it.extract_intent("Why did sales fall in 2024?")
    assert "causal_explanation" in intent["analysis"]


def test_planner_is_dynamic():
    q_a = it.extract_intent("Calculate average product price")
    q_b = it.extract_intent("Find relationship between rainfall and crop production for Haryana districts 2020 to 2025")
    q_c = it.extract_intent("Find unusual sales spikes 2022 to 2025")

    plan_a = planner.plan_workflow(q_a, [{"id": "d1", "name": "prices"}])
    plan_b = planner.plan_workflow(q_b, [{"id": "d1", "name": "rain"}, {"id": "d2", "name": "wheat"}])
    plan_c = planner.plan_workflow(q_c, [{"id": "d1", "name": "sales"}])

    types_a = [s["step_type"] for s in plan_a]
    types_b = [s["step_type"] for s in plan_b]
    types_c = [s["step_type"] for s in plan_c]

    # Relationship plan gets normalize+join; others don't
    assert "join" in types_b and "normalize_join_keys" in types_b
    assert "join" not in types_a and "join" not in types_c
    # Anomaly plan exists and differs structurally
    assert types_a != types_b != types_c


def test_intent_summary_readable():
    s = it.intent_summary(it.extract_intent("EV sales in India 2022 to 2025"))
    assert "ev_sales" in s and "2022" in s
