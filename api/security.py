"""X-API-Key authentication guard for the protected gateway routes.

Opt-in: enforced only when `API_KEY_REQUIRED` is truthy. The key authenticates
the caller (service-to-service / UI), not the end customer, so it is a coarse
edge gate and not a substitute for per-customer identity.
"""

from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.telemetry.logger import get_logger

logger = get_logger(__name__)

API_KEY_HEADER = "X-API-Key"
API_KEY_ENV = "API_KEY"
API_KEY_REQUIRED_ENV = "API_KEY_REQUIRED"
_TRUTHY = frozenset({"1", "true", "yes", "on"})

_api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def _api_key_required() -> bool:
    raw = os.getenv(API_KEY_REQUIRED_ENV, "")
    return raw.strip().lower() in _TRUTHY


def _verify_api_key(api_key: str | None) -> None:
    if not _api_key_required():
        return
    expected = os.getenv(API_KEY_ENV)
    if not expected:
        logger.error("API_KEY_REQUIRED is enabled but API_KEY is not configured")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server API key is not configured",
        )
    if not api_key or not secrets.compare_digest(api_key.encode(), expected.encode()):
        logger.warning("Rejected request: invalid or missing %s", API_KEY_HEADER)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )


def require_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    """FastAPI dependency: rejects when the key is required and absent/invalid."""
    _verify_api_key(api_key)
