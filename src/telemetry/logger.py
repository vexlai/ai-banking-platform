"""Structured JSON logging and execution latency tracing (stdlib logging only)."""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
import uuid
from collections import OrderedDict, deque
from datetime import datetime, timezone
from typing import Any, Self

LOGGER_NAME = "ai_banking"
DEFAULT_LEVEL = logging.INFO
TRACE_ID_FIELD = "trace_id"
DEFAULT_TRACE_CAPACITY = 200
DEFAULT_MAX_TRACES = 256

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


def _serialize_record(record: logging.LogRecord) -> dict[str, Any]:
    """JSON-safe payload for one record; `extra` fields are flattened to the top level."""
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
    return payload


class TraceBufferHandler(logging.Handler):
    """Bounded in-memory store of recent records indexed by `trace_id`.

    Tracks at most `max_traces` request ids (least-recently-written evicted first)
    and at most `capacity` records per trace. Thread-safe for the FastAPI pool.
    """

    def __init__(
        self,
        *,
        capacity: int = DEFAULT_TRACE_CAPACITY,
        max_traces: int = DEFAULT_MAX_TRACES,
    ) -> None:
        super().__init__()
        self._capacity = capacity
        self._max_traces = max_traces
        self._lock = threading.Lock()
        self._traces: OrderedDict[str, deque[dict[str, Any]]] = OrderedDict()

    def emit(self, record: logging.LogRecord) -> None:
        trace_id = getattr(record, TRACE_ID_FIELD, None)
        if not trace_id:
            return
        try:
            payload = _serialize_record(record)
        except (TypeError, ValueError):
            self.handleError(record)
            return
        with self._lock:
            bucket = self._traces.get(trace_id)
            if bucket is None:
                bucket = deque(maxlen=self._capacity)
                self._traces[trace_id] = bucket
            bucket.append(payload)
            self._traces.move_to_end(trace_id)
            while len(self._traces) > self._max_traces:
                self._traces.popitem(last=False)

    def records(self, trace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            bucket = self._traces.get(trace_id)
            return list(bucket) if bucket else []


_TRACE_BUFFER = TraceBufferHandler()


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
    if not any(
        isinstance(buffered, TraceBufferHandler) for buffered in logger.handlers
    ):
        logger.addHandler(_TRACE_BUFFER)
    return logger


def new_trace_id() -> str:
    """Opaque id correlating every line emitted for one request."""
    return uuid.uuid4().hex


def get_trace(request_id: str) -> list[dict[str, Any]]:
    """Buffered records captured for one trace; empty when the id is unknown."""
    return _TRACE_BUFFER.records(request_id)


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
