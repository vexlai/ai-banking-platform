"""Transport-only DTOs. Domain commands, states and evidence stay authoritative."""

from datetime import datetime

from pydantic import Field

from contracts.disputes import (
    Case,
    EvidenceBundle,
    Intake,
    Search,
    Selection,
    State,
    Transaction,
    Wire,
)


class VersionCommand(Wire):
    expected_version: int = Field(ge=1, strict=True)


class SearchCommand(VersionCommand):
    query: Search


class ConfirmCommand(VersionCommand):
    selection: Selection


class IntakeClues(Wire):
    """Untrusted output of the unchanged regex baseline, not identity/authority."""

    intent: str
    transaction_id: str | None
    amount: str | None
    currency: str | None
    merchant: str | None
    date_hint: str | None
    transaction_type_hint: str | None
    channel_hint: str | None


class CaseResponse(Wire):
    case_id: str
    schema_version: str
    state: State
    version: int
    as_of_time: datetime
    intake: Intake
    extracted_clues: IntakeClues
    search: Search | None
    candidates: tuple[Transaction, ...]
    candidates_truncated: bool
    selection: Selection | None
    evidence: EvidenceBundle | None
    issue: str | None
    handoff_id: str | None

    @classmethod
    def from_case(cls, case: Case):
        # Do not serialize persistence metadata or authentication subject/provider.
        return cls.model_validate(
            {name: getattr(case, name) for name in cls.model_fields}
        )


class AuditResponse(Wire):
    """Projection of existing audit rows, never fabricated guard/AI reasoning."""

    case_id: str
    version: int
    action: str
    actor: str
    provider: str
    from_state: State | None
    to_state: State
    recorded_at: datetime


class ErrorResponse(Wire):
    code: str
    request_id: str
