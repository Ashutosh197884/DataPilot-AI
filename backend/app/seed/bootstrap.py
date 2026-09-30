"""Startup bootstrap — idempotent: DB tables, source registry, default project,
demo datasets (with bundled CSVs as assets, uploaded to Cloudinary if keys exist).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pandas as pd

from ..config import settings
from ..engines import validation as va
from ..models import Dataset, Project, SessionLocal, ValidationRun, init_db
from ..services import cloudinary as cl
from . import demo_data


def bootstrap() -> None:
    init_db()
    db = SessionLocal()
    try:
        _ensure_project(db)
        _seed_sources(db)
        _ensure_demo_datasets(db)
    finally:
        db.close()
    # Cloudinary demo seeding (optional; never blocks startup)
    if cl.configured():
        try:
            _upload_demo_assets_to_cloudinary()
        except Exception as e:  # pragma: no cover
            print(f"[bootstrap] Cloudinary demo seeding skipped: {e}")


def _ensure_project(db) -> None:
    if not db.query(Project).first():
        db.add(Project(name="Demo Project", description="Default workspace for DataPilot AI demo"))


def _seed_sources(db) -> None:
    from ..services.source_registry import seed_sources

    seed_sources(db)


def _ensure_demo_datasets(db) -> None:
    project = db.query(Project).first()
    for fname, meta in [
        (
            "haryana_rainfall_wheat.csv",
            {
                "name": "Haryana Rainfall vs Wheat Production 2020–2025",
                "source_id": "agri_snap_india",
                "coverage": "2020–2025",
            },
        ),
        ("india_ev_sales.csv", {"name": "India EV Sales by Manufacturer 2022–2025", "source_id": "ev_vahan_snapshot", "coverage": "2022–2025"}),
    ]:
        path = demo_data.generate_rainfall_wheat if fname.startswith("haryana") else demo_data.generate_ev_sales
        csv_path = path()
        content = csv_path.read_bytes()
        digest = hashlib.md5(content).hexdigest()[:8]

        existing = (
            db.query(Dataset)
            .filter(Dataset.project_id == project.id, Dataset.name == meta["name"])
            .first()
        )
        if existing:
            # refresh local_path if demo file changed between runs
            if existing.local_path != str(csv_path):
                existing.local_path = str(csv_path)
                db.commit()
            continue

        row_count = sum(1 for _ in csv_path.open(encoding="utf-8")) - 1
        schema = demo_data.SCHEMAS[fname]
        ds = Dataset(
            project_id=project.id,
            name=meta["name"],
            source_type="api" if meta["source_id"] != "user_upload" else "upload",
            source_id=meta["source_id"],
            file_type="csv",
            local_path=str(csv_path),
            schema_json=schema,
            record_count=row_count,
            coverage_period=meta["coverage"],
        )
        db.add(ds)
        db.flush()
        # Seed-time validation so the manager shows quality from the start
        df = pd.read_csv(csv_path)
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        report = va.validate(df, non_negative=numeric_cols, dataset_name=meta["name"])
        ds.quality_score = report["quality_score"]
        db.add(
            ValidationRun(
                dataset_id=ds.id,
                completeness=report["completeness"],
                duplicate_count=report["duplicate_count"],
                invalid_count=report["invalid_count"],
                schema_valid=report["schema_valid"],
                quality_score=report["quality_score"],
                validation_details=report,
            )
        )
    db.commit()


def _upload_demo_assets_to_cloudinary() -> None:
    """Upload bundled demo CSVs as Cloudinary assets; link public IDs to datasets."""
    db = SessionLocal()
    try:
        project = db.query(Project).first()
        pairs = [
            ("haryana_rainfall_wheat.csv", "Haryana Rainfall vs Wheat Production 2020–2025", "haryana_rainfall_wheat"),
            ("india_ev_sales.csv", "India EV Sales by Manufacturer 2022–2025", "india_ev_sales"),
        ]
        for fname, ds_name, pid in pairs:
            csv_path = DEMO_PATH(fname)
            ds = db.query(Dataset).filter(Dataset.project_id == project.id, Dataset.name == ds_name).first()
            if not ds or ds.cloudinary_public_id:
                continue
            result = cl.upload_file(csv_path, public_id=f"datapilot/demo/{pid}")
            ds.cloudinary_public_id = result["public_id"]
            ds.cloudinary_url = result["secure_url"]
            db.commit()
    finally:
        db.close()


def DEMO_PATH(fname: str) -> Path:
    return Path(__file__).parent / "demo_data" / fname
