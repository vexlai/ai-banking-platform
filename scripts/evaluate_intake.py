"""Baseline replay, DEV, explicit freeze, then one held-out TEST; never changes frozen artifacts."""

import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intake.evaluation import (
    EVAL,
    OUT,
    consume_test,
    error_analysis,
    freeze,
    predict,
    signatures,
    summarize,
    workload,
    write,
)
from src.intake.extractor import (
    PROMPT_PATH,
    SCHEMA_PATH,
    LearnedStructuredExtractor,
    ModelConfig,
    RegexBaselineExtractor,
)


def baseline(*, persist=True):
    saved = {
        r["case_id"]: r["prediction"]
        for r in map(
            json.loads, (EVAL / "baseline_predictions.jsonl").read_text().splitlines()
        )
    }
    metrics, errors = {}, {}
    for split in ("development", "test"):
        cases = workload(split)
        rows = predict(cases, RegexBaselineExtractor())
        assert all(r["prediction"] == saved[r["case_id"]] for r in rows)
        metrics[split], errors[split] = (
            summarize(cases, rows),
            error_analysis(cases, rows),
        )
    if not persist:
        print(
            "PASS: 384 baseline predictions identical; frozen workload signatures verified"
        )
        return
    write(OUT / "baseline_metrics.json", metrics)
    write(OUT / "baseline_error_analysis.json", errors)
    write(
        OUT / "learned_metrics.json",
        {
            "status": "NOT_MEASURED",
            "reason": "Live provider/model configuration and credentials required; mocked tests are not learned results",
        },
    )
    write(
        OUT / "comparison.json",
        {"status": "NOT_MEASURED", "learned_outperformed_baseline": None},
    )
    write(
        OUT / "language_breakdown.json",
        {"baseline": metrics, "learned": "NOT_MEASURED", "PT": "team-generated"},
    )
    write(
        OUT / "latency_cost.json",
        {s: {l: v["latency_cost"] for l, v in m.items()} for s, m in metrics.items()},
    )


def live(split, config, directory, *, budget, lock=None):
    cases = workload(split)
    if not os.getenv(config.api_key_env):
        raise ValueError(
            "Configured API credential unavailable; no live evaluation performed"
        )
    if (
        config.input_usd_per_million is None
        or config.output_usd_per_million is None
        or not config.pricing_reference
    ):
        raise ValueError(
            "Explicit provider rates and pricing reference required for cost accounting"
        )
    # Conservative byte/token allowance plus envelope overhead, no retries. Not a billing guarantee.
    size = len(PROMPT_PATH.read_bytes()) + len(SCHEMA_PATH.read_bytes()) + 2048
    upper = (
        sum(
            (size + len(c["user_utterance"].encode()))
            * config.input_usd_per_million
            * 1.25
            + config.max_completion_tokens * config.output_usd_per_million
            for c in cases
        )
        / 1e6
    )
    if budget is None or not math.isfinite(budget) or budget <= 0 or upper > budget:
        raise ValueError(
            "Explicit evaluation budget insufficient for conservative allowance"
        )
    engine = LearnedStructuredExtractor(config)
    directory.mkdir(parents=True, exist_ok=False)
    if split == "test":
        consume_test(lock, OUT / "held_out_consumption.json")
    statuses = {}

    def progress(completed, total, status):
        statuses[status] = statuses.get(status, 0) + 1
        if completed % 16 == 0 or completed == total:
            print(
                json.dumps(
                    {
                        "split": split,
                        "completed": completed,
                        "total": total,
                        "statuses": statuses,
                    }
                ),
                flush=True,
            )

    rows = predict(cases, engine, progress=progress)
    metrics = summarize(cases, rows)
    write(directory / "predictions.json", rows)
    write(directory / "metrics.json", metrics)
    write(directory / "errors.json", error_analysis(cases, rows))
    write(
        directory / "run.json",
        {
            "split": split,
            "config": config.model_dump(),
            "signatures": signatures(),
            "successful_cases": sum(r["status"] == "ok" for r in rows),
            "attempted_cases": len(rows),
            "fallback_cases": 0,
            "returned_models": sorted(
                {
                    r["metadata"]["returned_model"]
                    for r in rows
                    if "returned_model" in r["metadata"]
                }
            ),
            "conservative_allowance_usd": upper,
        },
    )
    if split == "test":
        base = json.loads((OUT / "baseline_metrics.json").read_text())["test"]
        comparison = {
            l: {
                k: {"baseline": base[l][k], "learned": metrics[l][k]}
                for k in (
                    "full_schema_exact_match",
                    "should_clarify_accuracy",
                    "model_schema_valid_rate",
                    "missing_required_clue_set_exact_match",
                    "latency_cost",
                    "raw_model_extraction_before_semantic_gate",
                )
            }
            for l in metrics
        }
        write(directory / "comparison.json", comparison)
        # Immutable run-scoped results supersede NOT_MEASURED landing files; no silent overwrites.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["baseline", "baseline-check", "dev", "freeze", "test"]
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--run-id", default="v1")
    parser.add_argument("--max-cost-usd", type=float)
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        parser.error("Simple run ID required")
    directory = OUT / "runs" / args.run_id
    if args.command in {"baseline", "baseline-check"}:
        baseline(persist=args.command == "baseline")
        return
    if args.command == "test":
        lock = json.loads((directory / "config_lock.json").read_text())
        config = ModelConfig.model_validate(lock["config"])
        live("test", config, directory / "test", budget=args.max_cost_usd, lock=lock)
        return
    if args.config is None:
        parser.error("--config required")
    config = ModelConfig.model_validate_json(args.config.read_text())
    if args.command == "dev":
        if (OUT / "held_out_consumption.json").exists():
            raise ValueError(
                "Holdout already consumed: obtain a fresh workload before further tuning"
            )
        live("development", config, directory / "development", budget=args.max_cost_usd)
    else:
        freeze(config, directory / "development", directory / "config_lock.json")


if __name__ == "__main__":
    main()
