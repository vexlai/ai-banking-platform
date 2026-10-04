"""Shared observable port tests; synthetic edge cases, no changes to frozen fixtures."""

from datetime import timedelta

import duckdb
import pytest
from test_case_runtime import NOW, transaction

from api.main import create_app
from contracts.disputes import Intake, Principal, Search, Selection, State
from src.cases.dataset_tools import FORMAT, TIME_POLICY, TX_COLUMNS, DatasetTools
from src.cases.service import CaseService
from src.cases.store import CaseStore, Rejected
from src.cases.tools import FixtureTools


def write_projection(path, records):
    con = duckdb.connect(str(path))
    con.execute("""
        CREATE TABLE transactions(
            transaction_id VARCHAR PRIMARY KEY, customer_id VARCHAR NOT NULL,
            product_id VARCHAR NOT NULL, transaction_date TIMESTAMPTZ NOT NULL,
            amount DECIMAL(24,6) NOT NULL, currency VARCHAR NOT NULL,
            transaction_type VARCHAR NOT NULL, channel VARCHAR NOT NULL,
            transaction_status VARCHAR NOT NULL, merchant_name VARCHAR,
            source_ref VARCHAR NOT NULL, available_at TIMESTAMPTZ)
    """)
    con.executemany(
        "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [[getattr(r, k) for k in TX_COLUMNS] for r in records],
    )
    con.execute(
        "CREATE TABLE products(product_id VARCHAR PRIMARY KEY,customer_id VARCHAR)"
    )
    con.execute(
        "INSERT INTO products VALUES ('product-a','customer-a'),('product-b','customer-b')"
    )
    con.execute("CREATE TABLE customers(customer_id VARCHAR PRIMARY KEY)")
    con.execute("INSERT INTO customers VALUES ('customer-a'),('customer-b')")
    con.execute("CREATE INDEX transactions_customer_idx ON transactions(customer_id)")
    con.execute(
        "CREATE TABLE serving_meta(format VARCHAR, source_sha256 VARCHAR,time_policy VARCHAR, observation_start TIMESTAMPTZ)"
    )
    con.execute(
        "INSERT INTO serving_meta VALUES (?,?,?,?)",
        [FORMAT, "test-source", TIME_POLICY, NOW - timedelta(days=60)],
    )
    con.close()


@pytest.fixture(params=["fixture", "dataset"])
def backend(request, tmp_path):
    records = [
        transaction("target", transaction_date=NOW, amount="10", merchant_name=None),
        transaction("same-time", transaction_date=NOW, amount="200"),
        transaction(
            "start", transaction_date=NOW - timedelta(days=30), amount="0.000001"
        ),
        transaction(
            "prior",
            transaction_date=NOW - timedelta(days=1),
            amount="0.000002",
            merchant_name="Shop",
        ),
        transaction(
            "outside",
            transaction_date=NOW - timedelta(days=30, microseconds=1),
            amount="800",
        ),
        transaction("future", transaction_date=NOW + timedelta(microseconds=1)),
        transaction("foreign", customer_id="customer-b", product_id="product-b"),
        transaction(
            "cop",
            transaction_date=NOW - timedelta(days=2),
            amount="100",
            currency="COP",
        ),
        transaction(
            "late",
            transaction_date=NOW - timedelta(hours=1),
            available_at=NOW + timedelta(seconds=1),
        ),
        transaction(
            "known-at-target",
            transaction_date=NOW - timedelta(hours=1),
            available_at=NOW,
        ),
    ]
    if request.param == "fixture":
        yield FixtureTools(
            records,
            {"product-a": "customer-a", "product-b": "customer-b"},
            NOW - timedelta(days=60),
        )
    else:
        path = tmp_path / "serving.duckdb"
        write_projection(path, records)
        tools = DatasetTools(path, time_policy=TIME_POLICY)
        yield tools
        tools.close()


def test_exact_lookup_scoped_and_historical(backend):
    assert backend.get("customer-a", "target", NOW).transaction_id == "target"
    assert backend.get("customer-a", "foreign", NOW) is None
    assert backend.get("customer-a", "missing", NOW) is None
    assert backend.get("customer-a", "future", NOW) is None
    assert backend.get("customer-a", "late", NOW) is None
    assert backend.get("customer-a", "outside", NOW) is not None
    assert backend.product_owner("product-a", NOW) == "customer-a"
    assert backend.product_owner("unknown", NOW) is None


def test_search_time_currency_merchant_and_injection(backend):
    result = backend.search("customer-a", NOW, Search(confirmed=True))
    assert {r.transaction_id for r in result.candidates} == {
        "target",
        "same-time",
        "start",
        "prior",
        "cop",
        "known-at-target",
    }
    assert not result.truncated
    assert backend.search(
        "customer-a",
        NOW,
        Search(confirmed=True, transaction_id="target", amount="10", currency="USD"),
    ).candidates
    assert not backend.search(
        "customer-a",
        NOW,
        Search(confirmed=True, transaction_id="target", amount="10", currency="COP"),
    ).candidates
    assert [
        r.transaction_id
        for r in backend.search(
            "customer-a", NOW, Search(confirmed=True, merchant="Shop")
        ).candidates
    ] == ["prior"]
    assert not backend.search(
        "customer-a", NOW, Search(confirmed=True, merchant="shop")
    ).candidates
    assert not backend.search(
        "customer-a' OR 1=1 --", NOW, Search(confirmed=True)
    ).candidates
    assert not backend.search(
        "customer-a", NOW, Search(confirmed=True, transaction_id="' OR 1=1 --")
    ).candidates
    assert backend.get("customer-a", "target", NOW).merchant_name is None


