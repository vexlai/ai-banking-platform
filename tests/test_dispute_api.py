"""HTTP acceptance over the existing synthetic runtime rig; no LLM/network/IAM."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from test_case_runtime import NOW
from test_case_runtime import (
    forbid_network as forbid_network,  # noqa: PLC0414 - reuse no-network guard
)
from test_case_runtime import (
    rig as rig,  # noqa: PLC0414 - register existing pytest fixture
)

from api.main import create_app


@pytest.fixture
def http(rig):
    service, tools, principals = rig
    with TestClient(create_app(service, include_legacy=False)) as client:
        yield client, service, tools, principals


def headers(key="create", token="a"):
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key}


def create(client, key="create"):
    response = client.post(
        "/v1/disputes",
        headers=headers(key),
        json={"user_utterance": "No reconozco un cargo", "language": "es"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def command(client, case, action, key=None, **body):
    return client.post(
        f"/v1/disputes/{case['case_id']}/{action}",
        headers=headers(key or action),
        json={"expected_version": case["version"], **body},
    )


def test_happy_path_and_durable_replay(http):
    client, service, _, _ = http
    case = create(client)
    assert case["as_of_time"] == NOW.isoformat().replace("+00:00", "Z")
    assert "created_by" not in case and "customer_id" not in case
    assert create(client) == case
    r = command(
        client, case, "search", query={"confirmed": True, "transaction_id": "tx1"}
    )
    assert r.status_code == 200
    case = r.json()
    assert case["state"] == "AWAITING_CONFIRMATION" and case["selection"] is None
    assert command(client, case, "evidence", key="too-early").status_code == 409
    case = command(
        client, case, "confirm", selection={"transaction_id": "tx1", "confirmed": True}
    ).json()
    assert case["state"] == "OWNERSHIP_VERIFIED"
    case = command(client, case, "evidence").json()
    assert case["evidence"]["ownership_verified"] is True
    assert case["state"] == "ASSESSMENT_READY"
    before_handoff = case
    response = command(client, case, "handoff")
    case = response.json()
    assert case["state"] == "HANDOFF_RECORDED"
    assert command(client, before_handoff, "handoff").json() == case
    assert command(client, case, "handoff", key="different-handoff").status_code == 409
    handoff = client.get(
        f"/v1/disputes/{case['case_id']}/handoff", headers=headers()
    ).json()
    assert handoff["queue_status"] == "LOCAL_PENDING_HUMAN_REVIEW"
    audit = client.get(
        f"/v1/disputes/{case['case_id']}/audit", headers=headers()
    ).json()
    assert [r["action"] for r in audit] == [
        "CREATE",
        "SEARCH",
        "CONFIRM",
        "COLLECT",
        "HANDOFF",
    ]
    assert len(audit) == 5
    assert "command_hash" not in audit[0] and "sequence" not in audit[0]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]
    # SQL here is test verification only; never in the HTTP adapter.
    with sqlite3.connect(service.store.path) as db:
        assert db.execute("SELECT count(*) FROM cases").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM handoffs").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM commands").fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM audit").fetchone()[0] == 5
    # A fresh application/service/store can replay durable responses.
    from src.cases.service import CaseService
    from src.cases.store import CaseStore

    restarted = CaseService(
        CaseStore(service.store.path),
        service.tools,
        service.resolve_principal,
        service.clock,
    )
    with TestClient(create_app(restarted, include_legacy=False)) as second:
        assert command(second, before_handoff, "handoff").json() == case


@pytest.mark.parametrize(
    ("query", "state"),
    [
        ({"confirmed": True}, "MULTIPLE_CANDIDATES"),
        ({"confirmed": True, "transaction_id": "missing"}, "NO_CANDIDATE"),
        ({"confirmed": True, "transaction_id": "foreign"}, "NO_CANDIDATE"),
        ({"confirmed": True, "transaction_id": "future"}, "NO_CANDIDATE"),
        (
            {"confirmed": True, "transaction_id": "tx1", "currency": "COP"},
            "NO_CANDIDATE",
        ),
    ],
)
def test_candidate_branches_and_safe_handoff(http, query, state):
    client, _, _, _ = http
    case = command(client, create(client), "search", query=query).json()
    assert case["state"] == state
    assert case["selection"] is None and case["evidence"] is None
    assert all(t["customer_id"] == "customer-a" for t in case["candidates"])
    assert command(client, case, "handoff").json()["state"] == "HANDOFF_RECORDED"


@pytest.mark.parametrize("suffix", ["", "/audit", "/handoff"])
def test_reads_cross_customer_indistinguishable_from_missing(http, suffix):
    client, _, _, _ = http
    case = create(client)
    a = client.get(
        f"/v1/disputes/{case['case_id']}{suffix}", headers=headers(token="b")
    )
    b = client.get(f"/v1/disputes/missing{suffix}", headers=headers(token="b"))
    assert a.status_code == b.status_code == 404
    assert a.json()["code"] == b.json()["code"] == "CASE_NOT_ACCESSIBLE"
    assert case["case_id"] not in a.text
    assert "customer-a" not in a.text and "No reconozco" not in a.text


@pytest.mark.parametrize(
    ("action", "fields"),
    [
        ("search", {"query": {"confirmed": True, "transaction_id": "tx1"}}),
        ("confirm", {"selection": {"confirmed": True, "transaction_id": "tx1"}}),
        ("evidence", {}),
        ("handoff", {}),
    ],
)
def test_cross_customer_commands(http, action, fields):
    client, _, _, _ = http
    case = create(client)
    r = client.post(
        f"/v1/disputes/{case['case_id']}/{action}",
        headers=headers(action, "b"),
        json={"expected_version": case["version"], **fields},
    )
    assert r.status_code == 404
    assert "tx1" not in r.text


@pytest.mark.parametrize(
    "mode", ["missing", "invalid", "expired", "scope", "future-auth"]
)
def test_auth_fail_closed(http, mode):
    client, _, _, principals = http
    auth = headers()
    if mode == "missing":
        auth = {"X-API-Key": "not-a-customer-principal"}
    elif mode == "invalid":
        auth = headers(token="secret-invalid-token")
    elif mode == "expired":
        principals["a"] = principals["a"].model_copy(update={"expires_at": NOW})
    elif mode == "scope":
        principals["a"] = principals["a"].model_copy(update={"scopes": frozenset()})
    else:
        principals["a"] = principals["a"].model_copy(
            update={"verified_at": NOW + timedelta(seconds=1)}
        )
    r = client.post(
        "/v1/disputes",
        headers=auth,
        json={"user_utterance": "customer-b", "language": "es"},
    )
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
    assert "secret-invalid-token" not in r.text


def test_idempotency_version_and_selection_guards(http):
    client, _, _, _ = http
    case = create(client)
    changed = client.post(
        "/v1/disputes",
        headers=headers(),
        json={"user_utterance": "Otra petición", "language": "es"},
    )
    assert (
        changed.status_code == 409
        and changed.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    )
    assert (
        command(
            client,
            case,
            "confirm",
            selection={"confirmed": True, "transaction_id": "tx1"},
        ).status_code
        == 409
    )
    current = command(
        client, case, "search", query={"confirmed": True, "transaction_id": "tx1"}
    ).json()
    assert (
        command(client, case, "search", key="stale", query={"confirmed": True}).json()[
            "code"
        ]
        == "STALE_VERSION"
    )
    assert (
        command(
            client,
            current,
            "confirm",
            selection={"confirmed": False, "transaction_id": "tx1"},
        ).status_code
        == 422
    )
    assert (
        command(
            client,
            current,
            "confirm",
            selection={"confirmed": True, "transaction_id": "foreign"},
        ).status_code
        == 422
    )
    assert (
        client.get(f"/v1/disputes/{case['case_id']}", headers=headers()).json()[
            "selection"
        ]
        is None
    )


@pytest.mark.parametrize(
    "extra",
    [{"customer_id": "customer-b"}, {"as_of_time": "2099-01-01"}, {"principal": "b"}],
)
def test_identity_and_asof_not_body_authority(http, extra):
    client, _, _, _ = http
    r = client.post(
        "/v1/disputes",
        headers=headers(),
        json={"user_utterance": "customer-b", "language": "es", **extra},
    )
    assert r.status_code == 422 and r.json()["code"] == "INVALID_REQUEST"
    assert "customer-b" not in r.text


def test_failures_are_safe_and_not_empty_success(http, monkeypatch):
    client, service, tools, _ = http
    case = create(client)

    def fail(*args, **kwargs):
        raise RuntimeError("private backend secret")

    monkeypatch.setattr(tools, "search", fail)
    r = command(client, case, "search", query={"confirmed": True})
    assert r.status_code == 200  # Domain successfully recorded a FAILED evidence state.
    assert r.json()["state"] == "INSUFFICIENT_EVIDENCE"
    assert r.json()["issue"] == "TRANSACTION_TOOL_FAILED"
    assert "private backend secret" not in r.text
    case = r.json()
    assert command(client, case, "handoff").json()["state"] == "HANDOFF_RECORDED"
    monkeypatch.setattr(service, "get", fail)
    r = client.get(f"/v1/disputes/{case['case_id']}", headers=headers())
    assert r.status_code == 500 and r.json()["code"] == "INTERNAL_ERROR"
    assert "private backend secret" not in r.text


def test_store_failure_no_success(http, monkeypatch):
    client, service, _, _ = http

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("secret filesystem path")

    monkeypatch.setattr(service.store, "transaction", fail)
    r = client.post(
        "/v1/disputes",
        headers=headers(),
        json={"user_utterance": "No reconozco", "language": "es"},
    )
    assert r.status_code == 503 and "secret filesystem path" not in r.text


def test_invalid_input_metadata_and_no_legacy_routes(http):
    client, _, _, _ = http
    case = create(client)
    assert client.post("/v1/chat", json={}).status_code == 404
    assert client.get("/health").status_code == 200
    path = f"/v1/disputes/{case['case_id']}/search"
    for body in (
        {"query": {"confirmed": True}},
        {"expected_version": True, "query": {"confirmed": True}},
        {"expected_version": 1, "query": {"confirmed": True, "amount": 1.2}},
    ):
        assert (
            client.post(path, headers=headers("invalid"), json=body).status_code == 422
        )
    assert (
        command(
            client, case, "search", query={"confirmed": True, "amount": "10"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            path,
            headers={"Authorization": "Bearer a"},
            json={"expected_version": 1, "query": {"confirmed": True}},
        ).status_code
        == 422
    )
    assert client.post(path, headers=headers(), content="{broken").status_code == 422


def test_expiry_blocks_replay_and_reads(http):
    client, _, _, principals = http
    case = create(client)
    principals["a"] = principals["a"].model_copy(update={"expires_at": NOW})
    r = client.post(
        "/v1/disputes",
        headers=headers(),
        json={"user_utterance": "No reconozco un cargo", "language": "es"},
    )
    assert r.status_code == 401
    for suffix in ("", "/audit", "/handoff"):
        assert (
            client.get(
                f"/v1/disputes/{case['case_id']}{suffix}", headers=headers()
            ).status_code
            == 401
        )


def test_ownership_revalidated_at_http_confirmation(http):
    client, _, tools, _ = http
    case = command(
        client,
        create(client),
        "search",
        query={"confirmed": True, "transaction_id": "tx1"},
    ).json()
    tools.product_owners["product-a"] = "customer-b"
    case = command(
        client, case, "confirm", selection={"confirmed": True, "transaction_id": "tx1"}
    ).json()
    assert case["state"] == "INSUFFICIENT_EVIDENCE"
    assert case["selection"] is None
    assert case["issue"] == "OWNERSHIP_OR_EVIDENCE_CONFLICT"


def test_concurrent_http_versions(http):
    client, _, _, _ = http
    case = create(client)

    def search_once(key):
        return command(
            client, case, "search", key=key, query={"confirmed": True}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(search_once, ("concurrent-1", "concurrent-2")))
    assert sorted(codes) == [200, 409]
    audit = client.get(
        f"/v1/disputes/{case['case_id']}/audit", headers=headers()
    ).json()
    assert len(audit) == 2


def test_fixture_configuration_fails_closed(tmp_path, monkeypatch):
    from api.dispute_fixture import fixture_service, from_environment

    monkeypatch.delenv("DISPUTE_FIXTURE_MODE", raising=False)
    assert from_environment() is None
    monkeypatch.setenv("DISPUTE_FIXTURE_MODE", "true")
    monkeypatch.delenv("DISPUTE_FIXTURE_ANCHOR", raising=False)
    with pytest.raises(RuntimeError, match="Explicit fixture credentials"):
        from_environment()
    with pytest.raises(ValueError, match="distinct fixture credentials"):
        fixture_service(tmp_path / "invalid.sqlite3", "a", "b", NOW)
    assert not (tmp_path / "invalid.sqlite3").exists()


def test_unconfigured_app_closed():
    with TestClient(create_app(include_legacy=False)) as client:
        assert (
            client.post(
                "/v1/disputes",
                headers=headers(),
                json={"user_utterance": "request", "language": "es"},
            ).status_code
            == 503
        )
