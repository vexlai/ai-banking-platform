"""Publish derived report views from the completed run; never invoke inference."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intake.evaluation import signatures


def main():
    out = ROOT / "reports/evaluation/intake"
    run = out / "runs/openai-luna-v1"

    def read(path):
        return json.loads(path.read_text())

    assert read(run / "config_lock.json")["signatures"] == signatures()
    baseline = read(out / "baseline_metrics.json")
    learned = {s: read(run / s / "metrics.json") for s in ("development", "test")}
    for split in learned:
        manifest = read(run / split / "run.json")
        assert manifest["attempted_cases"] == learned[split]["all"]["cases"] == 192
        assert manifest["fallback_cases"] == 0
    provenance = {
        "status": "MEASURED",
        "source_run": "runs/openai-luna-v1",
        "supersedes": "Initial NOT_MEASURED report placeholders; immutable run outputs retained",
        "limitations": "Offline authored workload; PT team-generated; not production quality or billing",
    }

    def write(name, value):
        (out / name).write_text(json.dumps(value, indent=2) + "\n")

    write("learned_metrics.json", {**provenance, **learned})
    breakdown = {}
    for language in ("all", "es", "pt"):
        b, m = baseline["test"][language], learned["test"][language]
        breakdown[language] = {
            "cases": m["cases"], "baseline": b, "learned": m,
            "full_schema_improvement_percentage_points": 100 * (
                m["full_schema_exact_match"] - b["full_schema_exact_match"]
            ),
        }
    write("language_breakdown.json", {**provenance, **breakdown})
    write("comparison.json", {
        **provenance, "test": breakdown,
        "interpretation": "Higher full-schema and clarification accuracy, slower and two raw hallucinated fields versus zero baseline. Both rejected before delivery. No universal superiority claim.",
    })
    probe = read(out / "openai_luna_compatibility_probe.json")["metadata"]["estimated_cost_usd"]
    costs = {s: learned[s]["all"]["latency_cost"] for s in learned}
    total = probe + sum(c["estimated_total_usd"] for c in costs.values())
    assert total <= 2
    write("latency_cost.json", {
        **provenance, "baseline_test": baseline["test"]["all"]["latency_cost"],
        "learned": costs, "probe_estimated_usd": probe,
        "total_inference_calls": 385, "total_estimated_usd": total,
        "authorized_budget_usd": 2, "unknown_cost_cases": 0,
        "note": "Tariff estimate, not invoice; no new inference in report generation.",
    })
    errors = read(run / "test/errors.json")
    lines = ["# Intake error analysis", "", "Completed run: openai-luna-v1. TEST was scored once after configuration freeze; no post-test tuning.", "", "## Raw model errors (192 TEST cases; overlapping categories)", ""]
    lines += [f"- {k}: {v}" for k, v in errors["categories"].items()]
    lines += ["", "Two unsupported transaction_type_hint values occurred in ES; both complete outputs were rejected. Raw hallucination: 2/1,056 unknown slots; delivered: 0/1,056. Delivered amount errors include the two rejected outputs (18 versus 16 raw).", "", "Baseline per split: 36 amount, 12 currency, 12 intent errors and 12 clarification false positives (overlapping). Learned clarification: 192/192 correct. ES full-schema 86/96; PT 81/96. PT is team-generated, not observed banking behavior.", "", "## Sanitized references", ""]
    lines += [f"- {r['case_id']} ({r['language']}): {', '.join(r['categories'])}" for r in errors["sanitized_references"][:12]]
    lines += ["", "These references point to synthetic fixtures, not customer transcripts. Conservative gates can reject legitimate paraphrases. This sample does not certify prompt-injection robustness or production performance.", ""]
    (out / "error_analysis.md").write_text("\n".join(lines))
    print(json.dumps({"reports": "published", "total_estimated_usd": total, "inference_calls_this_command": 0}))


if __name__ == "__main__":
    main()
