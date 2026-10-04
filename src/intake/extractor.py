"""Versioned extraction boundary; baseline is imported, never rewritten."""

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from time import perf_counter
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.evaluation.baseline_intake_parser import (
    VERSION,
    extract,
    normalize,
    parse_amount,
)
from src.intake.schema import StructuredIntake

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = Path(__file__).with_name("prompt_v1.txt")
SCHEMA_PATH = ROOT / "artifacts/evaluation/intake_output.schema.json"
PROMPT_VERSION = "dispute-extraction-prompt-v1"
SCHEMA_VERSION = "dispute-intake-eval-v1"
logger = logging.getLogger("dispute.intake")


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    provider: Literal["openai-compatible"] = "openai-compatible"
    model: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    api_key_env: Literal["INTAKE_API_KEY", "OPENAI_API_KEY"] = "INTAKE_API_KEY"
    base_url: str = "https://api.openai.com/v1"
    temperature: float | None = 0
    reasoning_effort: (
        Literal["none", "low", "medium", "high", "xhigh", "max"] | None
    ) = None
    timeout_seconds: float = Field(default=20, gt=0, le=120)
    max_completion_tokens: int = Field(default=400, ge=100, le=2000)
    input_usd_per_million: float | None = Field(default=None, ge=0)
    output_usd_per_million: float | None = Field(default=None, ge=0)
    pricing_reference: str | None = None


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok", "model_error", "unsupported_output"]
    intake: StructuredIntake | None
    should_clarify: bool
    should_handoff: bool
    missing_fields: list[str]
    metadata: dict
    # Evaluation-only untrusted candidate; never HTTP serialization or telemetry.
    prediction_for_evaluation: dict | None = Field(default=None, exclude=True)


class StructuredIntakeExtractor(Protocol):
    def extract(self, text: str) -> ExtractionResult: ...


def validate_text(text):
    if not isinstance(text, str) or not 1 <= len(text) <= 4000:
        raise ValueError("Intake text must contain 1–4000 characters")


def result(intake, metadata, *, status="ok"):
    flags = (
        intake.flags()
        if intake
        else {"should_clarify": True, "should_handoff": False, "missing_fields": []}
    )
    return ExtractionResult(status=status, intake=intake, metadata=metadata, **flags)


class RegexBaselineExtractor:
    def extract(self, text):
        validate_text(text)
        start = perf_counter()
        intake = StructuredIntake.model_validate(extract(text))
        return result(
            intake,
            {
                "extractor_type": "baseline",
                "model": VERSION,
                "model_version": VERSION,
                "prompt_version": None,
                "schema_version": SCHEMA_VERSION,
                "latency_ms": (perf_counter() - start) * 1000,
                "schema_valid": True,
                "success": True,
                "token_usage": None,
                "estimated_cost_usd": 0,
                "fallback": False,
            },
        )


def unsupported_fields(text, value):
    """Conservative lexical support checks, NOT proof of meaning or truth.

    Intents/negation still need evaluation; these checks never authorize retrieval.
    No baseline substitution: unsupported output is rejected as a whole.
    """
    folded = normalize(text)
    bad = []
    if re.search(
        r"ignore (?:previous|all)|ignora (?:las|todas)|system\s*:|sistema\s*:|set\s+\w+\s*=",
        folded,
    ):
        bad.append("instruction_like_content")
    for field in ("merchant", "transaction_id"):
        clue = getattr(value, field)
        if clue is not None and normalize(clue) not in folded:
            bad.append(field)
    if value.amount is not None:
        numbers = {
            parse_amount(t)
            for t in re.findall(r"(?<![\w/-])-?\d+(?:[.,]\d+)?(?![\w/])", text)
        }
        if value.amount not in numbers:
            bad.append("amount")
    if value.currency:
        names = {
            "USD": r"us dollars|dolares estadounidenses|dolares americanos",
            "EUR": r"\beuros?\b",
            "BRL": r"\breais\b|reales brasilenos",
        }
        supported = re.search(r"\b" + re.escape(value.currency.lower()) + r"\b", folded)
        if not supported and not (
            value.currency in names and re.search(names[value.currency], folded)
        ):
            bad.append("currency")
    # Reuse established symbolic/date/type/channel vocabulary, not labels or auth context.
    literal = extract(text)
    for field in ("date_hint", "transaction_type_hint", "channel_hint"):
        if (
            getattr(value, field) is not None
            and getattr(value, field) != literal[field]
        ):
            bad.append(field)
    return bad


