"""Pure wire contracts shared by every layer of the platform.

The package depends only on the standard library and `pydantic`, so `api/`,
`src/**`, `apps/`, and `evals/` can import it without pulling in application
logic. `contracts/schemas.py` is the single source of truth.
"""

from contracts.schemas import (
    CaseRecord,
    ChatRequest,
    ChatResponse,
    Contract,
    Customer360,
    Decision,
    Evidence,
    EvidenceBundle,
    Handoff,
    HealthResponse,
    Intent,
    Interaction,
    JourneyEvent,
    JourneySummary,
    RiskLevel,
    SourceTool,
    Status,
    Transaction,
    TranscriptMatch,
)

__all__ = [
    "CaseRecord",
    "ChatRequest",
    "ChatResponse",
    "Contract",
    "Customer360",
    "Decision",
    "Evidence",
    "EvidenceBundle",
    "Handoff",
    "HealthResponse",
    "Intent",
    "Interaction",
    "JourneyEvent",
    "JourneySummary",
    "RiskLevel",
    "SourceTool",
    "Status",
    "Transaction",
    "TranscriptMatch",
]
