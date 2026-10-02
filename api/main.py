"""FastAPI gateway: app wiring, CORS, and the health probe."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.chat import build_router
from src.orchestrator.engine import OrchestratorEngine
from src.telemetry.logger import get_logger
from src.tools.schemas import HealthResponse

API_VERSION = "0.1.0"
DEFAULT_CORS_ORIGINS = ("*",)

logger = get_logger(__name__)


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


USE_MOCKS = _env_flag("USE_MOCKS", default=True)

app = FastAPI(title="AI Banking Platform", version=API_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(build_router(OrchestratorEngine(use_mocks=USE_MOCKS)))
logger.info(
    "API gateway configured: version=%s mocks_enabled=%s", API_VERSION, USE_MOCKS
)


@app.get("/health", response_model=HealthResponse, tags=["ops"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=API_VERSION, mocks_enabled=USE_MOCKS)
