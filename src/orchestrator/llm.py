"""Universal LLM provider abstraction over the mock context tools.

Speaks the OpenAI Chat Completions protocol, so it targets OpenAI (`gpt-4o-mini`)
or any compatible endpoint (`deepseek-chat` via `OPENAI_BASE_URL`). Disabled by
default: `from_env()` returns a client only when `USE_LLM` is truthy and
`OPENAI_API_KEY` is present, so tests and evals stay on the deterministic path.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from contracts import SourceTool
from src.telemetry.logger import get_logger
from src.tools import mocks

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - keeps the engine importable without the dep
    OpenAI = None  # type: ignore[assignment,misc]

logger = get_logger(__name__)

USE_LLM_ENV = "USE_LLM"
MODEL_ENV = "LLM_MODEL"
BASE_URL_ENV = "OPENAI_BASE_URL"
API_KEY_ENV = "OPENAI_API_KEY"
DEFAULT_MODEL = "gpt-4o-mini"
MAX_TOOL_ROUNDS = 4
_TRUTHY = frozenset({"1", "true", "yes", "on"})


class ToolExecutionError(RuntimeError):
    """Raised when the model asks for a tool the dispatch table cannot serve."""

    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__(f"Tool {tool_name} failed: {reason}")
        self.tool_name = tool_name


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One model-selected tool invocation, normalized from the wire format."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LLMTurn:
    """Completion content plus any tool calls the model requested for this turn."""

    content: str | None
    tool_calls: tuple[ToolCall, ...] = ()


class LLMClient(Protocol):
    """Provider-agnostic seam: one tool-enabled completion per call."""

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        tools: Sequence[Mapping[str, Any]],
    ) -> LLMTurn: ...


TOOL_HANDLERS: dict[SourceTool, Callable[[str], Any]] = {
    SourceTool.CUSTOMER_360: mocks.get_customer_360,
    SourceTool.RECENT_TRANSACTIONS: mocks.get_recent_transactions,
    SourceTool.JOURNEY_SUMMARY: mocks.get_journey_summary,
    SourceTool.INTERACTION_HISTORY: mocks.get_interaction_history,
    SourceTool.SIMILAR_TRANSCRIPTS: mocks.get_similar_transcripts,
    SourceTool.OPEN_CASES: mocks.get_open_cases,
}


def _jsonable(payload: Any) -> Any:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    if isinstance(payload, (list, tuple)):
        return [_jsonable(item) for item in payload]
    return payload


def execute_tool(name: str, arguments: Mapping[str, Any]) -> str:
    """Runs one mock tool and returns its JSON payload for a `role="tool"` message."""
    try:
        tool = SourceTool(name)
    except ValueError as exc:
        raise ToolExecutionError(name, "unknown tool") from exc
    customer_id = str(arguments.get("customer_id") or "")
    if not customer_id:
        raise ToolExecutionError(name, "missing customer_id")
    return json.dumps(
        _jsonable(TOOL_HANDLERS[tool](customer_id)), ensure_ascii=False, default=str
    )


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


class OpenAIClient:
    """Thin adapter over the OpenAI Chat Completions API for one tool-enabled turn."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        if OpenAI is None:
            raise RuntimeError(
                "The openai package is required for live LLM calls; install requirements.txt."
            )
        self._model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    @property
    def model(self) -> str:
        return self._model

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        tools: Sequence[Mapping[str, Any]],
    ) -> LLMTurn:
        request: dict[str, Any] = {"model": self._model, "messages": list(messages)}
        if tools:
            request["tools"] = [dict(tool) for tool in tools]
            request["tool_choice"] = "auto"
        completion = self._client.chat.completions.create(**request)
        message = completion.choices[0].message
        calls = tuple(
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=_parse_arguments(call.function.arguments),
            )
            for call in (message.tool_calls or ())
        )
        return LLMTurn(content=message.content, tool_calls=calls)


def _env_flag(environ: Mapping[str, str], name: str) -> bool:
    return environ.get(name, "").strip().lower() in _TRUTHY


def from_env(environ: Mapping[str, str] | None = None) -> LLMClient | None:
    """Returns a live client only when enabled and configured; otherwise `None`."""
    env = environ if environ is not None else os.environ
    if not _env_flag(env, USE_LLM_ENV):
        return None
    api_key = env.get(API_KEY_ENV)
    if not api_key:
        return None
    if OpenAI is None:
        logger.warning(
            "USE_LLM is set but the openai package is missing; using the heuristic path."
        )
        return None
    model = env.get(MODEL_ENV, DEFAULT_MODEL)
    logger.info("Live LLM enabled with model: %s", model)
    return OpenAIClient(
        model=model, api_key=api_key, base_url=env.get(BASE_URL_ENV) or None
    )
