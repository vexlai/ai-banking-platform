"""Metric and holdout protocol tests on authored tiny cases; no live model evaluation."""

import json

import pytest
from test_structured_intake import learned, output

from src.evaluation.baseline_intake_parser import FIELDS, intake_flags
from src.intake.evaluation import (
    consume_test,
    freeze,
    predict,
    signatures,
    summarize,
    write,
)
from src.intake.extractor import ModelConfig


def case():
    expected = output()
    flags = intake_flags(expected)
    return {
        "case_id": "test-only",
        "split": "development",
        "language": "pt",
        "source_type": "synthetic/team-generated",
        "user_utterance": "Não reconheço um valor",
        **{"expected_" + k: expected[k] for k in FIELDS},
        "expected_missing_fields": flags["missing_fields"],
        "expected_should_clarify": True,
        "expected_should_handoff": False,
        "expected_missing_required_fields": ["amount", "currency", "date_hint"],
    }


def test_rejected_hallucination_still_counted_and_labels_not_sent():
    engine, call = learned(output(currency="USD"))
    cases = [case()]
    rows = predict(cases, engine)
    metrics = summarize(cases, rows)["pt"]
    assert (
        metrics["raw_model_extraction_before_semantic_gate"]["hallucinated_fields"] == 1
    )
    assert metrics["full_schema_exact_match"] == 0
    assert metrics["should_clarify_accuracy"] == 1
    assert "expected_" not in json.dumps(call.call_args.kwargs)


def test_provider_failure_not_schema_valid_or_free():
    engine, _ = learned(output(), exception=TimeoutError())
    cases = [case()]
    metrics = summarize(cases, predict(cases, engine))["all"]
    assert metrics["model_schema_valid_rate"] == 0
    assert (
        metrics["raw_model_extraction_before_semantic_gate"]["full_schema_exact_match"]
        == 0
    )
    assert metrics["latency_cost"]["estimated_cost_per_attempt_usd"] is None


def test_freeze_and_holdout_one_use(tmp_path):
    config = ModelConfig(model="mock", model_version="mock-test-only")
    dev = tmp_path / "dev"
    write(
        dev / "run.json",
        {
            "config": config.model_dump(),
            "signatures": signatures(),
            "successful_cases": 1,
            "returned_models": ["mock-test-only"],
        },
    )
    write(dev / "metrics.json", {"synthetic_test_only": True})
    destination = tmp_path / "lock.json"
    freeze(config, dev, destination)
    lock = json.loads(destination.read_text())
    ledger = tmp_path / "ledger.json"
    consume_test(lock, ledger)
    with pytest.raises(FileExistsError):
        consume_test(lock, ledger)
    lock["signatures"] = {}
    with pytest.raises(ValueError, match="changed"):
        consume_test(lock, tmp_path / "second.json")
    with pytest.raises(ValueError, match="mismatch"):
        freeze(
            ModelConfig(model="different", model_version="v2"),
            dev,
            tmp_path / "other.json",
        )
