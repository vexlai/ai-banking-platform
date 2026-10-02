"""Structured JSON logging and execution latency tracing (stdlib logging only)."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Self

LOGGER_NAME = "ai_banking"
DEFAULT_LEVEL = logging.INFO

_LOG_RECORD_FIELDS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
    }
)


class JsonFormatter(logging.Formatter):
    """One JSON object per record; `extra` fields are flattened to the top level."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in _LOG_RECORD_FIELDS
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def get_logger(
    name: str = LOGGER_NAME, *, level: int = DEFAULT_LEVEL
) -> logging.Logger:
    """Returns a stdout logger carrying exactly one JSON handler (idempotent)."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    if not any(
        isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers
    ):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger


def new_trace_id() -> str:
    """Opaque id correlating every line emitted for one request."""
    return uuid.uuid4().hex


class LatencyTimer:
    """Monotonic stopwatch; `elapsed_ms` freezes when the `with` block exits."""

    __slots__ = ("_elapsed_ms", "_started_at")

    def __init__(self) -> None:
        self._started_at = time.perf_counter()
        self._elapsed_ms: float | None = None

    @property
    def elapsed_ms(self) -> float:
        return self._elapsed_ms if self._elapsed_ms is not None else self._read_ms()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self._elapsed_ms = self._read_ms()

    def _read_ms(self) -> float:
        return round((time.perf_counter() - self._started_at) * 1000, 3)
