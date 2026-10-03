"""Integration tests for the FastAPI gateway (`api/main.py`)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_responds_for_benign_customer() -> None:
    response = client.post(
        "/v1/chat",
        json={
            "customer_id": "CUST_001",
            "session_id": "SESS_API_01",
            "message": "What is my available balance?",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "respond"
    assert body["handoff"] is None
    assert body["trace_id"]
    assert body["reply"]


def test_customer_context_returns_bundle() -> None:
    response = client.get("/v1/customers/CUST_002/context")
    assert response.status_code == 200
    assert response.json()["customer_id"] == "CUST_002"


def test_trace_serves_records_for_request() -> None:
    chat = client.post(
        "/v1/chat",
        json={
            "customer_id": "CUST_001",
            "session_id": "SESS_API_02",
            "message": "What is my available balance?",
        },
    )
    trace_id = chat.json()["trace_id"]
    response = client.get(f"/v1/trace/{trace_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == trace_id
    assert body["records"]


def _chat_payload() -> dict[str, str]:
    return {
        "customer_id": "CUST_001",
        "session_id": "SESS_AUTH_01",
        "message": "What is my available balance?",
    }


def test_chat_rejects_missing_api_key_when_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_KEY_REQUIRED", "true")
    monkeypatch.setenv("API_KEY", "secret-key")
    assert client.post("/v1/chat", json=_chat_payload()).status_code == 401


def test_chat_rejects_invalid_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY_REQUIRED", "true")
    monkeypatch.setenv("API_KEY", "secret-key")
    response = client.post(
        "/v1/chat", json=_chat_payload(), headers={"X-API-Key": "wrong"}
    )
    assert response.status_code == 401


def test_chat_accepts_valid_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY_REQUIRED", "true")
    monkeypatch.setenv("API_KEY", "secret-key")
    response = client.post(
        "/v1/chat", json=_chat_payload(), headers={"X-API-Key": "secret-key"}
    )
    assert response.status_code == 200


def test_protected_routes_reject_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_KEY_REQUIRED", "true")
    monkeypatch.setenv("API_KEY", "secret-key")
    assert client.get("/v1/customers/CUST_002/context").status_code == 401
    assert client.get("/v1/trace/unknown").status_code == 401


def test_health_stays_open_when_api_key_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_KEY_REQUIRED", "true")
    monkeypatch.setenv("API_KEY", "secret-key")
    assert client.get("/health").status_code == 200


def test_auth_headers_forward_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    ui = pytest.importorskip("apps.demo_ui.app")
    monkeypatch.setenv("API_KEY", "secret-key")
    assert ui._auth_headers() == {"X-API-Key": "secret-key"}
    monkeypatch.delenv("API_KEY")
    assert ui._auth_headers() == {}
