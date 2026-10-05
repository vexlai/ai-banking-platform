"""DuckDB-backed context lookup tools (INT-01).

Serves the six customer-context views over the read-only database at
``src.data.config.DUCKDB_PATH`` with the same signatures as ``src.tools.mocks``.
When duckdb, the database file, or a view is unavailable, each tool logs a
warning and returns the deterministic mock; pass ``strict=True`` to raise
``ContextToolError`` instead.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any, TypeVar

from contracts import (
    CaseRecord,
    Customer360,
    EvidenceBundle,
    Interaction,
    JourneyEvent,
    JourneySummary,
    RiskLevel,
    Transaction,
    TranscriptMatch,
)
from src.data.config import DUCKDB_PATH
from src.telemetry.logger import get_logger
from src.tools import mocks

try:
    import duckdb
except ImportError:
    duckdb = None  # type: ignore[assignment]

logger = get_logger(__name__)

CUSTOMER_360_VIEW = "customer_360_view"
RECENT_TRANSACTIONS_VIEW = "recent_transactions"
JOURNEY_SUMMARY_VIEW = "journey_summary"
INTERACTION_HISTORY_VIEW = "interaction_history"
SIMILAR_TRANSCRIPTS_VIEW = "similar_transcripts"
OPEN_CASES_VIEW = "open_cases"

_SQL_CUSTOMER_360 = (
    "SELECT customer_id, full_name, segment, country, products, credit_limit, "
    "currency, as_of FROM customer_360_view WHERE customer_id = ? LIMIT 1"
)
_SQL_RECENT_TRANSACTIONS = (
    "SELECT transaction_id, customer_id, amount, currency, merchant, status, "
    "fraud_score, occurred_at FROM recent_transactions WHERE customer_id = ? "
    "ORDER BY occurred_at DESC LIMIT 20"
)
_SQL_JOURNEY_SUMMARY = (
    "SELECT customer_id, session_id, window_hours, events, error_count, "
    "abandoned_forms, as_of FROM journey_summary WHERE customer_id = ? LIMIT 1"
)
_SQL_INTERACTION_HISTORY = (
    "SELECT interaction_id, channel, summary, occurred_at FROM interaction_history "
    "WHERE customer_id = ? ORDER BY occurred_at DESC LIMIT 10"
)
_SQL_SIMILAR_TRANSCRIPTS = (
    "SELECT transcript_id, similarity, summary FROM similar_transcripts "
    "WHERE customer_id = ? ORDER BY similarity DESC LIMIT 3"
)
_SQL_OPEN_CASES = (
    "SELECT case_id, status, severity, sla_breach, repeat_complaint, opened_at "
    "FROM open_cases WHERE customer_id = ? ORDER BY opened_at DESC"
)

ModelT = TypeVar("ModelT")


class ContextToolError(RuntimeError):
    """Structured failure raised in strict mode for an unusable serving view."""

    def __init__(self, tool: str, reason: str) -> None:
        super().__init__(f"Context tool {tool} failed: {reason}")
        self.tool = tool
        self.reason = reason


def _connect() -> Any:
    if duckdb is None:
        raise ContextToolError("duckdb", "duckdb is not installed")
    if not DUCKDB_PATH.exists():
        raise ContextToolError("duckdb", f"serving database not found at {DUCKDB_PATH}")
    try:
        return duckdb.connect(str(DUCKDB_PATH), read_only=True)
    except Exception as exc:
        raise ContextToolError(
            "duckdb", f"failed to open serving database: {exc}"
        ) from exc


def _view_exists(con: Any, name: str) -> bool:
    rows = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = ? LIMIT 1",
        [name],
    ).fetchall()
    return bool(rows)


def _fetch(
    con: Any, tool: str, view: str, sql: str, params: list[Any]
) -> list[dict[str, Any]]:
    try:
        if not _view_exists(con, view):
            raise ContextToolError(tool, f"serving view '{view}' not found")
        cursor = con.execute(sql, params)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    except ContextToolError:
        raise
    except Exception as exc:
        raise ContextToolError(tool, f"query failed: {exc}") from exc


def _rows(tool: str, view: str, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    con = _connect()
    try:
        return _fetch(con, tool, view, sql, params)
    finally:
        con.close()


def _fallback(
    tool: str, strict: bool, reason: str, produce: Callable[[], ModelT]
) -> ModelT:
    if strict:
        raise ContextToolError(tool, reason)
    logger.warning("Context tool %s falling back to mocks: %s", tool, reason)
    return produce()


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _as_products(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(item) for item in value]


def _customer_360(row: Mapping[str, Any]) -> Customer360:
    return Customer360(
        customer_id=str(row["customer_id"]),
        full_name=str(row["full_name"]),
        segment=str(row["segment"]),
        country=str(row["country"]),
        products=_as_products(row.get("products")),
        credit_limit=float(row["credit_limit"]),
        currency=str(row["currency"]),
        as_of=_as_datetime(row["as_of"]),
    )


def _transaction(row: dict[str, Any]) -> Transaction:
    raw_score = float(row.get("fraud_score") or 0.0)
    score = raw_score / 100.0 if raw_score > 1.0 else raw_score
    score = max(0.0, min(1.0, score))

    return Transaction(
        transaction_id=str(row.get("transaction_id", "")),
        customer_id=str(row.get("customer_id", "")),
        amount=float(row.get("amount") or 0.0),
        currency=str(row.get("currency") or "USD"),
        merchant=str(row.get("merchant") or row.get("merchant_name") or ""),
        status=str(row.get("status") or "posted"),
        occurred_at=_as_datetime(row["occurred_at"]),
        fraud_score=score,
    )


def _journey_summary(customer_id: str, row: Mapping[str, Any]) -> JourneySummary:
    events = [
        JourneyEvent(
            event_id=str(event["event_id"]),
            event_type=str(event["event_type"]),
            status=str(event["status"]),
            occurred_at=_as_datetime(event["occurred_at"]),
        )
        for event in (row.get("events") or [])
    ]
    return JourneySummary(
        customer_id=str(row.get("customer_id") or customer_id),
        session_id=str(row["session_id"]),
        window_hours=int(row.get("window_hours") or 24),
        events=events,
        error_count=int(row.get("error_count") or 0),
        abandoned_forms=int(row.get("abandoned_forms") or 0),
        as_of=_as_datetime(row["as_of"]),
    )


def _interaction(row: Mapping[str, Any]) -> Interaction:
    return Interaction(
        interaction_id=str(row["interaction_id"]),
        channel=str(row["channel"]),
        summary=str(row["summary"]),
        occurred_at=_as_datetime(row["occurred_at"]),
    )


def _transcript_match(row: Mapping[str, Any]) -> TranscriptMatch:
    similarity = float(row.get("similarity") or 0.0)
    return TranscriptMatch(
        transcript_id=str(row["transcript_id"]),
        similarity=min(1.0, max(0.0, similarity)),
        summary=str(row["summary"]),
    )


def _case_record(row: Mapping[str, Any]) -> CaseRecord:
    return CaseRecord(
        case_id=str(row["case_id"]),
        status=str(row["status"]),
        severity=RiskLevel(str(row["severity"])),
        sla_breach=bool(row.get("sla_breach") or False),
        repeat_complaint=bool(row.get("repeat_complaint") or False),
        opened_at=_as_datetime(row["opened_at"]),
    )


def get_context(customer_id: str, *, strict: bool = False) -> EvidenceBundle:
    return EvidenceBundle(
        customer_id=customer_id,
        customer_360=get_customer_360(customer_id, strict=strict),
        recent_transactions=get_recent_transactions(customer_id, strict=strict),
        journey_summary=get_journey_summary(customer_id, strict=strict),
        interaction_history=get_interaction_history(customer_id, strict=strict),
        similar_transcripts=get_similar_transcripts(customer_id, strict=strict),
        open_cases=get_open_cases(customer_id, strict=strict),
        retrieved_at=datetime.now(timezone.utc),
    )


def get_customer_360(customer_id: str, *, strict: bool = False) -> Customer360:
    tool = CUSTOMER_360_VIEW
    try:
        rows = _rows(tool, tool, _SQL_CUSTOMER_360, [customer_id])
        if not rows:
            raise ContextToolError(tool, f"no profile row for '{customer_id}'")
        return _customer_360(rows[0])
    except ContextToolError as exc:
        return _fallback(
            tool, strict, exc.reason, lambda: mocks.get_customer_360(customer_id)
        )
    except Exception as exc:  # noqa: BLE001
        return _fallback(
            tool,
            strict,
            f"invalid serving row: {exc}",
            lambda: mocks.get_customer_360(customer_id),
        )


def get_recent_transactions(
    customer_id: str, *, strict: bool = False
) -> list[Transaction]:
    tool = RECENT_TRANSACTIONS_VIEW
    try:
        rows = _rows(tool, tool, _SQL_RECENT_TRANSACTIONS, [customer_id])
        return [_transaction(row) for row in rows]
    except ContextToolError as exc:
        return _fallback(
            tool, strict, exc.reason, lambda: mocks.get_recent_transactions(customer_id)
        )
    except Exception as exc:  # noqa: BLE001
        return _fallback(
            tool,
            strict,
            f"invalid serving row: {exc}",
            lambda: mocks.get_recent_transactions(customer_id),
        )


def get_journey_summary(customer_id: str, *, strict: bool = False) -> JourneySummary:
    tool = JOURNEY_SUMMARY_VIEW
    try:
        rows = _rows(tool, tool, _SQL_JOURNEY_SUMMARY, [customer_id])
        if not rows:
            raise ContextToolError(tool, f"no journey row for '{customer_id}'")
        return _journey_summary(customer_id, rows[0])
    except ContextToolError as exc:
        return _fallback(
            tool, strict, exc.reason, lambda: mocks.get_journey_summary(customer_id)
        )
    except Exception as exc:  # noqa: BLE001
        return _fallback(
            tool,
            strict,
            f"invalid serving row: {exc}",
            lambda: mocks.get_journey_summary(customer_id),
        )


def get_interaction_history(
    customer_id: str, *, strict: bool = False
) -> list[Interaction]:
    tool = INTERACTION_HISTORY_VIEW
    try:
        rows = _rows(tool, tool, _SQL_INTERACTION_HISTORY, [customer_id])
        return [_interaction(row) for row in rows]
    except ContextToolError as exc:
        return _fallback(
            tool, strict, exc.reason, lambda: mocks.get_interaction_history(customer_id)
        )
    except Exception as exc:  # noqa: BLE001
        return _fallback(
            tool,
            strict,
            f"invalid serving row: {exc}",
            lambda: mocks.get_interaction_history(customer_id),
        )


def get_similar_transcripts(
    customer_id: str, *, strict: bool = False
) -> list[TranscriptMatch]:
    tool = SIMILAR_TRANSCRIPTS_VIEW
    try:
        rows = _rows(tool, tool, _SQL_SIMILAR_TRANSCRIPTS, [customer_id])
        return [_transcript_match(row) for row in rows]
    except ContextToolError as exc:
        return _fallback(
            tool,
            strict,
            exc.reason,
            lambda: mocks.get_similar_transcripts(customer_id),
        )
    except Exception as exc:  # noqa: BLE001
        return _fallback(
            tool,
            strict,
            f"invalid serving row: {exc}",
            lambda: mocks.get_similar_transcripts(customer_id),
        )


def get_open_cases(customer_id: str, *, strict: bool = False) -> list[CaseRecord]:
    tool = OPEN_CASES_VIEW
    try:
        rows = _rows(tool, tool, _SQL_OPEN_CASES, [customer_id])
        return [_case_record(row) for row in rows]
    except ContextToolError as exc:
        return _fallback(
            tool, strict, exc.reason, lambda: mocks.get_open_cases(customer_id)
        )
    except Exception as exc:  # noqa: BLE001
        return _fallback(
            tool,
            strict,
            f"invalid serving row: {exc}",
            lambda: mocks.get_open_cases(customer_id),
        )
