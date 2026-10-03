"""Allowed case commands. Evidence-dependent guards remain in the application service."""

from contracts.disputes import State
from src.cases.store import Rejected

ALLOWED_ACTIONS = {
    State.INTAKE_INCOMPLETE: frozenset({"SEARCH", "HANDOFF"}),
    State.NO_CANDIDATE: frozenset({"SEARCH", "HANDOFF"}),
    State.MULTIPLE_CANDIDATES: frozenset({"SEARCH", "CONFIRM", "HANDOFF"}),
    State.AWAITING_CONFIRMATION: frozenset({"SEARCH", "CONFIRM", "HANDOFF"}),
    State.OWNERSHIP_VERIFIED: frozenset({"COLLECT", "HANDOFF"}),
    State.INSUFFICIENT_EVIDENCE: frozenset({"SEARCH", "HANDOFF"}),
    State.ASSESSMENT_READY: frozenset({"HANDOFF"}),
    State.HANDOFF_RECORDED: frozenset(),
}


def require_action(state: State, action: str):
    if state == State.HANDOFF_RECORDED:
        raise Rejected("TERMINAL_CASE")
    if action not in {"SEARCH", "CONFIRM", "COLLECT", "HANDOFF"}:
        raise Rejected("UNKNOWN_COMMAND")
    if action not in ALLOWED_ACTIONS[state]:
        raise Rejected("INVALID_TRANSITION")
