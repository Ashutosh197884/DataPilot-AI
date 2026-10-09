"""AI Orchestrator — the brain that runs a workflow from a natural-language query.

Flow (spec §48): store query → extract intent → plan steps → execute each step
through the controlled tool layer → persist workflow steps/results/insights/
evidence → publish SSE events as it goes. Runs in a worker thread so the API
returns immediately and the UI streams progress.
"""
from __future__ import annotations

import datetime as dt
import threading
import traceback
from typing import Any

from sqlalchemy.orm import Session

from ..models import (
    AnalysisResult,
    Dataset,
    Evidence,
    Insight,
    Query,
    SessionLocal,
    ValidationRun,
    WorkflowRun,
    WorkflowStep,
)
from ..services import cloudinary as cl
from ..services.events import event_bus
from . import intent as it
from . import insight as ins
from . import planner
from .tools import ToolContext


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def start_workflow(query_id: str, text: str, project_id: str, db_session_factory=SessionLocal) -> str:
    """Create the WorkflowRun + planned steps, then execute in background."""
    db = db_session_factory()
    try:
        query = db.get(Query, query_id)
        query.status = "RUNNING"
        run = WorkflowRun(query_id=query_id, status="RUNNING")
        db.add(run)
        db.flush()

        intent = it.extract_intent(text)
        query.structured_intent = intent

        # Match intent topics -> candidate datasets (only permitted, project-scoped)
        candidates = _match_datasets(db, intent, project_id)
        step_specs = planner.plan_workflow(intent, candidates)

        for i, spec in enumerate(step_specs, start=1):
            db.add(
                WorkflowStep(
                    workflow_id=run.id,
                    step_number=i,
                    step_type=spec["step_type"],
                    title=spec["title"],
                    input=spec.get("params", {}),
                    status="PENDING",
                )
            )
        db.commit()
        workflow_id = run.id
    finally:
        db.close()

    thread = threading.Thread(target=_execute, args=(workflow_id, query_id, text, project_id), daemon=True)
    thread.start()
    return workflow_id


def _match_datasets(db: Session, intent: dict[str, Any], project_id: str) -> list[dict[str, Any]]:
    """Map intent topics to existing, permitted datasets (dynamic source match)."""
    topic = intent.get("topic")
    wanted_cols: list[str] = []
    if topic in ("rainfall_vs_crop", "rainfall"):
        wanted_cols = ["rainfall"]
    if topic in ("rainfall_vs_crop", "crop_production"):
        wanted_cols.append("production")
    if topic in ("ev_sales", "sales", "generic"):
        wanted_cols = ["sales", "units", "registrations"]

    datasets = db.query(Dataset).filter(Dataset.project_id == project_id).all()
    scored: list[tuple[int, Dataset]] = []
    for ds in datasets:
        schema = ds.schema_json or {}
        cols = [c.get("name", "") for c in schema.get("columns", [])]
        cols_lower = [c.lower() for c in cols]
        score = sum(1 for w in wanted_cols for c in cols_lower if w in c)
        if intent.get("region") and intent["region"].lower() in ds.name.lower():
            score += 2
        if score > 0:
            scored.append((score, ds))
    scored.sort(key=lambda x: -x[0])
    return [{"id": ds.id, "name": ds.name, "source_type": ds.source_type} for _, ds in scored[:2]]


