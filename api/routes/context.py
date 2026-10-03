"""HTTP adapter exposing the retrieved customer evidence bundle."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.security import require_api_key
from contracts import EvidenceBundle
from src.telemetry.logger import get_logger
from src.tools import mocks

logger = get_logger(__name__)

router = APIRouter(
    prefix="/v1",
    tags=["context"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/customers/{customer_id}/context", response_model=EvidenceBundle)
def customer_context(customer_id: str) -> EvidenceBundle:
    logger.info("Context requested for customer: %s", customer_id)
    return mocks.get_context(customer_id)
