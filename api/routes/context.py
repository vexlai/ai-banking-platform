"""HTTP adapter exposing the retrieved customer evidence bundle."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.config import resolve_use_mocks
from api.security import require_api_key
from contracts import EvidenceBundle
from src.telemetry.logger import get_logger
from src.tools import context_tools, mocks
from src.tools.context_tools import CustomerNotFoundError, ServiceUnavailableError

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
    try:
        if resolve_use_mocks(use_mocks):
            logger.info("Context requested for customer: %s", customer_id)
            return mocks.get_context(customer_id)
        logger.info("Live context requested for customer: %s", customer_id)
        return context_tools.get_context(customer_id)
    except CustomerNotFoundError as exc:
        logger.warning("Context not found for customer: %s", customer_id)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Unknown customer: {customer_id}",
        ) from exc
    except ServiceUnavailableError as exc:
        logger.error("Serving data unavailable: %s", exc.reason)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banking data engine unavailable",
        ) from exc
