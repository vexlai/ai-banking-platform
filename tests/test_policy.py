"""Unit tests for the deterministic safety policy (`src/policy/rules.py`)."""

from __future__ import annotations

import pytest

from contracts import Decision, RiskLevel
from src.policy.rules import assess_risk, redact_pii
from src.tools import mocks


def test_redact_pii_masks_card_ssn_phone_in_order() -> None:
    raw = "card 4111 1111 1111 1111 ssn 123-45-6789 phone 5551234567"
    assert (
        redact_pii(raw)
        == "card [REDACTED_CARD] ssn [REDACTED_SSN] phone [REDACTED_PHONE]"
    )


@pytest.mark.parametrize(
    ("customer_id", "expected_decision", "expected_risk_level"),
    [
        ("CUST_002", Decision.ESCALATE, RiskLevel.HIGH),
        ("CUST_001", Decision.RESPOND, RiskLevel.LOW),
    ],
)
def test_assess_risk_decisions(
    customer_id: str, expected_decision: Decision, expected_risk_level: RiskLevel
) -> None:
    assessment = assess_risk(mocks.get_context(customer_id))
    assert assessment.decision is expected_decision
    assert assessment.risk_level is expected_risk_level
