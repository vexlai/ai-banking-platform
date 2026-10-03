"""Versioned dispute contracts. No authority is accepted from model/user prose."""

from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

VERSION = "dispute-case-v1"


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class State(StrEnum):
    INTAKE_INCOMPLETE = "INTAKE_INCOMPLETE"
    NO_CANDIDATE = "NO_CANDIDATE"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    OWNERSHIP_VERIFIED = "OWNERSHIP_VERIFIED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    ASSESSMENT_READY = "ASSESSMENT_READY"
    HANDOFF_RECORDED = "HANDOFF_RECORDED"


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value


class Principal(Wire):
    """Constructed only by an external credential verifier, never by a request body."""

    subject: str = Field(min_length=1, max_length=128)
    customer_id: str = Field(min_length=1, max_length=128)
    provider: str = Field(min_length=1, max_length=128)
    scopes: frozenset[str]
    verified_at: datetime
    expires_at: datetime
    _times = field_validator("verified_at", "expires_at")(aware)


class Intake(Wire):
    user_utterance: str = Field(min_length=1, max_length=4000)
    language: Literal["es", "pt"]


class Search(Wire):
    """Customer-confirmed clues, not extracted ground truth. Exact monetary matching."""

    confirmed: bool = Field(strict=True)
    transaction_id: str | None = Field(default=None, min_length=1, max_length=128)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=6)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    date: Date | None = None
    merchant: str | None = Field(default=None, min_length=1, max_length=100)
    transaction_type: str | None = Field(default=None, min_length=1, max_length=100)
    channel: str | None = Field(default=None, min_length=1, max_length=100)
    lookback_days: int = Field(default=30, ge=1, le=30, strict=True)

    @field_validator("amount", mode="before")
    @classmethod
    def decimal_only(cls, value):
        if value is not None and not isinstance(value, (str, Decimal)):
            raise ValueError("Amounts must be decimal strings or Decimal, never floats")
        return value


class Selection(Wire):
    transaction_id: str = Field(min_length=1, max_length=128)
    confirmed: bool = Field(strict=True)


class Transaction(Wire):
    transaction_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    transaction_date: datetime
    amount: Decimal = Field(max_digits=24, decimal_places=6)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    transaction_type: str
    channel: str
    transaction_status: str
    merchant_name: str | None = None
    source_ref: str = Field(min_length=1)
    # None means historical availability has NOT been certified.
    available_at: datetime | None = None

    _time = field_validator("transaction_date")(aware)

    @field_validator("available_at")
    @classmethod
    def optional_time(cls, value):
        return aware(value) if value is not None else None

    @field_validator("amount", mode="before")
    @classmethod
    def decimal_only(cls, value):
        return Search.decimal_only(value)


class SearchResult(Wire):
    candidates: tuple[Transaction, ...]
    truncated: bool = Field(strict=True)


class HistoricalContext(Wire):
    transaction_count_prior_30d: int = Field(ge=0)
    same_currency_count_prior_30d: int = Field(ge=0)
    median_amount_same_currency_prior_30d: Decimal | None
    currency: str
    window_start: datetime
    window_end_exclusive: datetime
    complete_window_observed: bool
    source_ref: str
    _times = field_validator("window_start", "window_end_exclusive")(aware)


class EvidenceBundle(Wire):
    transaction: Transaction
    ownership_verified: Literal[True]
    historical_context: HistoricalContext | None
    missing_evidence: tuple[str, ...]
    limitations: tuple[str, ...]
    as_of_time: datetime
    collected_at: datetime
    _times = field_validator("as_of_time", "collected_at")(aware)


class Case(Wire):
    schema_version: Literal["dispute-case-v1"] = VERSION
    case_id: str
    customer_id: str
    created_by: str
    state: State
    version: int = Field(ge=1)
    as_of_time: datetime
    intake: Intake
    extracted_clues: dict
    search: Search | None = None
    candidates: tuple[Transaction, ...] = ()
    candidates_truncated: bool = False
    selection: Selection | None = None
    confirmed_by: str | None = None
    evidence: EvidenceBundle | None = None
    issue: str | None = None
    handoff_id: str | None = None
    _time = field_validator("as_of_time")(aware)


class HandoffPackage(Wire):
    schema_version: Literal["dispute-case-v1"] = VERSION
    handoff_id: str
    case_id: str
    user_request: str
    authenticated_identity_reference: str
    customer_id: str
    selected_transaction_or_candidates: tuple[str, ...]
    verified_facts: dict
    evidence_references: tuple[str, ...]
    actions_taken: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    guard_results: dict[str, bool | str]
    state: Literal["HANDOFF_RECORDED"] = "HANDOFF_RECORDED"
    as_of_time: datetime
    recorded_at: datetime
    policy_status: Literal["EXTERNAL_POLICY_REQUIRED"] = "EXTERNAL_POLICY_REQUIRED"
    queue_status: Literal["LOCAL_PENDING_HUMAN_REVIEW"] = "LOCAL_PENDING_HUMAN_REVIEW"
    _times = field_validator("as_of_time", "recorded_at")(aware)
