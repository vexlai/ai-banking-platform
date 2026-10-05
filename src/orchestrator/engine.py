"""Execution loop: intent, evidence assembly, policy decision, and grounded response."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from contracts import (
    ChatRequest,
    ChatResponse,
    Decision,
    Evidence,
    EvidenceBundle,
    Handoff,
    Intent,
)
from src.orchestrator import llm, prompts
from src.orchestrator.state_machine import State, StateMachine
from src.policy.handoff import build_evidence, build_handoff
from src.policy.rules import RiskAssessment, assess_risk, contains_pii, redact_pii
from src.telemetry.logger import LatencyTimer, get_logger, new_trace_id
from src.tools import context_tools, mocks


def classify_intent(message: str) -> Intent:
    """First-match over the priority keyword table; anything unmatched is UNKNOWN."""
    lowered = message.lower()
    for intent, keywords in prompts.INTENT_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return intent
    return Intent.UNKNOWN


def _assistant_message(turn: llm.LLMTurn) -> dict[str, Any]:
    """Rebuilds the OpenAI assistant message so tool results can follow it."""
    return {
        "role": "assistant",
        "content": turn.content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                },
            }
            for call in turn.tool_calls
        ],
    }


class OrchestratorEngine:
    """Runs one turn through UNDERSTAND -> GATHER -> DECIDE -> RESPOND.

    The policy engine owns the decision; intent only shapes the reply. `use_mocks=False`
    routes evidence assembly through the DuckDB context tools (INT-01), which degrade
    to the deterministic fixtures when the serving database or views are unavailable.
    """

    def __init__(
        self,
        *,
        use_mocks: bool = True,
        logger: logging.Logger | None = None,
        llm_client: llm.LLMClient | None = None,
    ) -> None:
        self._use_mocks = use_mocks
        self._logger = logger or get_logger()
        self._llm = llm_client if llm_client is not None else llm.from_env()

    def process_turn(self, request: ChatRequest) -> ChatResponse:
        trace_id = new_trace_id()
        timer = LatencyTimer()
        machine = StateMachine()
        self._logger.info(
            "Orchestrator turn started for customer: %s",
            request.customer_id,
            extra={"trace_id": trace_id, "session_id": request.session_id},
        )
        intent = self._understand(request, machine, trace_id)
        bundle = self._gather(request, machine, trace_id)
        assessment = self._decide(bundle, machine, trace_id)
        response = self._respond(
            request, bundle, assessment, intent, trace_id, timer.elapsed_ms
        )
        self._logger.info(
            "Orchestrator turn finished decision=%s latency_ms=%s",
            response.decision,
            response.latency_ms,
            extra={"trace_id": trace_id, "intent": response.intent.value},
        )
        return response

    def _understand(
        self, request: ChatRequest, machine: StateMachine, trace_id: str
    ) -> Intent:
        for field in ("customer_id", "session_id", "message"):
            if not getattr(request, field).strip():
                self._logger.warning(
                    "Missing request field: %s", field, extra={"trace_id": trace_id}
                )
        intent = classify_intent(request.message)
        self._logger.info(
            "Intent classified as: %s",
            intent,
            extra={"trace_id": trace_id, "customer_id": request.customer_id},
        )
        machine.advance(State.GATHER)
        return intent

    def _gather(
        self, request: ChatRequest, machine: StateMachine, trace_id: str
    ) -> EvidenceBundle:
        if self._use_mocks:
            bundle = mocks.get_context(request.customer_id)
        else:
            bundle = context_tools.get_context(request.customer_id)
        self._logger.info(
            "Evidence gathered for customer %s: %s transaction(s), %s interaction(s), %s case(s)",
            request.customer_id,
            len(bundle.recent_transactions),
            len(bundle.interaction_history),
            len(bundle.open_cases),
            extra={"trace_id": trace_id},
        )
        machine.advance(State.DECIDE)
        return bundle

    def _decide(
        self, bundle: EvidenceBundle, machine: StateMachine, trace_id: str
    ) -> RiskAssessment:
        assessment = assess_risk(bundle)
        self._logger.info(
            "Policy decision resolved: %s risk=%s signals=%s",
            assessment.decision,
            assessment.risk_level,
            len(assessment.signals),
            extra={"trace_id": trace_id, "customer_id": bundle.customer_id},
        )
        machine.advance(State.RESPOND)
        return assessment

    def _respond(
        self,
        request: ChatRequest,
        bundle: EvidenceBundle,
        assessment: RiskAssessment,
        intent: Intent,
        trace_id: str,
        latency_ms: float,
    ) -> ChatResponse:
        evidence = build_evidence(bundle)
        handoff = self._handoff_or_none(bundle, request, assessment)
        llm_reply = self._llm_reply(request, intent, assessment, trace_id)
        raw_reply = llm_reply or self._render_reply(
            intent, assessment, bundle, evidence, handoff
        )
        reply = redact_pii(raw_reply)
        response = ChatResponse(
            session_id=request.session_id,
            decision=assessment.decision,
            intent=intent,
            reply=reply,
            evidence=evidence,
            handoff=handoff,
            redacted=reply != raw_reply or contains_pii(request.message),
            trace_id=trace_id,
            latency_ms=latency_ms,
            created_at=datetime.now(timezone.utc),
        )
        self._logger.info(
            "Response assembled redacted=%s handoff=%s",
            response.redacted,
            response.handoff is not None,
            extra={"trace_id": trace_id},
        )
        return response

    def _llm_reply(
        self,
        request: ChatRequest,
        intent: Intent,
        assessment: RiskAssessment,
        trace_id: str,
    ) -> str | None:
        """Runs the tool-calling loop for a grounded reply.

        Returns `None` when the client is disabled or the provider fails, letting the
        deterministic template take over; escalations never surface model text.
        """
        if self._llm is None or assessment.decision is not Decision.RESPOND:
            return None
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": prompts.SYSTEM_PROMPT},
            {"role": "user", "content": self._llm_user_prompt(request, intent)},
        ]
        try:
            for _ in range(llm.MAX_TOOL_ROUNDS):
                turn = self._llm.complete(messages, tools=prompts.TOOL_DEFINITIONS)
                if not turn.tool_calls:
                    return turn.content
                messages.append(_assistant_message(turn))
                messages.extend(
                    self._tool_message(call, trace_id) for call in turn.tool_calls
                )
            self._logger.warning(
                "LLM tool loop exhausted without a final answer",
                extra={"trace_id": trace_id},
            )
        except Exception as exc:  # noqa: BLE001 - any provider failure must fall back
            self._logger.warning(
                "LLM turn failed, using heuristic reply: %s",
                exc,
                extra={"trace_id": trace_id},
            )
        return None

    def _tool_message(self, call: llm.ToolCall, trace_id: str) -> dict[str, Any]:
        try:
            content = llm.execute_tool(call.name, call.arguments)
        except llm.ToolExecutionError as exc:
            self._logger.warning(
                "LLM requested an unavailable tool: %s",
                exc,
                extra={"trace_id": trace_id, "tool": call.name},
            )
            content = json.dumps({"error": str(exc)})
        else:
            self._logger.info(
                "LLM tool executed: %s",
                call.name,
                extra={"trace_id": trace_id, "tool": call.name},
            )
        return {
            "role": "tool",
            "tool_call_id": call.id,
            "name": call.name,
            "content": content,
        }

    @staticmethod
    def _llm_user_prompt(request: ChatRequest, intent: Intent) -> str:
        return (
            f"Customer {request.customer_id} in session {request.session_id} asks: "
            f"{request.message}\n"
            f"Classified intent: {intent.value}. Call the context tools you need, then "
            "answer using only the returned evidence."
        )

    @staticmethod
    def _handoff_or_none(
        bundle: EvidenceBundle, request: ChatRequest, assessment: RiskAssessment
    ) -> Handoff | None:
        if assessment.decision is not Decision.ESCALATE:
            return None
        return build_handoff(bundle, request.session_id, assessment)

    @staticmethod
    def _render_reply(
        intent: Intent,
        assessment: RiskAssessment,
        bundle: EvidenceBundle,
        evidence: list[Evidence],
        handoff: Handoff | None,
    ) -> str:
        if assessment.decision is Decision.ESCALATE and handoff is not None:
            return prompts.ESCALATION_REPLY.format(handoff_id=handoff.handoff_id)
        if assessment.decision is Decision.CLARIFY:
            return prompts.CLARIFICATION_REPLY
        return prompts.RESPOND_TEMPLATE.format(
            opener=prompts.RESPOND_OPENERS[intent],
            name=bundle.customer_360.full_name,
            count=len(evidence),
            sources=OrchestratorEngine._source_ids(evidence),
            facts=OrchestratorEngine._grounded_facts(bundle),
        )

    @staticmethod
    def _source_ids(evidence: list[Evidence]) -> str:
        return ", ".join(dict.fromkeys(item.source_id for item in evidence))

    @staticmethod
    def _grounded_facts(bundle: EvidenceBundle) -> str:
        customer = bundle.customer_360
        journey = bundle.journey_summary
        return prompts.FACTS_TEMPLATE.format(
            segment=customer.segment,
            country=customer.country,
            products=", ".join(customer.products) or "none",
            session_id=journey.session_id,
            errors=journey.error_count,
            abandoned=journey.abandoned_forms,
            window_hours=journey.window_hours,
        )
