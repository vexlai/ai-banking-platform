"""FastAPI gateway: app wiring, CORS, and the health probe."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.dispute_fixture import from_environment
from api.routes import disputes
from contracts import HealthResponse
from src.cases.service import CaseService
from src.telemetry.logger import get_logger

API_VERSION = "0.1.0"
DEFAULT_CORS_ORIGINS = ("http://localhost:8501",)

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


def create_app(case_service: CaseService | None = None, *, include_legacy: bool = True):
    """Composition only. Dispute routes exclusively call the injected CaseService."""
    application = FastAPI(title="AI Banking Platform", version=API_VERSION)
    application.state.case_service = case_service
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-API-Key"],
        expose_headers=["X-Request-ID"],
    )
    application.include_router(disputes.router)
    if include_legacy:
        from api.routes import context, trace
        from api.routes.chat import build_router
        from src.orchestrator.engine import OrchestratorEngine

        application.include_router(
            build_router(OrchestratorEngine(use_mocks=USE_MOCKS))
        )
        application.include_router(context.router)
        application.include_router(trace.router)

    @application.get("/health", response_model=HealthResponse, tags=["ops"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=API_VERSION, mocks_enabled=USE_MOCKS)

    return application


app = create_app(
    from_environment(), include_legacy=_env_flag("ENABLE_LEGACY_API", default=True)
)
