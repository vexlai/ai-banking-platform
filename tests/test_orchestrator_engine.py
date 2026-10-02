"""Tests for the orchestrator engine (`src/orchestrator/engine.py`)."""

from src.orchestrator.engine import OrchestratorEngine
from src.tools.schemas import ChatRequest, Decision


def test_benign_turn_responds_without_handoff() -> None:
    response = OrchestratorEngine().process_turn(
        ChatRequest(
            customer_id="CUST_001",
            session_id="SESS_TEST",
            message="What is my available balance?",
        )
    )
    assert response.decision is Decision.RESPOND
    assert response.handoff is None
