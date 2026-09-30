"""DataPilot AI — FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .seed.bootstrap import bootstrap
from .services.events import event_bus


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    event_bus.set_loop(asyncio.get_running_loop())
    bootstrap()  # idempotent: tables, sources, demo datasets, Cloudinary seeding
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .api import datasets, projects, queries, workflows  # noqa: E402

api = settings.api_prefix
app.include_router(queries.router, prefix=api, tags=["queries"])
app.include_router(workflows.router, prefix=api, tags=["workflows"])
app.include_router(datasets.router, prefix=api, tags=["datasets"])
app.include_router(projects.router, prefix=api, tags=["projects"])


@app.get("/health")
def health():
    return {
        "status": "ok",
        "cloudinary": "configured" if settings.cloudinary_configured else "local-mode",
        "llm_enhancer": "enabled" if settings.openai_api_key else "own-engine",
    }
