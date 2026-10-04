"""Read-only frozen workload evaluation with explicit failure and split accounting."""

import hashlib
import json
import platform
import statistics
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from src.evaluation.baseline_intake_parser import FIELDS
from src.evaluation.metrics import extraction_metrics
from src.intake.extractor import PROMPT_PATH, ROOT, SCHEMA_PATH

EVAL = ROOT / "artifacts/evaluation"
OUT = ROOT / "reports/evaluation/intake"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def workload(split):
    lock = json.loads((EVAL / "baseline_lock.json").read_text())
    path = EVAL / "dispute_intake_eval.jsonl"
    if digest(path) != lock["dataset_sha256"] or any(
        digest(ROOT / p) != h for p, h in lock["code_sha256"].items()
    ):
        raise ValueError("Frozen workload/baseline signature changed")
    cases = [json.loads(line) for line in path.read_text().splitlines()]
    groups = {
        s: {c["group_id"] for c in cases if c["split"] == s}
        for s in ("development", "test")
    }
    if groups["development"] & groups["test"]:
        raise ValueError("Group leakage")
    return [c for c in cases if c["split"] == split]


def signatures():
    paths = [
        PROMPT_PATH,
        SCHEMA_PATH,
        ROOT / "src/intake/schema.py",
        ROOT / "src/intake/extractor.py",
        Path(__file__),
        ROOT / "scripts/evaluate_intake.py",
        EVAL / "dispute_intake_eval.jsonl",
        ROOT / "src/evaluation/metrics.py",
        ROOT / "src/evaluation/baseline_intake_parser.py",
    ]
    return {
        **{str(p.relative_to(ROOT)): digest(p) for p in paths},
        "runtime:python": platform.python_version(),
        "runtime:openai": version("openai"),
        "runtime:pydantic": version("pydantic"),
    }


def predict(cases, engine, *, progress=None):
    rows = []
    for case in cases:
        # This is the only value sent to the extractor; no labels, split or principal.
        outcome = engine.extract(case["user_utterance"])
        raw = outcome.prediction_for_evaluation
        if raw is None and outcome.intake:
            raw = outcome.intake.model_dump()
        # Never persist unexpected model keys, raw prose, identity or chain-of-thought.
        raw = raw if isinstance(raw, dict) else {}
        sanitized = {
            f: raw.get(f) if isinstance(raw.get(f), str) else None for f in FIELDS
        }
        rows.append(
            {
                "case_id": case["case_id"],
                "language": case["language"],
                "source_type": case["source_type"],
                "split": case["split"],
                "prediction": outcome.intake.model_dump()
                if outcome.intake
                else dict.fromkeys(FIELDS),
                "untrusted_model_fields": sanitized,
                "status": outcome.status,
                "should_clarify": outcome.should_clarify,
                "metadata": outcome.metadata,
            }
        )
        if progress is not None:
            progress(len(rows), len(cases), outcome.status)
    return rows