def test_prior_history_exact_precision_and_left_censoring(backend):
    tx = backend.get("customer-a", "target", NOW)
    history = backend.history(tx, NOW)
    assert (
        history.transaction_count_prior_30d == 3
    )  # start, prior, COP, not same-time/late
    assert history.same_currency_count_prior_30d == 2
    assert str(history.median_amount_same_currency_prior_30d) == "0.0000015"
    assert history.window_end_exclusive == tx.transaction_date
    assert history.complete_window_observed
    early = backend.get("customer-a", "outside", NOW)
    assert backend.history(early, NOW).complete_window_observed is False


def test_same_case_service_and_http_contract(backend, tmp_path):
    from fastapi.testclient import TestClient

    principal = Principal(
        subject="demo",
        customer_id="customer-a",
        provider="TEST",
        scopes={"dispute:read", "dispute:write"},
        verified_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(hours=1),
    )
    service = CaseService(
        CaseStore(tmp_path / "cases.sqlite3"), backend, lambda _: principal, lambda: NOW
    )
    case = service.create(
        "token", Intake(user_utterance="Cargo no reconocido", language="es"), key="c"
    )
    with pytest.raises(Rejected, match="CURRENCY"):
        service.search(
            "token",
            case.case_id,
            Search(confirmed=True, amount="10"),
            version=1,
            key="bad",
        )
    with TestClient(create_app(service, include_legacy=False)) as client:
        h = {"Authorization": "Bearer test", "Idempotency-Key": "s"}
        r = client.post(
            f"/v1/disputes/{case.case_id}/search",
            headers=h,
            json={
                "expected_version": 1,
                "query": {"confirmed": True, "transaction_id": "target"},
            },
        )
        assert r.json()["state"] == "AWAITING_CONFIRMATION"
    case = service.confirm(
        "token",
        case.case_id,
        Selection(transaction_id="target", confirmed=True),
        version=2,
        key="confirm",
    )
    case = service.collect("token", case.case_id, version=case.version, key="collect")
    assert case.state == State.ASSESSMENT_READY
    assert (
        service.handoff(
            "token", case.case_id, version=case.version, key="handoff"
        ).state
        == State.HANDOFF_RECORDED
    )


def test_truncation_parity(tmp_path):
    records = [transaction(f"tx-{i:03d}") for i in range(51)]
    path = tmp_path / "many.duckdb"
    write_projection(path, records)
    reference = FixtureTools(
        records, {"product-a": "customer-a"}, NOW - timedelta(days=60)
    )
    tools = DatasetTools(path, time_policy=TIME_POLICY)
    try:
        assert tools.search(
            "customer-a", NOW, Search(confirmed=True)
        ) == reference.search("customer-a", NOW, Search(confirmed=True))
        assert (
            len(tools.search("customer-a", NOW, Search(confirmed=True)).candidates)
            == 50
        )
    finally:
        tools.close()


def test_startup_validation_read_only(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        DatasetTools(tmp_path / "missing", time_policy=TIME_POLICY)
    with pytest.raises(ValueError, match="Explicit acceptance"):
        DatasetTools(tmp_path / "missing", time_policy="auto")
    path = tmp_path / "serving.duckdb"
    write_projection(path, [transaction()])
    original = path.read_bytes()
    tools = DatasetTools(path, time_policy=TIME_POLICY)
    with pytest.raises(duckdb.Error):
        tools._con.execute("DELETE FROM transactions")
    tools.close()
    assert path.read_bytes() == original
    con = duckdb.connect(str(path))
    con.execute("DROP INDEX transactions_customer_idx")
    con.close()
    with pytest.raises(ValueError, match="index absent"):
        DatasetTools(path, time_policy=TIME_POLICY)


def test_absent_columns_and_duplicate_primary_key(tmp_path):
    path = tmp_path / "bad.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE transactions(x INT)")
    con.close()
    with pytest.raises(ValueError, match="schema"):
        DatasetTools(path, time_policy=TIME_POLICY)
    path2 = tmp_path / "duplicate.duckdb"
    with pytest.raises(duckdb.ConstraintException):
        write_projection(path2, [transaction(), transaction()])


def test_dataset_configuration_fails_fast(monkeypatch):
    from api.dispute_configuration import from_environment

    monkeypatch.setenv("BANKING_TOOLS_BACKEND", "dataset")
    monkeypatch.setenv("ENABLE_LEGACY_API", "true")
    with pytest.raises(ValueError, match="LEGACY"):
        from_environment()
    monkeypatch.setenv("ENABLE_LEGACY_API", "false")
    monkeypatch.delenv("DISPUTE_DATASET_DEMO_MODE", raising=False)
    with pytest.raises(ValueError, match="Explicit local"):
        from_environment()