def _execute(workflow_id: str, query_id: str, text: str, project_id: str) -> None:
    """Worker-thread execution: step through the plan with the tool layer."""
    db = SessionLocal()
    ctx: ToolContext | None = None
    try:
        run = db.get(WorkflowRun, workflow_id)
        steps = db.query(WorkflowStep).filter(WorkflowStep.workflow_id == workflow_id).order_by(WorkflowStep.step_number).all()
        query = db.get(Query, query_id)
        intent = query.structured_intent or {}

        event_bus.publish(workflow_id, "workflow.started", {"query": text})

        # Match datasets again for the context (we need ORM objects)
        candidates = _match_datasets(db, intent, project_id)
        ds_rows = [db.get(Dataset, c["id"]) for c in candidates]
        ctx = ToolContext(db, workflow_id, intent, [d for d in ds_rows if d])

        # ---------- Understand ----------
        _run_step(db, run, steps, "intent", lambda: {
            "intent": intent,
            "summary": it.intent_summary(intent),
            "clarifying_questions": intent.get("clarifying_questions", []),
            "dimensions": len(intent.get("dimensions", [])),
        }, workflow_id)

        # ---------- Source discovery ----------
        def do_sources() -> dict:
            from ..services.source_registry import allowed_sources

            srcs = allowed_sources(db)
            return {
                "sources_found": [
                    {"id": s.id, "name": s.name, "type": s.type, "license": s.license}
                    for s in srcs
                    if s.domain in ("any", "agriculture", "transport") or s.type == "upload"
                ],
                "matched_datasets": candidates,
            }

        _run_step(db, run, steps, "source_discovery", do_sources, workflow_id)

        # ---------- Collect ----------
        for ds in ctx.datasets:
            _run_step(db, run, steps, "collect", (lambda d=ds: ctx.load_dataset(d)), workflow_id)

        # ---------- Process ----------
        _run_step(db, run, steps, "process", ctx.clean, workflow_id)

        # ---------- Dynamic branches (normalize + join) ----------
        def _find(step_type: str) -> WorkflowStep | None:
            return next((s for s in steps if s.step_type == step_type), None)

        ns = _find("normalize_join_keys")
        if ns:
            _run_step(db, run, steps, "normalize_join_keys", ctx.normalize_join_keys, workflow_id)
        js = _find("join")
        if js:
            def do_join() -> dict:
                key_cols = ["district", "year"] if "district" in (ctx.joined_cols if hasattr(ctx, "joined_cols") else _common_cols(ctx)) else _common_cols(ctx)
                return ctx.join(key_cols)
            _run_step(db, run, steps, "join", do_join, workflow_id)

        # ---------- Aggregate (if planned) ----------
        ag = _find("aggregate")
        if ag:
            _run_step(db, run, steps, "aggregate", ctx.aggregate, workflow_id)

        # ---------- Filter period ----------
        fp = _find("filter_period")
        if fp:
            _run_step(db, run, steps, "filter_period", (lambda: ctx.filter_period(fp.input["start"], fp.input["end"])), workflow_id)

        # ---------- Validate ----------
        def do_validate() -> dict:
            out = ctx.validate()
            # persist ValidationRun
            rep = ctx.validation
            vr = ValidationRun(
                dataset_id=ctx.datasets[0].id,
                workflow_id=workflow_id,
                completeness=rep["completeness"],
                duplicate_count=rep["duplicate_count"],
                invalid_count=rep["invalid_count"],
                schema_valid=rep["schema_valid"],
                quality_score=rep["quality_score"],
                validation_details=rep,
            )
            db.add(vr)
            return out

        _run_step(db, run, steps, "validate", do_validate, workflow_id)

        # ---------- Analysis (also snapshots chart configs for the dashboard) ----------
        def do_analysis() -> dict:
            ctx.analysis["_dim_col"] = ctx._find_col(["district", "state", "region"])
            out = ctx.run_analysis()
            for atype, result in ctx.analysis.items():
                if atype.startswith("_"):
                    continue
                calc = ""
                if isinstance(result, dict):
                    calc = result.get("calculation", "")
                db.add(AnalysisResult(workflow_id=workflow_id, analysis_type=atype, result=result, calculation=calc))
            # Snapshot charts so the dashboard API can rebuild them from the DB alone
            ctx.generate_charts()
            db.add(
                AnalysisResult(
                    workflow_id=workflow_id,
                    analysis_type="_chart_snapshot",
                    result={"charts": ctx.charts},
                    calculation="",
                )
            )
            return out

        _run_step(db, run, steps, "analysis", do_analysis, workflow_id)

        # ---------- Visualize ----------
        _run_step(db, run, steps, "visualize", ctx.generate_charts, workflow_id)  # configs live in ctx.charts + snapshot

        # ---------- Insights + Evidence ----------
        def do_insights() -> dict:
            insights, kpi_cards = ins.build_insights(intent, ctx.analysis, ctx.validation["quality_score"] if ctx.validation else None)
            insights = ins.polish_with_llm_sync(insights) if hasattr(ins, "polish_with_llm_sync") else insights
            saved = []
            for i in insights:
                row = Insight(
                    workflow_id=workflow_id,
                    title=i["title"],
                    description=i["description"],
                    calculation=i.get("calculation", ""),
                    confidence=i.get("confidence", 0.8),
                    kind=i.get("kind", "descriptive"),
                )
                db.add(row)
                db.flush()
                saved.append((row, i))
            db.flush()

            # Evidence rows: chain each insight -> dataset -> source -> cloudinary
            primary_ds = ctx.datasets[0] if ctx.datasets else None
            for row, i in saved:
                ev = Evidence(
                    insight_id=row.id,
                    dataset_id=primary_ds.id if primary_ds else None,
                    source_id=primary_ds.source_id if primary_ds else None,
                    transformations=[t["detail"] for t in ctx.transformations],
                    calculation=i.get("calculation", ""),
                    source_reference=(
                        f"Cloudinary:{primary_ds.cloudinary_public_id}" if primary_ds and primary_ds.cloudinary_public_id
                        else (primary_ds.local_path if primary_ds else "bundled snapshot")
                    ),
                )
                db.add(ev)
            return {"insights": len(saved), "kpis": kpi_cards}

        _run_step(db, run, steps, "insights", do_insights, workflow_id)

        # ---------- Evidence ----------
        def do_evidence() -> dict:
            return {
                "dataset": primary_ds_summary(ctx),
                "transformations": [t["detail"] for t in ctx.transformations],
                "validation": {
                    "quality": ctx.validation["quality_score"] if ctx.validation else None,
                    "completeness": ctx.validation["completeness"] if ctx.validation else None,
                },
                "cloudinary": {
                    "configured": cl.configured(),
                    "public_id": ctx.datasets[0].cloudinary_public_id if ctx.datasets else None,
                },
            }

        ev_step = _find("evidence")
        if ev_step:
            _run_step(db, run, steps, "evidence", do_evidence, workflow_id)

        # ---------- Done ----------
        run.status = "COMPLETED"
        run.completed_at = _now()
        query.status = "COMPLETED"
        db.commit()
        event_bus.publish(workflow_id, "workflow.completed", {"quality": ctx.validation["quality_score"] if ctx.validation else None})
    except Exception as e:
        db.rollback()
        try:
            run = db.get(WorkflowRun, workflow_id)
            if run:
                run.status = "FAILED"
                query = db.get(Query, query_id)
                if query:
                    query.status = "FAILED"
                failed = next((s for s in run.steps if s.status in ("RUNNING", "PENDING")), None)
                if failed:
                    failed.status = "FAILED"
                    failed.error = f"{type(e).__name__}: {e}"
                db.commit()
        except Exception:
            db.rollback()
        event_bus.publish(workflow_id, "workflow.failed", {"error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-800:]})
    finally:
        db.close()


def _run_step(
    db: Session,
    run: WorkflowRun,
    steps: list[WorkflowStep],
    step_type: str,
    fn,
    workflow_id: str,
) -> None:
    """Execute one planned step with RUNNING/COMPLETED events + persistence."""
    step = next((s for s in steps if s.step_type == step_type and s.status == "PENDING"), None)
    if step is None:
        return
    step.status = "RUNNING"
    step.started_at = _now()
    db.commit()
    event_bus.publish(workflow_id, "workflow.step.started", {"step": step_type, "title": step.title, "number": step.step_number})
    try:
        out = fn()
        step.output = out
        step.status = "COMPLETED"
        step.completed_at = _now()
        db.commit()
        event_bus.publish(workflow_id, "workflow.step.completed", {"step": step_type, "title": step.title, "number": step.step_number, "output": _compact(out)})
    except Exception as e:
        step.status = "FAILED"
        step.error = f"{type(e).__name__}: {e}"
        step.completed_at = _now()
        db.commit()
        raise


def _compact(out: Any, limit: int = 2000) -> Any:
    """Shrink step output for SSE payloads (full output stays in DB)."""
    s = repr(out)
    if len(s) > limit:
        return s[:limit] + "…"
    return out


def _common_cols(ctx: ToolContext) -> list[str]:
    """Join keys = common columns across loaded frames, preferring dims+year."""
    frames = list(ctx.frames.values())
    if len(frames) < 2:
        return []
    common = set(frames[0].columns)
    for f in frames[1:]:
        common &= set(f.columns)
    preferred = [c for c in ("district", "state", "region", "manufacturer", "year") if c in common]
    return preferred or sorted(common)


def primary_ds_summary(ctx: ToolContext) -> dict | None:
    if not ctx.datasets:
        return None
    d = ctx.datasets[0]
    return {
        "id": d.id,
        "name": d.name,
        "records": d.record_count,
        "cloudinary_public_id": d.cloudinary_public_id,
        "cloudinary_url": d.cloudinary_url,
        "file_type": d.file_type,
    }