def summarize(cases, rows):
    scores = {}
    for language in ("all", "es", "pt"):
        pairs = [
            (c, r)
            for c, r in zip(cases, rows, strict=True)
            if language == "all" or c["language"] == language
        ]
        if not pairs:
            continue
        gold, predicted = zip(*pairs, strict=True)
        delivered = [r["prediction"] for r in predicted]
        raw = [r["untrusted_model_fields"] for r in predicted]
        metric = extraction_metrics(gold, delivered)
        raw_metric = extraction_metrics(gold, raw)
        # Invalid JSON/schema must not become valid merely by metric normalization.
        validity = sum(r["metadata"]["schema_valid"] for r in predicted) / len(
            predicted
        )
        raw_metric["schema_valid_rate"] = validity
        raw_metric["full_schema_exact_match"] = sum(
            r["metadata"]["schema_valid"]
            and all(
                r["untrusted_model_fields"][f] == c["expected_" + f] for f in FIELDS
            )
            for c, r in pairs
        ) / len(pairs)
        metric["model_schema_valid_rate"] = validity
        metric["should_clarify_accuracy"] = sum(
            r["should_clarify"] == c["expected_should_clarify"] for c, r in pairs
        ) / len(pairs)
        missing_correct = 0
        for c, r in pairs:
            p = r["prediction"]
            missing = (
                []
                if p["transaction_id"] or p["intent"] == "unsupported_action"
                else [f for f in ("amount", "currency", "date_hint") if p[f] is None]
            )
            missing_correct += set(missing) == set(
                c["expected_missing_required_fields"]
            )
        metric["missing_required_clue_set_exact_match"] = missing_correct / len(pairs)
        metric["raw_model_extraction_before_semantic_gate"] = raw_metric
        metric["hallucination_note"] = (
            "Inspect raw_model_extraction_before_semantic_gate; rejected hallucinations are NOT erased from model scores."
        )
        latency = [r["metadata"]["latency_ms"] for r in predicted]
        costs = [r["metadata"]["estimated_cost_usd"] for r in predicted]
        known = [x for x in costs if x is not None]
        metric["latency_cost"] = {
            "attempts": len(pairs),
            "p50_ms": statistics.median(latency),
            "p95_ms": statistics.quantiles(latency, n=100, method="inclusive")[94]
            if len(latency) > 1
            else latency[0],
            "known_cost_cases": len(known),
            "unknown_cost_cases": len(costs) - len(known),
            "estimated_total_usd": sum(known) if len(known) == len(costs) else None,
            "estimated_cost_per_attempt_usd": sum(known) / len(costs)
            if len(known) == len(costs)
            else None,
        }
        metric["status_counts"] = dict(Counter(r["status"] for r in predicted))
        metric["language_source"] = (
            "synthetic/team-generated, not observed Portuguese"
            if language == "pt"
            else "frozen authored evaluation utterances"
        )
        scores[language] = metric
    return scores


def error_analysis(cases, rows):
    counts, examples = Counter(), []
    for c, r in zip(cases, rows, strict=True):
        errors = [
            f + "_extraction"
            for f in FIELDS
            if r["untrusted_model_fields"][f] != c["expected_" + f]
        ]
        if any(
            c["expected_" + f] is None and r["untrusted_model_fields"][f] is not None
            for f in FIELDS
        ):
            errors.append("hallucination")
        if r["should_clarify"] != c["expected_should_clarify"]:
            errors.append(
                "clarification_false_positive"
                if r["should_clarify"]
                else "clarification_false_negative"
            )
        if not r["metadata"]["schema_valid"]:
            errors.append("schema_or_provider_failure")
        counts.update(errors)
        if errors and len(examples) < 8:
            # References to synthetic fixture IDs; no utterance/merchant/customer text copied.
            examples.append(
                {
                    "case_id": c["case_id"],
                    "language": c["language"],
                    "categories": errors,
                }
            )
    return {"categories": dict(counts), "sanitized_references": examples}


def freeze(config, development_dir, destination):
    dev = json.loads((development_dir / "run.json").read_text())
    if dev["config"] != config.model_dump() or dev["signatures"] != signatures():
        raise ValueError("Development/config/code mismatch; rerun DEV before freeze")
    if not dev["successful_cases"]:
        raise ValueError("Cannot freeze without successful live DEV calls")
    if dev.get("returned_models") != [config.model_version]:
        raise ValueError(
            "Returned provider model does not match declared pinned version"
        )
    write(
        destination,
        {
            "config": config.model_dump(),
            "signatures": signatures(),
            "development_metrics_sha256": digest(development_dir / "metrics.json"),
            "frozen_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def consume_test(lock, ledger):
    if lock["signatures"] != signatures():
        raise ValueError("Configuration code/schema changed after freeze")
    # One immutable marker for this frozen workload, not one marker per model version.
    # Even an interrupted attempt consumes the holdout; no unrecorded retry/tuning.
    write(
        ledger,
        {
            "status": "CONSUMED_BEFORE_FIRST_CALL",
            "lock": lock,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "rule": "No subsequent prompt/model optimization presented as independent held-out testing",
        },
    )
