"""Golden-set evaluation runner for the orchestrator engine.

Each line of `golden_cases.jsonl` is a `GoldenCase`: one chat turn plus the
contract it must satisfy. The engine runs in-process on the deterministic mock
fixtures, and the runner reports metrics (accuracy, intent
accuracy, evidence precision, escalation recall, unsupported claim rate, p95
latency). Exit code is 0 only when every case passes.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pydantic import Field

from src.orchestrator.engine import OrchestratorEngine
from src.telemetry.logger import get_logger
from src.tools.schemas import (
    ChatRequest,
    ChatResponse,
    Contract,
    Decision,
    Intent,
    RiskLevel,
    SourceTool,
)

GOLDEN_CASES_PATH = Path(__file__).with_name("golden_cases.jsonl")
RESPOND_GROUNDING_MARKER = "grounded in"

logger = get_logger(__name__)


class GoldenCase(Contract):
    id: str
    customer_id: str
    session_id: str
    message: str
    expected_decision: Decision
    expected_intent: Intent
    expected_risk_level: RiskLevel
    expected_handoff: bool
    expected_sources: list[SourceTool] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CaseResult:
    case: GoldenCase
    response: ChatResponse
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


def load_cases(path: Path = GOLDEN_CASES_PATH) -> list[GoldenCase]:
    return [
        GoldenCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _grounded(response: ChatResponse) -> bool:
    if response.decision is Decision.ESCALATE:
        return response.handoff is not None and response.handoff.handoff_id in response.reply
    if response.decision is Decision.RESPOND:
        return RESPOND_GROUNDING_MARKER in response.reply
    return bool(response.reply.strip())


def _evidence_precision(case: GoldenCase, response: ChatResponse) -> float:
    if not response.evidence:
        return 0.0
    expected = set(case.expected_sources)
    relevant = sum(1 for item in response.evidence if item.source in expected)
    return relevant / len(response.evidence)


def _failures(case: GoldenCase, response: ChatResponse) -> tuple[str, ...]:
    checks = {
        "decision": response.decision is case.expected_decision,
        "intent": response.intent is case.expected_intent,
        "handoff": (response.handoff is not None) is case.expected_handoff,
        "grounding": _grounded(response),
    }
    if response.handoff is not None:
        checks["risk_level"] = response.handoff.risk_level is case.expected_risk_level

    present = {item.source for item in response.evidence}
    missing = [source.value for source in case.expected_sources if source not in present]
    if missing:
        checks["sources"] = False

    failures = [
        f"{name} expected {_expected(case, name)} got {_actual(response, name)}"
        for name, ok in checks.items()
        if not ok
    ]
    if missing:
        failures.append(f"sources missing {missing}")
    return tuple(failures)


def _expected(case: GoldenCase, name: str) -> object:
    return {
        "decision": case.expected_decision,
        "intent": case.expected_intent,
        "handoff": case.expected_handoff,
        "risk_level": case.expected_risk_level,
        "grounding": True,
    }[name]


def _actual(response: ChatResponse, name: str) -> object:
    if name == "decision":
        return response.decision
    if name == "intent":
        return response.intent
    if name == "handoff":
        return response.handoff is not None
    if name == "risk_level":
        return response.handoff.risk_level if response.handoff else None
    return _grounded(response)


def evaluate(engine: OrchestratorEngine, case: GoldenCase) -> CaseResult:
    response = engine.process_turn(
        ChatRequest(customer_id=case.customer_id, session_id=case.session_id, message=case.message)
    )
    return CaseResult(case=case, response=response, failures=_failures(case, response))


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _percent(ratio: float) -> str:
    return f"{ratio * 100:.2f}%"


def _report(results: list[CaseResult]) -> None:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    accuracy = passed / total if total else 0.0
    intent_accuracy = (
        sum(1 for r in results if r.response.intent is r.case.expected_intent) / total
        if total
        else 0.0
    )
    precision = (
        sum(_evidence_precision(r.case, r.response) for r in results) / total if total else 0.0
    )
    escalations = [r for r in results if r.case.expected_decision is Decision.ESCALATE]
    escalation_recall = (
        sum(1 for r in escalations if r.response.decision is Decision.ESCALATE) / len(escalations)
        if escalations
        else 1.0
    )
    unsupported_rate = sum(1 for r in results if not _grounded(r.response)) / total if total else 0.0
    p95 = _p95([r.response.latency_ms for r in results]) if results else 0.0

    logger.info("Intent accuracy: %s", _percent(intent_accuracy))
    logger.info("Evidence precision: %s", _percent(precision))
    logger.info("Escalation recall: %s", _percent(escalation_recall))
    logger.info("Unsupported claim rate: %s", _percent(unsupported_rate))
    logger.info("P95 latency: %s", f"{p95:.3f} ms")
    logger.info("%s/%s PASS, %s", passed, total, _percent(accuracy))


def main() -> int:
    engine = OrchestratorEngine()
    results = [evaluate(engine, case) for case in load_cases()]

    for result in results:
        logger.info(
            "Golden case %s evaluated: decision=%s intent=%s handoff=%s passed=%s",
            result.case.id,
            result.response.decision,
            result.response.intent,
            result.response.handoff is not None,
            result.passed,
            extra={"case_id": result.case.id, "trace_id": result.response.trace_id},
        )
        for failure in result.failures:
            logger.warning("Golden case %s failed: %s", result.case.id, failure)

    _report(results)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
