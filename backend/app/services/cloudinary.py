"""Cloudinary service — asset & evidence layer (signed uploads, asset fetch).

Used for: user dataset uploads (direct, browser -> Cloudinary with a
server-generated signature), bundled demo assets, and evidence attachments.
Works in "local mode" when credentials are absent so the product never
hard-depends on network access.
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

import cloudinary
import cloudinary.api
import cloudinary.uploader
from fastapi import HTTPException

from ..config import settings

_LOCAL_ASSET_ROOT = Path("local_assets")


def configure() -> bool:
    """Configure the Cloudinary SDK. Returns True when credentials present."""
    if settings.cloudinary_configured:
        cloudinary.config(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
            secure=True,
        )
        return True
    return False


def configured() -> bool:
    return settings.cloudinary_configured


def sign_upload_params(folder: str = "datapilot/datasets") -> dict[str, Any]:
    """Server-signed params for a direct browser -> Cloudinary upload."""
    if not configured():
        raise HTTPException(
            status_code=503,
            detail="Cloudinary is not configured. Add CLOUDINARY_* keys to .env.",
        )
    timestamp = cloudinary.utils.now()
    params: dict[str, Any] = {
        "folder": folder,
        "timestamp": timestamp,
    }
    signature = cloudinary.utils.api_sign_request(params, settings.cloudinary_api_secret)
    return {
        "cloud_name": settings.cloudinary_cloud_name,
        "api_key": settings.cloudinary_api_key,
        "timestamp": timestamp,
        "folder": folder,
        "signature": signature,
        # Browser posts the file to this URL:
        "upload_url": f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/auto/upload",
    }


def fetch_asset_bytes(public_id: str, resource_type: str = "raw") -> bytes:
    """Download the stored asset bytes via Cloudinary's API."""
    if not configured():
        raise HTTPException(status_code=503, detail="Cloudinary is not configured.")
    url, _ = cloudinary.utils.cloudinary_url(
        public_id, resource_type=resource_type, type="upload", secure=True
    )
    import httpx

    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def upload_file(file_path: str | Path, public_id: str | None = None) -> dict[str, Any]:
    """Upload a local file (used for demo seeding when keys are configured)."""
    if not configured():
        raise HTTPException(status_code=503, detail="Cloudinary is not configured.")
    result = cloudinary.uploader.upload(
        str(file_path),
        public_id=public_id,
        resource_type="raw",
        folder="datapilot/datasets",
        overwrite=True,
    )
    return {
        "public_id": result.get("public_id"),
        "secure_url": result.get("secure_url"),
        "bytes": result.get("bytes"),
        "created_at": result.get("created_at"),
        "format": result.get("format"),
    }


def store_local_copy(file_path: str | Path) -> Path:
    """Persist a local copy of an uploaded/bundled file (local-mode fallback)."""
    _LOCAL_ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    dest = _LOCAL_ASSET_ROOT / f"{uuid.uuid4().hex[:8]}_{Path(file_path).name}"
    shutil.copyfile(file_path, dest)
    return dest


def local_mode() -> bool:
    return not configured()
