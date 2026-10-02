"""Shared Pydantic contracts for API, tool, and evidence payloads."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Decision(StrEnum):
    RESPOND = "respond"
    CLARIFY = "clarify"
    ESCALATE = "escalate"


class Intent(StrEnum):
    BALANCE_INQUIRY = "balance_inquiry"
    TRANSACTION_STATUS = "transaction_status"
    FRAUD_REPORT = "fraud_report"
    CARD_ISSUE = "card_issue"
    COMPLAINT = "complaint"
    UNKNOWN = "unknown"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceTool(StrEnum):
    CUSTOMER_360 = "customer_360_view"
    RECENT_TRANSACTIONS = "recent_transactions"
    JOURNEY_SUMMARY = "journey_summary"
    INTERACTION_HISTORY = "interaction_history"
    SIMILAR_TRANSCRIPTS = "similar_transcripts"
    OPEN_CASES = "open_cases"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Customer360(Contract):
    customer_id: str
    full_name: str
    segment: str
    country: str
    products: list[str] = Field(default_factory=list)
    credit_limit: float
    currency: str
    as_of: datetime


class Transaction(Contract):
    transaction_id: str
    customer_id: str
    amount: float
    currency: str
    merchant: str
    status: str
    fraud_score: float = Field(ge=0.0, le=1.0)
    occurred_at: datetime


class JourneyEvent(Contract):
    event_id: str
    event_type: str
    status: str
    occurred_at: datetime


class JourneySummary(Contract):
    customer_id: str
    session_id: str
    window_hours: int
    events: list[JourneyEvent] = Field(default_factory=list)
    error_count: int
    abandoned_forms: int
    as_of: datetime


class Interaction(Contract):
    interaction_id: str
    channel: str
    summary: str
    occurred_at: datetime


class TranscriptMatch(Contract):
    transcript_id: str
    similarity: float = Field(ge=0.0, le=1.0)
    summary: str


class CaseRecord(Contract):
    case_id: str
    status: str
    severity: RiskLevel
    sla_breach: bool
    repeat_complaint: bool
    opened_at: datetime


class Evidence(Contract):
    source: SourceTool
    source_id: str
    snippet: str


class EvidenceBundle(Contract):
    customer_id: str
    customer_360: Customer360
    recent_transactions: list[Transaction] = Field(default_factory=list)
    journey_summary: JourneySummary
    interaction_history: list[Interaction] = Field(default_factory=list)
    similar_transcripts: list[TranscriptMatch] = Field(default_factory=list)
    open_cases: list[CaseRecord] = Field(default_factory=list)
    retrieved_at: datetime


class Handoff(Contract):
    handoff_id: str
    customer_id: str
    session_id: str
    reason: str
    risk_level: RiskLevel
    verified_facts: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    created_at: datetime


class ChatRequest(Contract):
    customer_id: str
    session_id: str
    message: str


class ChatResponse(Contract):
    session_id: str
    decision: Decision
    intent: Intent
    reply: str
    evidence: list[Evidence] = Field(default_factory=list)
    handoff: Handoff | None = None
    redacted: bool = False
    trace_id: str
    latency_ms: float
    created_at: datetime


class HealthResponse(Contract):
    status: str
    version: str
    mocks_enabled: bool
