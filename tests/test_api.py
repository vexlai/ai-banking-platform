"""Integration tests for the FastAPI gateway (`api/main.py`)."""

from __future__ import annotations

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
