"""Grounded, PII-safe handoff payloads and the evidence list shown in the UI panel."""

from __future__ import annotations

from src.policy.rules import RiskAssessment, redact_pii
from src.tools.schemas import Evidence, EvidenceBundle, Handoff, SourceTool

_ACTION_BY_SIGNAL = {
    "FRAUD_SCORE_SPIKE": "Confirm the flagged transaction with the customer before any account action.",
    "OPEN_HIGH_SEVERITY_CASE": "Review the open high-severity case and confirm the next SLA step.",
    "SLA_BREACH": "Notify the case owner that the SLA is breached.",
    "REPEAT_COMPLAINT": "Review how the previous complaint was resolved before replying.",
    "MISSING_CONTEXT": "Collect the missing identifiers before attempting an answer.",
}

_AGENT_ONLY_ACTION = "Route to a human agent; automation must not move money or approve credit."


def _redacted(source: SourceTool, source_id: str, snippet: str) -> Evidence:
    return Evidence(source=source, source_id=source_id, snippet=redact_pii(snippet))


def build_evidence(bundle: EvidenceBundle) -> list[Evidence]:
    customer = bundle.customer_360
    journey = bundle.journey_summary
    evidence = [
        _redacted(
            SourceTool.CUSTOMER_360,
            customer.customer_id,
            f"{customer.full_name} | segment={customer.segment} | country={customer.country} "
            f"| products={', '.join(customer.products) or 'none'}",
        ),
        _redacted(
            SourceTool.JOURNEY_SUMMARY,
            journey.session_id,
            f"window={journey.window_hours}h | errors={journey.error_count} "
            f"| abandoned_forms={journey.abandoned_forms}",
        ),
    ]
    evidence += [
        _redacted(
            SourceTool.RECENT_TRANSACTIONS,
            txn.transaction_id,
            f"{txn.amount:.2f} {txn.currency} at {txn.merchant} | status={txn.status} "
            f"| fraud_score={txn.fraud_score:.2f}",
        )
        for txn in bundle.recent_transactions
    ]
    evidence += [
        _redacted(
            SourceTool.INTERACTION_HISTORY,
            interaction.interaction_id,
            f"{interaction.channel}: {interaction.summary}",
        )
        for interaction in bundle.interaction_history
    ]
    evidence += [
        _redacted(
            SourceTool.SIMILAR_TRANSCRIPTS,
            match.transcript_id,
            f"similarity={match.similarity:.2f} | {match.summary}",
        )
        for match in bundle.similar_transcripts
    ]
    evidence += [
        _redacted(
            SourceTool.OPEN_CASES,
            case.case_id,
            f"status={case.status} | severity={case.severity.value} | sla_breach={case.sla_breach} "
            f"| repeat_complaint={case.repeat_complaint}",
        )
        for case in bundle.open_cases
    ]
    return evidence


def _verified_facts(bundle: EvidenceBundle, assessment: RiskAssessment) -> list[str]:
    customer = bundle.customer_360
    journey = bundle.journey_summary
    facts = [
        f"Profile: {customer.full_name}, segment {customer.segment}, country {customer.country}, "
        f"as of {customer.as_of.isoformat()}.",
        f"Session {journey.session_id}: {journey.error_count} error(s) and "
        f"{journey.abandoned_forms} abandoned form(s) in the last {journey.window_hours}h.",
    ]
    facts += [signal.detail for signal in assessment.signals]
    facts += [
        f"{interaction.channel} interaction: {interaction.summary}"
        for interaction in bundle.interaction_history
    ]
    return facts


def _recommended_actions(assessment: RiskAssessment) -> list[str]:
    actions = list(
        dict.fromkeys(
            _ACTION_BY_SIGNAL[signal.code]
            for signal in assessment.signals
            if signal.code in _ACTION_BY_SIGNAL
        )
    )
    actions.append(_AGENT_ONLY_ACTION)
    return actions


def build_handoff(bundle: EvidenceBundle, session_id: str, assessment: RiskAssessment) -> Handoff:
    return Handoff(
        handoff_id=f"HND_{bundle.customer_id}_{session_id}",
        customer_id=bundle.customer_id,
        session_id=session_id,
        reason=" ".join(signal.detail for signal in assessment.signals)
        or "Escalated for manual review.",
        risk_level=assessment.risk_level,
        verified_facts=_verified_facts(bundle, assessment),
        recommended_actions=_recommended_actions(assessment),
        evidence=build_evidence(bundle),
        created_at=bundle.retrieved_at,
    )
