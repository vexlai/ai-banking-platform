"""Deterministic, customer-scoped mock data for isolated component testing.

Fixtures are frozen at import time and every accessor returns a deep copy, so
callers can never mutate shared state and repeated dumps stay byte-identical.
Only `CUST_002` carries the high fraud score (0.92); an unknown id raises
`CustomerNotFoundError`, mirroring the strict DuckDB serving tools.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from contracts import (
    CaseRecord,
    Customer360,
    EvidenceBundle,
    Interaction,
    JourneyEvent,
    JourneySummary,
    RiskLevel,
    Transaction,
    TranscriptMatch,
)
from src.tools.errors import CustomerNotFoundError

FIXED_NOW = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
"""Frozen clock so every mock payload is byte-stable across runs."""

FRAUD_ALERT_SCORE = 0.92
"""Fraud score attached only to the CUST_002 escalate fixture."""

MOCK_CUSTOMERS: tuple[str, ...] = (
    "CUST_001",
    "CUST_002",
    "CUST_003",
    "CUST_004",
    "CUST_005",
    "CUST_006",
    "CUST_007",
)
"""Named customer fixtures; any other id raises `CustomerNotFoundError`."""


def _ago(minutes: int) -> datetime:
    return FIXED_NOW - timedelta(minutes=minutes)


def _txn(
    customer_id: str,
    suffix: str,
    amount: float,
    merchant: str,
    status: str,
    fraud_score: float,
    age_minutes: int,
    currency: str,
) -> Transaction:
    return Transaction(
        transaction_id=f"TXN_{suffix}",
        customer_id=customer_id,
        amount=amount,
        currency=currency,
        merchant=merchant,
        status=status,
        fraud_score=fraud_score,
        occurred_at=_ago(age_minutes),
    )


def _journey(
    customer_id: str,
    session_id: str,
    error_count: int,
    abandoned_forms: int,
) -> JourneySummary:
    events = [
        JourneyEvent(
            event_id=f"EVT_{session_id}_LOGIN",
            event_type="login",
            status="success",
            occurred_at=_ago(90),
        ),
        JourneyEvent(
            event_id=f"EVT_{session_id}_FORM",
            event_type="form_submit",
            status="error" if error_count else "success",
            occurred_at=_ago(60),
        ),
    ]
    return JourneySummary(
        customer_id=customer_id,
        session_id=session_id,
        window_hours=24,
        events=events,
        error_count=error_count,
        abandoned_forms=abandoned_forms,
        as_of=FIXED_NOW,
    )


def _cust_001() -> EvidenceBundle:
    customer_id = "CUST_001"
    return EvidenceBundle(
        customer_id=customer_id,
        customer_360=Customer360(
            customer_id=customer_id,
            full_name="Maria Gonzalez",
            segment="retail",
            country="MX",
            products=["checking_account", "credit_card"],
            credit_limit=25000.0,
            currency="MXN",
            as_of=FIXED_NOW,
        ),
        recent_transactions=[
            _txn(
                customer_id,
                "C001_001",
                1250.00,
                "Supermercado Central",
                "posted",
                0.02,
                180,
                "MXN",
            ),
            _txn(
                customer_id,
                "C001_002",
                430.75,
                "Farmacia del Sol",
                "posted",
                0.01,
                2400,
                "MXN",
            ),
        ],
        journey_summary=_journey(
            customer_id, "SESS_C001", error_count=0, abandoned_forms=0
        ),
        interaction_history=[
            Interaction(
                interaction_id="INT_C001_001",
                channel="chat",
                summary="Asked about current account balance.",
                occurred_at=_ago(60),
            ),
        ],
        similar_transcripts=[
            TranscriptMatch(
                transcript_id="TR_C001_001",
                similarity=0.81,
                summary="Customer asked for available balance.",
            ),
        ],
        open_cases=[],
        retrieved_at=FIXED_NOW,
    )


def _cust_002() -> EvidenceBundle:
    customer_id = "CUST_002"
    return EvidenceBundle(
        customer_id=customer_id,
        customer_360=Customer360(
            customer_id=customer_id,
            full_name="Juan Perez",
            segment="retail",
            country="CO",
            products=["savings_account", "credit_card"],
            credit_limit=50000.0,
            currency="COP",
            as_of=FIXED_NOW,
        ),
        recent_transactions=[
            _txn(
                customer_id,
                "C002_001",
                4820.50,
                "UNKNOWN_ECOM_MERCHANT",
                "flagged",
                FRAUD_ALERT_SCORE,
                45,
                "COP",
            ),
            _txn(
                customer_id,
                "C002_002",
                120.00,
                "Coffee Corner",
                "posted",
                0.03,
                3000,
                "COP",
            ),
        ],
        journey_summary=_journey(
            customer_id, "SESS_C002", error_count=2, abandoned_forms=1
        ),
        interaction_history=[
            Interaction(
                interaction_id="INT_C002_001",
                channel="call",
                summary="Reported an unrecognized card charge.",
                occurred_at=_ago(30),
            ),
        ],
        similar_transcripts=[
            TranscriptMatch(
                transcript_id="TR_C002_001",
                similarity=0.88,
                summary="Customer reporting a possible card fraud.",
            ),
        ],
        open_cases=[
            CaseRecord(
                case_id="CASE_C002_001",
                status="open",
                severity=RiskLevel.HIGH,
                sla_breach=False,
                repeat_complaint=False,
                opened_at=_ago(20),
            ),
        ],
        retrieved_at=FIXED_NOW,
    )


def _cust_003() -> EvidenceBundle:
    customer_id = "CUST_003"
    return EvidenceBundle(
        customer_id=customer_id,
        customer_360=Customer360(
            customer_id=customer_id,
            full_name="Ana Silva",
            segment="premium",
            country="AR",
            products=["checking_account", "investment_account"],
            credit_limit=80000.0,
            currency="ARS",
            as_of=FIXED_NOW,
        ),
        recent_transactions=[
            _txn(
                customer_id,
                "C003_001",
                9800.00,
                "Boutique Norte",
                "posted",
                0.04,
                600,
                "ARS",
            ),
        ],
        journey_summary=_journey(
            customer_id, "SESS_C003", error_count=0, abandoned_forms=0
        ),
        interaction_history=[
            Interaction(
                interaction_id="INT_C003_001",
                channel="email",
                summary="Requested a replacement card statement.",
                occurred_at=_ago(120),
            ),
        ],
        similar_transcripts=[
            TranscriptMatch(
                transcript_id="TR_C003_001",
                similarity=0.76,
                summary="Customer requested a card statement copy.",
            ),
        ],
        open_cases=[],
        retrieved_at=FIXED_NOW,
    )


def _cust_004() -> EvidenceBundle:
    customer_id = "CUST_004"
    return EvidenceBundle(
        customer_id=customer_id,
        customer_360=Customer360(
            customer_id=customer_id,
            full_name="Liam Chen",
            segment="retail",
            country="US",
            products=["checking_account"],
            credit_limit=15000.0,
            currency="USD",
            as_of=FIXED_NOW,
        ),
        recent_transactions=[],
        journey_summary=_journey(
            customer_id, "SESS_C004", error_count=0, abandoned_forms=0
        ),
        interaction_history=[
            Interaction(
                interaction_id="INT_C004_001",
                channel="chat",
                summary="Confirmed there is no recent account activity.",
                occurred_at=_ago(150),
            ),
        ],
        similar_transcripts=[
            TranscriptMatch(
                transcript_id="TR_C004_001",
                similarity=0.74,
                summary="Customer asked about recent transactions.",
            ),
        ],
        open_cases=[],
        retrieved_at=FIXED_NOW,
    )


def _cust_005() -> EvidenceBundle:
    customer_id = "CUST_005"
    return EvidenceBundle(
        customer_id=customer_id,
        customer_360=Customer360(
            customer_id=customer_id,
            full_name="Sofia Rossi",
            segment="retail",
            country="IT",
            products=["checking_account", "credit_card"],
            credit_limit=20000.0,
            currency="EUR",
            as_of=FIXED_NOW,
        ),
        recent_transactions=[
            _txn(
                customer_id,
                "C005_001",
                64.20,
                "Caffe Milano",
                "posted",
                0.01,
                300,
                "EUR",
            ),
        ],
        journey_summary=_journey(
            customer_id, "SESS_C005", error_count=3, abandoned_forms=2
        ),
        interaction_history=[
            Interaction(
                interaction_id="INT_C005_001",
                channel="web",
                summary="Could not complete the online login form.",
                occurred_at=_ago(45),
            ),
        ],
        similar_transcripts=[
            TranscriptMatch(
                transcript_id="TR_C005_001",
                similarity=0.79,
                summary="Customer reported repeated digital login errors.",
            ),
        ],
        open_cases=[],
        retrieved_at=FIXED_NOW,
    )


def _cust_006() -> EvidenceBundle:
    customer_id = "CUST_006"
    return EvidenceBundle(
        customer_id=customer_id,
        customer_360=Customer360(
            customer_id=customer_id,
            full_name="Diego Torres",
            segment="premium",
            country="ES",
            products=["checking_account", "mortgage"],
            credit_limit=60000.0,
            currency="EUR",
            as_of=FIXED_NOW,
        ),
        recent_transactions=[
            _txn(
                customer_id,
                "C006_001",
                220.00,
                "Iberia Utilities",
                "posted",
                0.05,
                720,
                "EUR",
            ),
        ],
        journey_summary=_journey(
            customer_id, "SESS_C006", error_count=1, abandoned_forms=0
        ),
        interaction_history=[
            Interaction(
                interaction_id="INT_C006_001",
                channel="call",
                summary="Complained about an unresolved transfer delay.",
                occurred_at=_ago(90),
            ),
        ],
        similar_transcripts=[
            TranscriptMatch(
                transcript_id="TR_C006_001",
                similarity=0.83,
                summary="Customer chased an open complaint past its SLA.",
            ),
        ],
        open_cases=[
            CaseRecord(
                case_id="CASE_C006_001",
                status="open",
                severity=RiskLevel.HIGH,
                sla_breach=True,
                repeat_complaint=False,
                opened_at=_ago(2880),
            ),
        ],
        retrieved_at=FIXED_NOW,
    )


def _cust_007() -> EvidenceBundle:
    customer_id = "CUST_007"
    return EvidenceBundle(
        customer_id=customer_id,
        customer_360=Customer360(
            customer_id=customer_id,
            full_name="Emma Novak",
            segment="retail",
            country="CZ",
            products=["savings_account"],
            credit_limit=12000.0,
            currency="CZK",
            as_of=FIXED_NOW,
        ),
        recent_transactions=[
            _txn(
                customer_id,
                "C007_001",
                310.50,
                "Praha Electronics",
                "posted",
                0.02,
                500,
                "CZK",
            ),
        ],
        journey_summary=_journey(
            customer_id, "SESS_C007", error_count=0, abandoned_forms=1
        ),
        interaction_history=[
            Interaction(
                interaction_id="INT_C007_001",
                channel="email",
                summary="Reopened a complaint that was never resolved.",
                occurred_at=_ago(120),
            ),
        ],
        similar_transcripts=[
            TranscriptMatch(
                transcript_id="TR_C007_001",
                similarity=0.77,
                summary="Repeat complainer requesting a manager callback.",
            ),
        ],
        open_cases=[
            CaseRecord(
                case_id="CASE_C007_001",
                status="open",
                severity=RiskLevel.MEDIUM,
                sla_breach=False,
                repeat_complaint=True,
                opened_at=_ago(4320),
            ),
        ],
        retrieved_at=FIXED_NOW,
    )


_BUILDERS = {
    "CUST_001": _cust_001,
    "CUST_002": _cust_002,
    "CUST_003": _cust_003,
    "CUST_004": _cust_004,
    "CUST_005": _cust_005,
    "CUST_006": _cust_006,
    "CUST_007": _cust_007,
}

_FIXTURES: dict[str, EvidenceBundle] = {
    cid: build() for cid, build in _BUILDERS.items()
}


def is_mock_customer(customer_id: str) -> bool:
    return customer_id in _FIXTURES


def get_context(customer_id: str) -> EvidenceBundle:
    bundle = _FIXTURES.get(customer_id)
    if bundle is None:
        raise CustomerNotFoundError(
            "customer_360_view", f"no fixture for '{customer_id}'"
        )
    return bundle.model_copy(deep=True)


def get_customer_360(customer_id: str) -> Customer360:
    return get_context(customer_id).customer_360


def get_recent_transactions(customer_id: str) -> list[Transaction]:
    return get_context(customer_id).recent_transactions


def get_journey_summary(customer_id: str) -> JourneySummary:
    return get_context(customer_id).journey_summary


def get_interaction_history(customer_id: str) -> list[Interaction]:
    return get_context(customer_id).interaction_history


def get_similar_transcripts(customer_id: str) -> list[TranscriptMatch]:
    return get_context(customer_id).similar_transcripts


def get_open_cases(customer_id: str) -> list[CaseRecord]:
    return get_context(customer_id).open_cases
