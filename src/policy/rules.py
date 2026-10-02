"""Deterministic safety policy: PII redaction and evidence-based escalation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from contracts import Decision, EvidenceBundle, RiskLevel

CARD_PATTERN = re.compile(r"(?<!\d)(?:\d{4}[ -]?){3}\d{4}(?!\d)")
SSN_PATTERN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+\d{1,3}\s?)?\(?\d{3}\)?\s?\d{3}\s?\d{4}(?!\d)")

REDACTED_CARD = "[REDACTED_CARD]"
REDACTED_SSN = "[REDACTED_SSN]"
REDACTED_PHONE = "[REDACTED_PHONE]"

FRAUD_SCORE_THRESHOLD = 0.80

_HIGH_RISK_CODES = frozenset(
    {"FRAUD_SCORE_SPIKE", "OPEN_HIGH_SEVERITY_CASE", "SLA_BREACH"}
)
_OPEN_CASE_STATUS = "open"


def redact_pii(text: str) -> str:
    """Card runs first: it owns the long digit runs the narrower patterns would split.
    Grouped phone numbers (`555-123-4567`) are not masked; contiguous ones are.
    """
    redacted = CARD_PATTERN.sub(REDACTED_CARD, text)
    redacted = SSN_PATTERN.sub(REDACTED_SSN, redacted)
    return PHONE_PATTERN.sub(REDACTED_PHONE, redacted)


def contains_pii(text: str) -> bool:
    return redact_pii(text) != text


@dataclass(frozen=True, slots=True)
class EscalationSignal:
    code: str
    detail: str
    source_id: str


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    decision: Decision
    risk_level: RiskLevel
    signals: tuple[EscalationSignal, ...] = ()


def _fraud_signals(bundle: EvidenceBundle) -> list[EscalationSignal]:
    return [
        EscalationSignal(
            code="FRAUD_SCORE_SPIKE",
            detail=(
                f"Transaction {txn.transaction_id} ({txn.amount:.2f} {txn.currency} at "
                f"{txn.merchant}, status={txn.status}) scored {txn.fraud_score:.2f}, "
                f"at or above the {FRAUD_SCORE_THRESHOLD:.2f} escalation threshold."
            ),
            source_id=txn.transaction_id,
        )
        for txn in bundle.recent_transactions
        if txn.fraud_score >= FRAUD_SCORE_THRESHOLD
    ]


def _case_signals(bundle: EvidenceBundle) -> list[EscalationSignal]:
    signals: list[EscalationSignal] = []
    for case in bundle.open_cases:
        if case.status.lower() == _OPEN_CASE_STATUS and case.severity == RiskLevel.HIGH:
            signals.append(
                EscalationSignal(
                    code="OPEN_HIGH_SEVERITY_CASE",
                    detail=f"Case {case.case_id} is open at {case.severity.value} severity.",
                    source_id=case.case_id,
                )
            )
        if case.sla_breach:
            signals.append(
                EscalationSignal(
                    code="SLA_BREACH",
                    detail=f"Case {case.case_id} has breached its SLA.",
                    source_id=case.case_id,
                )
            )
        if case.repeat_complaint:
            signals.append(
                EscalationSignal(
                    code="REPEAT_COMPLAINT",
                    detail=f"Case {case.case_id} is flagged as a repeat complaint.",
                    source_id=case.case_id,
                )
            )
    return signals


def _has_evidence(bundle: EvidenceBundle) -> bool:
    return bool(
        bundle.recent_transactions
        or bundle.interaction_history
        or bundle.similar_transcripts
        or bundle.open_cases
    )


def assess_risk(bundle: EvidenceBundle) -> RiskAssessment:
    signals = _fraud_signals(bundle) + _case_signals(bundle)
    if signals:
        risk_level = (
            RiskLevel.HIGH
            if any(signal.code in _HIGH_RISK_CODES for signal in signals)
            else RiskLevel.MEDIUM
        )
        return RiskAssessment(
            decision=Decision.ESCALATE,
            risk_level=risk_level,
            signals=tuple(signals),
        )

    if not _has_evidence(bundle):
        return RiskAssessment(
            decision=Decision.CLARIFY,
            risk_level=RiskLevel.MEDIUM,
            signals=(
                EscalationSignal(
                    code="MISSING_CONTEXT",
                    detail=(
                        f"No transactions, interactions, transcripts, or cases were retrieved "
                        f"for {bundle.customer_id}."
                    ),
                    source_id=bundle.customer_id,
                ),
            ),
        )

    return RiskAssessment(decision=Decision.RESPOND, risk_level=RiskLevel.LOW)
