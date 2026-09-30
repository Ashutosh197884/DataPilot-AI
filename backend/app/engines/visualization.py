"""Visualization engine — emits chart CONFIG, never raw HTML/JS.

The frontend renders these configs with Recharts. The planner/insight engine
chooses chart types based on analysis shape (spec §23).
"""
from __future__ import annotations

from typing import Any


def _trim(rows: list[dict[str, Any]], max_points: int = 200) -> list[dict[str, Any]]:
    return rows[:max_points]


def line_chart(title: str, x: str, y: str, data: list[dict[str, Any]], group: str | None = None) -> dict[str, Any]:
    return {
        "type": "line",
        "title": title,
        "x": x,
        "y": y,
        "group": group,
        "data": _trim(data),
    }


def bar_chart(title: str, x: str, y: str, data: list[dict[str, Any]], horizontal: bool = False) -> dict[str, Any]:
    return {
        "type": "bar",
        "title": title,
        "x": x,
        "y": y,
        "horizontal": horizontal,
        "data": _trim(data),
    }


def scatter_chart(title: str, x: str, y: str, data: list[dict[str, Any]], point_label: str | None = None) -> dict[str, Any]:
    return {
        "type": "scatter",
        "title": title,
        "x": x,
        "y": y,
        "point_label": point_label,
        "data": _trim(data, 500),
    }


def kpi_card(label: str, value: Any, hint: str | None = None) -> dict[str, Any]:
    return {"type": "kpi", "label": label, "value": value, "hint": hint}


def table(title: str, columns: list[str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "table", "title": title, "columns": columns, "data": _trim(rows, 50)}
