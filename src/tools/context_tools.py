"""DuckDB-backed context lookup tools (INT-01).

Target contract: replace the deterministic fixtures in ``src.tools.mocks`` with
live queries over the DuckDB serving views (``customer_360_view``,
``recent_transactions``, ``journey_summary``, ``interaction_history``,
``similar_transcripts``, ``open_cases``). Signatures mirror ``src.tools.mocks``
so ``src.orchestrator`` can swap the data source without touching call sites.
Not implemented yet: every entry point raises ``NotImplementedError`` until the
serving views (INT-01) and the FAISS index (INT-02) land.
"""

from __future__ import annotations

from contracts import (
    CaseRecord,
    Customer360,
    EvidenceBundle,
    Interaction,
    JourneySummary,
    Transaction,
    TranscriptMatch,
)


def get_context(customer_id: str) -> EvidenceBundle:
    """Assemble the full :class:`EvidenceBundle` for one customer.

    # TODO: Implement DuckDB context tools replacing mock responses
    """
    raise NotImplementedError("INT-01: DuckDB context tools are not implemented yet")


def get_customer_360(customer_id: str) -> Customer360:
    """Read the compact customer/segment/product profile (``customer_360_view``).

    # TODO: Implement DuckDB context tools replacing mock responses
    """
    raise NotImplementedError("INT-01: DuckDB context tools are not implemented yet")


def get_recent_transactions(customer_id: str) -> list[Transaction]:
    """Read the 30-day, status/fraud-normalized transaction window.

    # TODO: Implement DuckDB context tools replacing mock responses
    """
    raise NotImplementedError("INT-01: DuckDB context tools are not implemented yet")


def get_journey_summary(customer_id: str) -> JourneySummary:
    """Read the 24-hour digital-journey summary (``journey_summary``).

    # TODO: Implement DuckDB context tools replacing mock responses
    """
    raise NotImplementedError("INT-01: DuckDB context tools are not implemented yet")


def get_interaction_history(customer_id: str) -> list[Interaction]:
    """Read the last 5-10 customer support interactions (``interaction_history``).

    # TODO: Implement DuckDB context tools replacing mock responses
    """
    raise NotImplementedError("INT-01: DuckDB context tools are not implemented yet")


def get_similar_transcripts(customer_id: str) -> list[TranscriptMatch]:
    """Read the FAISS top-3 semantic transcript matches (``similar_transcripts``).

    # TODO: Implement DuckDB context tools replacing mock responses
    """
    raise NotImplementedError("INT-01: DuckDB context tools are not implemented yet")


def get_open_cases(customer_id: str) -> list[CaseRecord]:
    """Read active cases with SLA-breach and repeat-complaint flags (``open_cases``).

    # TODO: Implement DuckDB context tools replacing mock responses
    """
    raise NotImplementedError("INT-01: DuckDB context tools are not implemented yet")
