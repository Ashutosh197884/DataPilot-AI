"""Source registry — the AI may only use sources registered here as allowed."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import DataSource

# Seeded registry entries. Type 'api' sources are served through bundled
# snapshots fetched via the same tool interface (see agents/tools.py), so the
# provenance chain is real while the demo stays network-independent.
SEED_SOURCES: list[dict] = [
    {
        "id": "agri_snap_india",
        "name": "India Agriculture Snapshot API (bundled)",
        "type": "api",
        "base_url": "https://api.data.gov.in/catalog/...",
        "description": "District-level rainfall and crop production series (bundled snapshot of permitted open-data API).",
        "allowed": True,
        "license": "Government Open Data License - India",
        "domain": "agriculture",
        "last_updated": "2026-09-18",
    },
    {
        "id": "ev_vahan_snapshot",
        "name": "VAHAN EV Registrations Snapshot (bundled)",
        "type": "api",
        "base_url": "https://vahan.parivahan.gov.in/",
        "description": "EV sales/registration by manufacturer and year (bundled snapshot of public registry data).",
        "allowed": True,
        "license": "Public dataset",
        "domain": "transport",
        "last_updated": "2026-09-20",
    },
    {
        "id": "user_upload",
        "name": "User Uploads (Cloudinary assets)",
        "type": "upload",
        "base_url": "",
        "description": "Datasets uploaded by the user and managed as Cloudinary assets.",
        "allowed": True,
        "license": "User-provided",
        "domain": "any",
        "last_updated": "",
    },
]


def seed_sources(db: Session) -> None:
    for spec in SEED_SOURCES:
        if db.get(DataSource, spec["id"]) is None:
            db.add(DataSource(**spec))
    db.commit()


def allowed_sources(db: Session) -> list[DataSource]:
    return db.query(DataSource).filter(DataSource.allowed.is_(True)).all()
