"""Linear UNDERSTAND -> GATHER -> DECIDE -> RESPOND state engine."""

from __future__ import annotations

from enum import StrEnum


class State(StrEnum):
    UNDERSTAND = "understand"
    GATHER = "gather"
    DECIDE = "decide"
    RESPOND = "respond"


TRANSITIONS: dict[State, frozenset[State]] = {
    State.UNDERSTAND: frozenset({State.GATHER}),
    State.GATHER: frozenset({State.DECIDE}),
    State.DECIDE: frozenset({State.RESPOND}),
    State.RESPOND: frozenset(),
}


class InvalidTransition(RuntimeError):
    def __init__(self, current: State, target: State) -> None:
        super().__init__(f"Illegal transition: {current.value} -> {target.value}")
        self.current = current
        self.target = target


class StateMachine:
    """Guards the single-pass orchestration flow; illegal skips raise."""

    def __init__(self, initial: State = State.UNDERSTAND) -> None:
        self._state = initial

    @property
    def state(self) -> State:
        return self._state

    def can_advance(self, target: State) -> bool:
        return target in TRANSITIONS[self._state]

    def advance(self, target: State) -> State:
        if not self.can_advance(target):
            raise InvalidTransition(self._state, target)
        self._state = target
        return self._state
