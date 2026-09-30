"""Query API — the most important endpoint (spec §31)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..agents import orchestrator
from ..models import Project, Query, get_db

router = APIRouter()


class QueryCreate(BaseModel):
    project_id: str
    query: str = Field(min_length=3, max_length=2000)


@router.post("/queries", status_code=201)
def create_query(body: QueryCreate, db: Session = Depends(get_db)):
    project = db.get(Project, body.project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    q = Query(project_id=body.project_id, text=body.query, status="PLANNING")
    db.add(q)
    db.commit()

    workflow_id = orchestrator.start_workflow(q.id, q.text, body.project_id)
    return {
        "query_id": q.id,
        "workflow_id": workflow_id,
        "status": "RUNNING",
    }
