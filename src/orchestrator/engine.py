"""Execution loop: intent, evidence assembly, policy decision, and grounded response."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.orchestrator import prompts
from src.orchestrator.state_machine import State, StateMachine
from src.policy.handoff import build_evidence, build_handoff
from src.policy.rules import RiskAssessment, assess_risk, contains_pii, redact_pii
from src.telemetry.logger import LatencyTimer, get_logger, new_trace_id
from src.tools import mocks
from src.tools.schemas import (
    ChatRequest,
    ChatResponse,
    Decision,
    Evidence,
    EvidenceBundle,
    Handoff,
    Intent,
)


def classify_intent(message: str) -> Intent:
    """First-match over the priority keyword table; anything unmatched is UNKNOWN."""
    lowered = message.lower()
    for intent, keywords in prompts.INTENT_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return intent
    return Intent.UNKNOWN


class OrchestratorEngine:
    """Runs one turn through UNDERSTAND -> GATHER -> DECIDE -> RESPOND.

    The policy engine owns the decision; intent only shapes the reply. `use_mocks=False`
    is reserved for the real DuckDB tools (Developer A, INT-01).
    """

    def __init__(
        self, *, use_mocks: bool = True, logger: logging.Logger | None = None
    ) -> None:
        self._use_mocks = use_mocks
        self._logger = logger or get_logger()

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
        if not self._use_mocks:
            raise NotImplementedError(
                "Real DuckDB context tools belong to Developer A (INT-01)."
            )
        bundle = mocks.get_context(request.customer_id)
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
        raw_reply = self._render_reply(intent, assessment, bundle, evidence, handoff)
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
