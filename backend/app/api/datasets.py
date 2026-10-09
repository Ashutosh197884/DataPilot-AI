"""Dataset APIs — Cloudinary signed direct upload + registration + manager views."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..engines import validation as va
from ..models import Dataset, Project, ValidationRun, get_db
from ..services import cloudinary as cl

router = APIRouter()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}


@router.get("/datasets/upload-signature")
def upload_signature():
    """Server-signed params for direct browser -> Cloudinary upload (spec §34)."""
    return cl.sign_upload_params(folder="datapilot/datasets")


@router.post("/datasets/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    name: str = Form(None),
    db: Session = Depends(get_db),
):
    """Multipart upload endpoint. Stores to Cloudinary when configured,
    otherwise keeps a local managed copy so uploads always work offline."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type {ext}. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 25 MB)")

    # File validation before processing (spec §50)
    tmp = Path(tempfile.gettempdir()) / f"dp_{project_id}_{file.filename}"
    tmp.write_bytes(raw)

    public_id = None
    secure_url = None
    if cl.configured():
        try:
            result = cl.upload_file(tmp, public_id=None)
            public_id = result["public_id"]
            secure_url = result["secure_url"]
            local_copy = cl.store_local_copy(tmp)
        except Exception:
            local_copy = cl.store_local_copy(tmp)
    else:
        local_copy = cl.store_local_copy(tmp)

    ds = _register_dataset(db, project_id, name or file.filename, str(local_copy), ext.lstrip("."), public_id, secure_url, source_id="user_upload")
    return {
        "id": ds.id,
        "name": ds.name,
        "records": ds.record_count,
        "quality_score": ds.quality_score,
        "schema": ds.schema_json,
        "cloudinary_public_id": ds.cloudinary_public_id,
        "cloudinary_url": ds.cloudinary_url,
        "cloudinary_configured": cl.configured(),
    }


@router.get("/datasets")
def list_datasets(project_id: str, db: Session = Depends(get_db)):
    datasets = db.query(Dataset).filter(Dataset.project_id == project_id).order_by(Dataset.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "source_type": d.source_type,
            "file_type": d.file_type,
            "records": d.record_count,
            "quality_score": d.quality_score,
            "coverage": d.coverage_period,
            "cloudinary_public_id": d.cloudinary_public_id,
            "cloudinary_url": d.cloudinary_url,
            "columns": [c.get("name") for c in (d.schema_json or {}).get("columns", [])],
            "created_at": d.created_at.isoformat(),
        }
        for d in datasets
    ]


@router.get("/datasets/{dataset_id}")
def dataset_detail(dataset_id: str, db: Session = Depends(get_db)):
    d = db.get(Dataset, dataset_id)
    if not d:
        raise HTTPException(404, "Dataset not found")
    vr = db.query(ValidationRun).filter(ValidationRun.dataset_id == d.id).order_by(ValidationRun.created_at.desc()).first()

    # Data preview
    preview_rows: list[dict] = []
    columns: list[dict] = []
    if d.local_path and Path(d.local_path).exists():
        try:
            df = pd.read_csv(d.local_path) if d.file_type == "csv" else pd.read_excel(d.local_path)
            columns = [
                {"name": c, "type": ("numeric" if pd.api.types.is_numeric_dtype(df[c]) else "string")}
                for c in df.columns
            ]
            preview_rows = df.head(10).fillna("").to_dict(orient="records")
        except Exception:
            pass

    return {
        "id": d.id,
        "name": d.name,
        "source_type": d.source_type,
        "records": d.record_count,
        "quality_score": d.quality_score or (vr.quality_score if vr else None),
        "coverage": d.coverage_period,
        "retrieved_at": d.retrieved_at.isoformat() if d.retrieved_at else None,
        "cloudinary_public_id": d.cloudinary_public_id,
        "cloudinary_url": d.cloudinary_url,
        "schema": {"columns": columns},
        "preview": preview_rows,
        "validation": {
            "completeness": vr.completeness if vr else None,
            "duplicates": vr.duplicate_count if vr else None,
            "invalid": vr.invalid_count if vr else None,
            "schema_valid": vr.schema_valid if vr else None,
        } if vr else None,
    }


@router.get("/datasets/{dataset_id}/download")
def download_dataset(dataset_id: str, db: Session = Depends(get_db)):
    d = db.get(Dataset, dataset_id)
    if not d or not d.local_path or not Path(d.local_path).exists():
        raise HTTPException(404, "Dataset file not available")
    return FileResponse(d.local_path, filename=f"{d.name}.{d.file_type}")


def _register_dataset(
    db: Session, project_id: str, name: str, local_path: str, file_type: str,
    public_id: str | None, secure_url: str | None, source_id: str = "user_upload",
) -> Dataset:
    """Parse, infer schema, validate, persist dataset metadata."""
    if file_type in {"xlsx", "xls"}:
        df = pd.read_excel(local_path)
    elif file_type == "json":
        df = pd.read_json(local_path)
    else:
        df = pd.read_csv(local_path)

    schema = {
        "columns": [
            {"name": c, "type": ("numeric" if pd.api.types.is_numeric_dtype(df[c]) else "string")}
            for c in df.columns
        ]
    }
    numeric_cols = [c for c, t in [(c["name"], c["type"]) for c in schema["columns"]] if t == "numeric"]

    report = va.validate(df, non_negative=numeric_cols, dataset_name=name)
    ds = Dataset(
        project_id=project_id,
        name=name,
        source_type="upload",
        source_id=source_id,
        cloudinary_public_id=public_id,
        cloudinary_url=secure_url,
        file_type=file_type,
        local_path=local_path,
        schema_json=schema,
        record_count=int(len(df)),
        quality_score=report["quality_score"],
    )
    db.add(ds)
    db.flush()
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
    return ds
