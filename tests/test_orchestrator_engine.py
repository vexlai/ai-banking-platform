"""Tests for the orchestrator engine (`src/orchestrator/engine.py`)."""

from collections.abc import Mapping, Sequence
from typing import Any

from contracts import ChatRequest, Decision
from src.orchestrator.engine import OrchestratorEngine
from src.orchestrator.llm import LLMTurn, ToolCall
from src.orchestrator.state_machine import State, StateMachine
from src.telemetry.logger import get_trace


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


def test_state_machine_advances_through_pipeline() -> None:
    machine = StateMachine()
    assert machine.state is State.UNDERSTAND
    for target in (State.GATHER, State.DECIDE, State.RESPOND):
        assert machine.can_advance(target)
        assert machine.advance(target) is target
    assert not machine.can_advance(State.RESPOND)


class _StubLLM:
    """Scripted `LLMClient` seam: replays queued turns and records requests."""

    def __init__(self, turns: list[LLMTurn]) -> None:
        self._turns = list(turns)
        self.requests: list[list[Mapping[str, Any]]] = []

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        tools: Sequence[Mapping[str, Any]],
    ) -> LLMTurn:
        self.requests.append(list(messages))
        return self._turns.pop(0)


def test_llm_tool_loop_executes_mock_tool_and_logs() -> None:
    stub = _StubLLM(
        [
            LLMTurn(
                content=None,
                tool_calls=(
                    ToolCall(
                        id="call_1",
                        name="customer_360_view",
                        arguments={"customer_id": "CUST_001"},
                    ),
                ),
            ),
            LLMTurn(content="Grounded balance answer."),
        ]
    )
    response = OrchestratorEngine(llm_client=stub).process_turn(
        ChatRequest(
            customer_id="CUST_001",
            session_id="SESS_TEST",
            message="What is my available balance?",
        )
    )
    assert response.decision is Decision.RESPOND
    assert response.reply == "Grounded balance answer."
    assert len(stub.requests) == 2
    assert any(
        message.get("role") == "tool" and message.get("tool_call_id") == "call_1"
        for message in stub.requests[1]
    )
    records = get_trace(response.trace_id)
    assert any(record["message"].startswith("LLM tool executed:") for record in records)
