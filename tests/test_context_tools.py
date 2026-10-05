"""Graceful-degradation tests for the DuckDB context tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from contracts import EvidenceBundle
from src.tools import context_tools, mocks


@pytest.fixture
def missing_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(context_tools, "DUCKDB_PATH", tmp_path / "missing.duckdb")


def test_customer_360_falls_back_to_mocks(missing_database: None) -> None:
    assert context_tools.get_customer_360("CUST_001") == mocks.get_customer_360(
        "CUST_001"
    )


def test_recent_transactions_fall_back_to_mocks(missing_database: None) -> None:
    assert context_tools.get_recent_transactions(
        "CUST_001"
    ) == mocks.get_recent_transactions("CUST_001")


def test_journey_summary_falls_back_to_mocks(missing_database: None) -> None:
    assert context_tools.get_journey_summary("CUST_002") == mocks.get_journey_summary(
        "CUST_002"
    )


def test_interaction_history_falls_back_to_mocks(missing_database: None) -> None:
    assert context_tools.get_interaction_history(
        "CUST_002"
    ) == mocks.get_interaction_history("CUST_002")


def test_similar_transcripts_fall_back_to_mocks(missing_database: None) -> None:
    assert context_tools.get_similar_transcripts(
        "CUST_003"
    ) == mocks.get_similar_transcripts("CUST_003")


def test_open_cases_fall_back_to_mocks(missing_database: None) -> None:
    assert context_tools.get_open_cases("CUST_002") == mocks.get_open_cases("CUST_002")


def test_get_context_falls_back_to_mock_bundle(missing_database: None) -> None:
    bundle = context_tools.get_context("CUST_002")
    expected = mocks.get_context("CUST_002")

    assert isinstance(bundle, EvidenceBundle)
    assert bundle.customer_360 == expected.customer_360
    assert bundle.recent_transactions == expected.recent_transactions
    assert bundle.journey_summary == expected.journey_summary
    assert bundle.open_cases == expected.open_cases
    assert bundle.retrieved_at.tzinfo is not None


def test_strict_mode_raises_structured_error(missing_database: None) -> None:
    with pytest.raises(context_tools.ContextToolError) as error:
        context_tools.get_customer_360("CUST_001", strict=True)

    assert error.value.tool == "customer_360_view"
    assert "not found" in error.value.reason


def test_live_view_is_queried(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    duckdb = pytest.importorskip("duckdb")
    database = tmp_path / "serving.duckdb"
    con = duckdb.connect(str(database))
    con.execute(
        "CREATE TABLE customer_360_view(customer_id VARCHAR, full_name VARCHAR, "
        "segment VARCHAR, country VARCHAR, products VARCHAR[], credit_limit DOUBLE, "
        "currency VARCHAR, as_of TIMESTAMP)"
    )
    con.execute(
        "INSERT INTO customer_360_view VALUES "
        "('CUST_001', 'Maria Gonzalez', 'retail', 'MX', "
        "['checking_account', 'credit_card'], 25000.0, 'MXN', "
        "TIMESTAMP '2026-06-17 12:00:00')"
    )
    con.close()
    monkeypatch.setattr(context_tools, "DUCKDB_PATH", database)

    profile = context_tools.get_customer_360("CUST_001")

    assert profile.full_name == "Maria Gonzalez"
    assert profile.products == ["checking_account", "credit_card"]
