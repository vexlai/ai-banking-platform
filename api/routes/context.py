"""HTTP adapter exposing the retrieved customer evidence bundle."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.config import resolve_use_mocks
from api.security import require_api_key
from contracts import EvidenceBundle
from src.telemetry.logger import get_logger
from src.tools import context_tools, mocks

logger = get_logger(__name__)

router = APIRouter(
    prefix="/v1",
    tags=["context"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/customers/{customer_id}/context", response_model=EvidenceBundle)
def customer_context(
    customer_id: str, use_mocks: bool | None = Query(default=None)
) -> EvidenceBundle:
    if resolve_use_mocks(use_mocks):
        logger.info("Context requested for customer: %s", customer_id)
        return mocks.get_context(customer_id)
    logger.info("Live context requested for customer: %s", customer_id)
    return context_tools.get_context(customer_id)
