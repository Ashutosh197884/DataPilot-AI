"""SQLAlchemy models — the system of record (metadata, state, provenance).

Cloudinary holds the actual assets; this DB holds relationships and state.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from ..config import settings


class Base(DeclarativeBase):
    pass


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    queries: Mapped[list[Query]] = relationship(back_populates="project")
    datasets: Mapped[list[Dataset]] = relationship(back_populates="project")


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    text: Mapped[str] = mapped_column(Text)
    structured_intent: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="PLANNING")  # PLANNING/RUNNING/COMPLETED/FAILED/NEEDS_INPUT
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped[Project] = relationship(back_populates="queries")
    workflow_runs: Mapped[list[WorkflowRun]] = relationship(back_populates="query")


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(24))  # api | upload | database
    base_url: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    license: Mapped[str] = mapped_column(String(200), default="")
    domain: Mapped[str] = mapped_column(String(80), default="")
    last_updated: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(24), default="upload")  # upload | api | demo
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    cloudinary_public_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    cloudinary_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_type: Mapped[str] = mapped_column(String(16), default="csv")
    local_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    schema_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage_period: Mapped[str | None] = mapped_column(String(80), nullable=True)
    retrieved_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped[Project] = relationship(back_populates="datasets")
    source: Mapped[DataSource | None] = relationship()


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_id)
    query_id: Mapped[str] = mapped_column(ForeignKey("queries.id"))
    status: Mapped[str] = mapped_column(String(24), default="RUNNING")  # RUNNING/COMPLETED/FAILED
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    query: Mapped[Query] = relationship(back_populates="workflow_runs")
    steps: Mapped[list[WorkflowStep]] = relationship(
        back_populates="workflow", order_by="WorkflowStep.step_number", cascade="all, delete-orphan"
    )


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_id)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"))
    step_number: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(String(48))
    title: Mapped[str] = mapped_column(String(200), default="")
    input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="PENDING")  # PENDING/RUNNING/COMPLETED/FAILED
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow: Mapped[WorkflowRun] = relationship(back_populates="steps")


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    workflow_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_runs.id"), nullable=True)
    completeness: Mapped[float] = mapped_column(Float, default=0.0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0)
    schema_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    validation_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    dataset: Mapped[Dataset] = relationship()


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_id)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"))
    analysis_type: Mapped[str] = mapped_column(String(48))
    result: Mapped[dict] = mapped_column(JSON)
    calculation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_id)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    calculation: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    kind: Mapped[str] = mapped_column(String(24), default="descriptive")  # descriptive|correlational|limitation
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_id)
    insight_id: Mapped[str] = mapped_column(ForeignKey("insights.id"))
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    workflow_step_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_steps.id"), nullable=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    transformations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    calculation: Mapped[str] = mapped_column(Text, default="")
    source_reference: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    insight: Mapped[Insight] = relationship()
    dataset: Mapped[Dataset | None] = relationship()
    source: Mapped[DataSource | None] = relationship()


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
