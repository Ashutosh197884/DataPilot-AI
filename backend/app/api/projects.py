"""Projects, queries history, and source registry APIs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..models import DataSource, Project, Query, WorkflowRun, get_db

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "created_at": p.created_at.isoformat(),
        }
        for p in projects
    ]


@router.post("/projects", status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    p = Project(name=body.name, description=body.description)
    db.add(p)
    db.commit()
    return {"id": p.id, "name": p.name}


@router.get("/projects/{project_id}/queries")
def project_queries(project_id: str, db: Session = Depends(get_db)):
    queries = (
        db.query(Query)
        .filter(Query.project_id == project_id)
        .order_by(Query.created_at.desc())
        .all()
    )
    out = []
    for q in queries:
        latest = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.query_id == q.id)
            .order_by(WorkflowRun.started_at.desc())
            .first()
        )
        out.append(
            {
                "id": q.id,
                "text": q.text,
                "status": q.status,
                "created_at": q.created_at.isoformat(),
                "workflow_id": latest.id if latest else None,
            }
        )
    return out


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    sources = db.query(DataSource).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "type": s.type,
            "allowed": s.allowed,
            "license": s.license,
            "domain": s.domain,
            "last_updated": s.last_updated,
            "description": s.description,
        }
        for s in sources
    ]


@router.get("/queries/{query_id}")
def get_query(query_id: str, db: Session = Depends(get_db)):
    q = db.get(Query, query_id)
    if not q:
        raise HTTPException(404, "Query not found")
    latest_run = db.query(WorkflowRun).filter(WorkflowRun.query_id == q.id).order_by(WorkflowRun.started_at.desc()).first()
    return {
        "id": q.id,
        "project_id": q.project_id,
        "text": q.text,
        "status": q.status,
        "structured_intent": q.structured_intent,
        "created_at": q.created_at.isoformat(),
        "workflow_id": latest_run.id if latest_run else None,
    }
