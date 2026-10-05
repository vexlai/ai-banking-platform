"""Strict-mode behavior for the DuckDB context tools (no silent fallback)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.tools import context_tools, mocks


@pytest.fixture
def missing_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(context_tools, "DUCKDB_PATH", tmp_path / "missing.duckdb")


@pytest.fixture
def serving_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    duckdb = pytest.importorskip("duckdb")
    database = tmp_path / "serving.duckdb"
    con = duckdb.connect(str(database))
    con.execute(
        "CREATE TABLE customer_360_view(customer_id VARCHAR, full_name VARCHAR, "
        "segment VARCHAR, country VARCHAR, products VARCHAR[], credit_limit DOUBLE, "
        "currency VARCHAR, as_of TIMESTAMP)"
    )
    con.execute(
        "INSERT INTO customer_360_view VALUES ('CUST_001', 'Maria Gonzalez', 'retail', "
        "'MX', ['checking_account'], 25000.0, 'MXN', TIMESTAMP '2026-06-17 12:00:00')"
    )
    con.execute(
        "CREATE TABLE recent_transactions(transaction_id VARCHAR, customer_id VARCHAR, "
        "amount DOUBLE, currency VARCHAR, merchant VARCHAR, status VARCHAR, "
        "fraud_score DOUBLE, occurred_at TIMESTAMP)"
    )
    con.execute(
        "CREATE TABLE journey_summary(customer_id VARCHAR, session_id VARCHAR, "
        "window_hours INTEGER, events VARCHAR[], error_count INTEGER, "
        "abandoned_forms INTEGER, as_of TIMESTAMP)"
    )
    con.execute(
        "CREATE TABLE interaction_history(interaction_id VARCHAR, customer_id VARCHAR, "
        "channel VARCHAR, summary VARCHAR, occurred_at TIMESTAMP)"
    )
    con.execute(
        "CREATE TABLE similar_transcripts(transcript_id VARCHAR, customer_id VARCHAR, "
        "similarity DOUBLE, summary VARCHAR)"
    )
    con.execute(
        "CREATE TABLE open_cases(case_id VARCHAR, customer_id VARCHAR, status VARCHAR, "
        "severity VARCHAR, sla_breach BOOLEAN, repeat_complaint BOOLEAN, "
        "opened_at TIMESTAMP)"
    )
    con.close()
    monkeypatch.setattr(context_tools, "DUCKDB_PATH", database)
    return database


def test_missing_database_raises_service_unavailable(missing_database: None) -> None:
    with pytest.raises(context_tools.ServiceUnavailableError) as error:
        context_tools.get_customer_360("CUST_001")

    assert error.value.tool == "duckdb"
    assert "not found" in error.value.reason


def test_strict_false_opts_into_mocks(missing_database: None) -> None:
    assert context_tools.get_customer_360(
        "CUST_001", strict=False
    ) == mocks.get_customer_360("CUST_001")


def test_unknown_customer_raises_not_found(serving_database: Path) -> None:
    with pytest.raises(context_tools.CustomerNotFoundError):
        context_tools.get_customer_360("NON_EXISTENT_ID")


def test_known_customer_returns_profile(serving_database: Path) -> None:
    assert context_tools.get_customer_360("CUST_001").full_name == "Maria Gonzalez"


def test_valid_customer_empty_transactions_returns_empty_list(
    serving_database: Path,
) -> None:
    assert context_tools.get_recent_transactions("CUST_001") == []


def test_valid_customer_empty_journey_returns_summary(serving_database: Path) -> None:
    journey = context_tools.get_journey_summary("CUST_001")

    assert journey.session_id == ""
    assert journey.error_count == 0


def test_get_context_valid_empty(serving_database: Path) -> None:
    bundle = context_tools.get_context("CUST_001")

    assert bundle.customer_360.full_name == "Maria Gonzalez"
    assert bundle.recent_transactions == []
    assert bundle.retrieved_at.tzinfo is not None
