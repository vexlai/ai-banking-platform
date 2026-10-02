"""HTTP adapter exposing buffered telemetry records for one request trace."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from src.telemetry.logger import get_logger, get_trace

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["trace"])


@router.get("/trace/{request_id}")
def request_trace(request_id: str) -> dict[str, Any]:
    records = get_trace(request_id)
    if not records:
        logger.warning("Trace not found for request: %s", request_id)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown trace id: {request_id}"
        )
    logger.info("Trace served for request: %s records=%s", request_id, len(records))
    return {"request_id": request_id, "records": records}
