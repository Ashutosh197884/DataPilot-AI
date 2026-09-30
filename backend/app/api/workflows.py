"""Workflow APIs — status/steps, live SSE stream, and the dashboard payload."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from ..models import (
    AnalysisResult,
    Dataset,
    Insight,
    ValidationRun,
    WorkflowRun,
    WorkflowStep,
    get_db,
)
from ..services import cloudinary as cl
from ..services.events import EventBus, event_bus

router = APIRouter()


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str, db: Session = Depends(get_db)):
    run = db.get(WorkflowRun, workflow_id)
    if not run:
        raise HTTPException(404, "Workflow not found")
    steps = (
        db.query(WorkflowStep)
        .filter(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.step_number)
        .all()
    )
    return {
        "id": run.id,
        "query_id": run.query_id,
        "status": run.status,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "steps": [
            {
                "number": s.step_number,
                "type": s.step_type,
                "title": s.title,
                "status": s.status,
                "output": s.output,
                "error": s.error,
            }
            for s in steps
        ],
    }


@router.get("/workflows/{workflow_id}/events")
async def workflow_events(workflow_id: str):
    """SSE stream of workflow events (with replay for late subscribers)."""
    queue = await event_bus.subscribe(workflow_id)

    async def generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                    continue
                yield EventBus.sse_format(event)
                if event["type"] in ("workflow.completed", "workflow.failed"):
                    break
        finally:
            event_bus.unsubscribe(workflow_id, queue)

    return EventSourceResponse(generator())


@router.get("/workflows/{workflow_id}/dashboard")
def workflow_dashboard(workflow_id: str, db: Session = Depends(get_db)):
    """Everything the intelligence dashboard renders: KPIs, charts, insights, quality."""
    run = db.get(WorkflowRun, workflow_id)
    if not run:
        raise HTTPException(404, "Workflow not found")
    if run.status not in ("COMPLETED", "FAILED"):
        raise HTTPException(409, f"Workflow still {run.status}")

    query = run.query
    intent = query.structured_intent or {}
    insights = db.query(Insight).filter(Insight.workflow_id == workflow_id).order_by(Insight.created_at).all()
    vr = db.query(ValidationRun).filter(ValidationRun.workflow_id == workflow_id).order_by(ValidationRun.created_at.desc()).first()
    results = db.query(AnalysisResult).filter(AnalysisResult.workflow_id == workflow_id).all()

    # Rebuild KPI cards from persisted analysis results (same logic as live step)
    from ..agents import insight as ins

    analysis_map = {r.analysis_type: r.result for r in results}
    _, kpis = ins.build_insights(intent, analysis_map, vr.quality_score if vr else None)
    snapshot = analysis_map.get("_chart_snapshot", {}).get("charts", [])
    charts = snapshot if snapshot else _rebuild_charts(analysis_map, intent)

    # charts set above: snapshot from the run when present, deterministic
    # rebuild from analysis results otherwise

    dataset = None
    if vr:
        ds = db.get(Dataset, vr.dataset_id)
        if ds:
            dataset = {
                "id": ds.id,
                "name": ds.name,
                "records": ds.record_count,
                "cloudinary_public_id": ds.cloudinary_public_id,
                "cloudinary_url": ds.cloudinary_url,
            }

    return {
        "workflow_id": workflow_id,
        "query": query.text,
        "topic": intent.get("topic"),
        "region": intent.get("region"),
        "period": [intent.get("start_year"), intent.get("end_year")],
        "kpis": kpis,
        "charts": charts,
        "insights": [
            {
                "id": i.id,
                "title": i.title,
                "description": i.description,
                "calculation": i.calculation,
                "confidence": i.confidence,
                "kind": i.kind,
            }
            for i in insights
        ],
        "quality": {
            "score": vr.quality_score if vr else None,
            "completeness": vr.completeness if vr else None,
            "duplicates": vr.duplicate_count if vr else None,
            "invalid": vr.invalid_count if vr else None,
            "schema_valid": vr.schema_valid if vr else None,
            "details": (vr.validation_details or {}).get("checks", []) if vr else [],
        },
        "dataset": dataset,
    }


def _rebuild_charts(analysis_map: dict, intent: dict) -> list[dict]:
    """Deterministic chart configs from persisted analysis results."""
    from ..engines import visualization as vz

    charts: list[dict] = []
    topic = intent.get("topic")

    if "trend" in analysis_map:
        t = analysis_map["trend"]
        label = "Production by Year" if topic in ("rainfall_vs_crop", "crop_production", "rainfall") else "Sales by Year"
        y = "prod" if "prod" in str(t.get("values", [0]))[:1] else "sales"
        charts.append(
            vz.line_chart(
                label, "year", y,
                [{"year": p, "value": v} for p, v in zip(t["periods"], t["values"])],
            )
        )

    if "avg_rainfall" in analysis_map and "_yearly" in analysis_map:
        yearly = analysis_map["_yearly"]
        charts.append(
            vz.line_chart(
                "Average Rainfall by Year", "year", "rain",
                [{"year": int(r["year"]), "rain": round(r["rain"], 1)} for r in yearly],
            )
        )

    if "correlation" in analysis_map and "_scatter" in analysis_map:
        s = analysis_map["_scatter"]
        charts.append(
            vz.scatter_chart(
                f"Rainfall vs Production (per {s.get('label', 'point')})",
                s["x"], s["y"], s["points"], point_label=s.get("label"),
            )
        )

    if "group_growth" in analysis_map:
        gg = analysis_map["group_growth"]
        charts.append(
            vz.bar_chart(
                f"Growth by {gg['group_column']} {gg['period_from']}→{gg['period_to']} (%)",
                gg["group_column"], "growth_pct",
                [{"name": k, "growth_pct": v} for k, v in gg["growth_pct_by_group"].items()],
            )
        )

    if "anomalies" in analysis_map and analysis_map["anomalies"].get("anomalies"):
        t = analysis_map.get("trend", {})
        marks = {p["period"] for p in analysis_map["anomalies"]["anomalies"]}
        if t.get("periods"):
            charts.append(
                vz.line_chart(
                    "Anomaly flags", "year", "value",
                    [{"year": p, "value": v, "anomaly": p in marks} for p, v in zip(t["periods"], t["values"])],
                )
            )
    return charts


@router.get("/workflows/{workflow_id}/evidence")
def workflow_evidence(workflow_id: str, db: Session = Depends(get_db)):
    """The lineage chain: insight -> calculation -> transformations -> validation -> dataset -> cloudinary -> source."""
    run = db.get(WorkflowRun, workflow_id)
    if not run:
        raise HTTPException(404, "Workflow not found")

    from ..models import Evidence

    evidences = db.query(Evidence).filter(Evidence.insight_id.in_(
        [i.id for i in db.query(Insight).filter(Insight.workflow_id == workflow_id).all()]
    )).all()

    query = run.query
    intent = query.structured_intent or {}

    def ds_info(ds_id):
        ds = db.get(Dataset, ds_id)
        if not ds:
            return None
        src = db.get(DataSourceLite, ds.source_id) if ds.source_id else None
        return {
            "id": ds.id,
            "name": ds.name,
            "records": ds.record_count,
            "file_type": ds.file_type,
            "cloudinary_public_id": ds.cloudinary_public_id,
            "cloudinary_url": ds.cloudinary_url,
            "coverage": ds.coverage_period,
            "retrieved_at": ds.retrieved_at.isoformat() if ds.retrieved_at else None,
            "source": {
                "id": src.id,
                "name": src.name,
                "license": src.license,
                "last_updated": src.last_updated,
            } if src else None,
        }

    items = []
    for ev in evidences:
        insight = db.get(Insight, ev.insight_id)
        items.append(
            {
                "insight": {"id": insight.id, "title": insight.title, "description": insight.description, "kind": insight.kind},
                "calculation": ev.calculation,
                "transformations": ev.transformations or [],
                "dataset": ds_info(ev.dataset_id),
                "validation": _validation_for(db, workflow_id),
                "source_reference": ev.source_reference,
            }
        )

    return {
        "workflow_id": workflow_id,
        "query": query.text,
        "chain_summary": {
            "region": intent.get("region"),
            "period": [intent.get("start_year"), intent.get("end_year")],
        },
        "evidence_items": items,
    }


def _validation_for(db: Session, workflow_id: str) -> dict | None:
    vr = db.query(ValidationRun).filter(ValidationRun.workflow_id == workflow_id).order_by(ValidationRun.created_at.desc()).first()
    if not vr:
        return None
    return {
        "quality": vr.quality_score,
        "completeness": vr.completeness,
        "duplicates": vr.duplicate_count,
        "invalid": vr.invalid_count,
        "schema_valid": vr.schema_valid,
    }


from ..models import DataSource as DataSourceLite  # noqa: E402
