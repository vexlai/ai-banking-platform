"""FastAPI gateway: app wiring, CORS, the health probe, and a boot readiness gate."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import duckdb
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import use_mocks_default
from api.routes import context, trace
from api.routes.chat import build_router
from contracts import HealthResponse
from src.data.config import DUCKDB_PATH, FAISS_INDEX_PATH
from src.orchestrator import llm
from src.orchestrator.engine import OrchestratorEngine
from src.retrieval import vector_store
from src.telemetry.logger import get_logger

API_VERSION = "0.1.0"
DEFAULT_CORS_ORIGINS = ("*",)
_TRUTHY = frozenset({"1", "true", "yes", "on"})

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

logger = get_logger(__name__)
USE_MOCKS = use_mocks_default()
LLM = llm.from_env()


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


def _serving_check_enabled() -> bool:
    raw = os.getenv("SKIP_SERVING_CHECK", "").strip().lower()
    return raw not in _TRUTHY and not USE_MOCKS


def _verify_serving_artifacts() -> None:
    if not _serving_check_enabled():
        logger.info("Serving artifact check skipped (mock mode or SKIP_SERVING_CHECK)")
        return
    try:
        if not DUCKDB_PATH.exists():
            raise RuntimeError(f"serving database missing: {DUCKDB_PATH}")
        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        try:
            con.execute("SELECT 1").fetchone()
        finally:
            con.close()
        if vector_store.load_index(FAISS_INDEX_PATH) is None:
            raise RuntimeError(f"FAISS index missing or unreadable: {FAISS_INDEX_PATH}")
    except Exception as exc:
        logger.critical("Serving layer unavailable; refusing to start: %s", exc)
        raise RuntimeError("Serving layer is not ready; refusing to start") from exc
    logger.info("Serving artifacts verified: %s and %s", DUCKDB_PATH, FAISS_INDEX_PATH)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _verify_serving_artifacts()
    yield


app = FastAPI(title="AI Banking Platform", version=API_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(
    build_router(
        OrchestratorEngine(
            use_mocks=USE_MOCKS,
            llm_client=LLM,
            transcript_search=None if USE_MOCKS else vector_store.search,
        )
    )
)
app.include_router(context.router)
app.include_router(trace.router)
logger.info(
    "API gateway configured: version=%s mocks_enabled=%s llm_enabled=%s",
    API_VERSION,
    USE_MOCKS,
    LLM is not None,
)


@app.get("/health", response_model=HealthResponse, tags=["ops"])
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=API_VERSION,
        mocks_enabled=USE_MOCKS,
        llm_enabled=LLM is not None,
        llm_model=getattr(LLM, "model", None),
    )
