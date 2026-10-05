"""HTTP adapter for the orchestrator engine: one chat turn per request."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.config import resolve_use_mocks
from api.security import require_api_key
from contracts import ChatRequest, ChatResponse
from src.orchestrator.engine import OrchestratorEngine
from src.retrieval import vector_store
from src.telemetry.logger import get_logger
from src.tools.context_tools import ServiceUnavailableError

logger = get_logger(__name__)


def _select_engine(
    engine: OrchestratorEngine, use_mocks: bool | None
) -> OrchestratorEngine:
    """Reuses the injected engine unless the request overrides the serving mode."""
    resolved = resolve_use_mocks(use_mocks)
    if resolved == engine.use_mocks:
        return engine
    if resolved:
        return OrchestratorEngine(use_mocks=True, logger=engine.logger)
    return OrchestratorEngine(
        use_mocks=False, transcript_search=vector_store.search, logger=engine.logger
    )


def build_router(engine: OrchestratorEngine) -> APIRouter:
    router = APIRouter(
        prefix="/v1",
        tags=["chat"],
        dependencies=[Depends(require_api_key)],
    )

    @router.post("/chat", response_model=ChatResponse)
    def chat(
        request: ChatRequest, use_mocks: bool | None = Query(default=None)
    ) -> ChatResponse:
        active = _select_engine(engine, use_mocks)
        logger.info(
            "Chat turn received for customer: %s",
            request.customer_id,
            extra={"session_id": request.session_id, "use_mocks": active.use_mocks},
        )
        try:
            response = active.process_turn(request)
        except ServiceUnavailableError as exc:
            logger.error(
                "Serving data unavailable: %s",
                exc.reason,
                extra={"session_id": request.session_id},
            )
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Banking data engine unavailable",
            ) from exc
        logger.info(
            "Chat turn completed decision=%s status=%s trace_id=%s",
            response.decision,
            response.status,
            response.trace_id,
        )
        return response

    return router
