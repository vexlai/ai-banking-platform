"""HTTP adapter for the orchestrator engine: one chat turn per request."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.orchestrator.engine import OrchestratorEngine
from src.telemetry.logger import get_logger
from src.tools.schemas import ChatRequest, ChatResponse

logger = get_logger(__name__)


def build_router(engine: OrchestratorEngine) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["chat"])

    @router.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        logger.info(
            "Chat turn received for customer: %s",
            request.customer_id,
            extra={"session_id": request.session_id},
        )
        try:
            response = engine.process_turn(request)
        except NotImplementedError as exc:
            logger.error(
                "Chat turn unavailable because real context tools are not wired: %s",
                exc,
                extra={"session_id": request.session_id},
            )
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
        logger.info(
            "Chat turn completed decision=%s trace_id=%s",
            response.decision,
            response.trace_id,
        )
        return response

    return router