class LearnedStructuredExtractor:
    def __init__(self, config: ModelConfig, *, client=None):
        self.config = config
        if client is None:
            from openai import OpenAI

            key = os.environ.get(config.api_key_env)
            if not key:
                raise ValueError(
                    "Configured API credential unavailable for learned extraction"
                )
            if not config.base_url.startswith("https://"):
                raise ValueError("Learned provider requires HTTPS")
            client = OpenAI(
                api_key=key,
                base_url=config.base_url,
                timeout=config.timeout_seconds,
                max_retries=0,
            )
        self.client = client
        self.prompt = PROMPT_PATH.read_text(encoding="utf-8")
        self.schema = json.loads(SCHEMA_PATH.read_text())

    def extract(self, text):
        validate_text(text)
        start = perf_counter()
        meta = {
            "extractor_type": "learned",
            "model": self.config.model,
            "model_version": self.config.model_version,
            "provider": self.config.provider,
            "prompt_version": PROMPT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "schema_valid": False,
            "success": False,
            "token_usage": None,
            "estimated_cost_usd": None,
            "fallback": False,
        }
        intake, status = None, "model_error"
        untrusted = None
        try:
            params = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": self.prompt},
                    {"role": "user", "content": text},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "dispute_intake_v1",
                        "strict": True,
                        "schema": self.schema,
                    },
                },
                "max_completion_tokens": self.config.max_completion_tokens,
                "timeout": self.config.timeout_seconds,
                "store": False,
            }
            if self.config.temperature is not None:
                params["temperature"] = self.config.temperature
            if self.config.reasoning_effort is not None:
                params["reasoning_effort"] = self.config.reasoning_effort
            response = self.client.chat.completions.create(**params)
            meta["returned_model"] = response.model
            usage = response.usage
            if usage:
                meta["token_usage"] = {
                    "input": usage.prompt_tokens,
                    "output": usage.completion_tokens,
                }
                if (
                    self.config.input_usd_per_million is not None
                    and self.config.output_usd_per_million is not None
                ):
                    meta["estimated_cost_usd"] = (
                        usage.prompt_tokens * self.config.input_usd_per_million
                        + usage.completion_tokens * self.config.output_usd_per_million
                    ) / 1e6
            choice = response.choices[0]
            if (
                choice.finish_reason != "stop"
                or choice.message.refusal
                or choice.message.tool_calls
            ):
                raise ValueError("REFUSED_OR_INCOMPLETE")
            raw = choice.message.content or ""
            meta["response_sha256"] = hashlib.sha256(raw.encode()).hexdigest()

            def unique_keys(pairs):
                obj = {}
                for key, value in pairs:
                    if key in obj:
                        raise ValueError("DUPLICATE_JSON_KEY")
                    obj[key] = value
                return obj

            untrusted = json.loads(raw, object_pairs_hook=unique_keys)
            candidate = StructuredIntake.model_validate(untrusted)
            meta["schema_valid"] = True
            unsupported = unsupported_fields(text, candidate)
            if unsupported:
                status = "unsupported_output"
                meta["unsupported_fields"] = unsupported
            else:
                intake, status = candidate, "ok"
                meta["success"] = True
        except (ValidationError, ValueError, TypeError, IndexError):
            meta["error_code"] = "INVALID_MODEL_OUTPUT"
        except Exception as exc:  # noqa: BLE001 - provider boundary: never leak provider text/credentials
            meta["error_code"] = (
                "MODEL_TIMEOUT"
                if "timeout" in type(exc).__name__.lower()
                else "PROVIDER_FAILURE"
            )
        meta["latency_ms"] = (perf_counter() - start) * 1000
        outcome = result(intake, meta, status=status)
        if isinstance(untrusted, dict):
            outcome.prediction_for_evaluation = untrusted
        return outcome


def from_environment():
    selected = os.getenv("INTAKE_EXTRACTOR", "baseline")
    if selected == "baseline":
        return RegexBaselineExtractor()
    if selected != "learned":
        raise ValueError("INTAKE_EXTRACTOR must be baseline or learned")
    config = ModelConfig.model_validate_json(
        Path(os.environ["INTAKE_MODEL_CONFIG"]).read_text()
    )
    return LearnedStructuredExtractor(config)


def record_metadata(outcome, *, request_id, case_id, language):
    # No utterance, principal, tokens, model prose, credentials or chain-of-thought.
    logger.info(
        "intake_extraction %s",
        json.dumps(
            {
                **outcome.metadata,
                "request_id": request_id,
                "case_id": case_id,
                "input_language": language,
                "status": outcome.status,
            },
            sort_keys=True,
        ),
    )
