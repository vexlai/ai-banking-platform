"""Check frozen contracts and baseline parity without rerunning analytics or overwrites."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.baseline_intake_parser import extract
from src.evaluation.metrics import retrieval_metrics


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    manifest = json.loads(
        (ROOT / "artifacts/integration/analytics_import_manifest.json").read_text()
    )
    protected = []
    historical_discrepancies = []
    for item in manifest["files"]:
        name = item["destination"]
        path = ROOT / name
        actual = sha(path) if path.is_file() else None
        if actual != item["sha256"]:
            historical_discrepancies.append(name)
        # All exported analytical data/contracts/evaluation outputs must still match.
        if name.startswith(("artifacts/", "reports/", "evals/")):
            assert actual == item["sha256"], name
            protected.append(name)
    frozen = ROOT / "artifacts/evaluation"
    lock = json.loads((frozen / "baseline_lock.json").read_text())
    for name, digest in lock["code_sha256"].items():
        assert sha(ROOT / name) == digest, name
    assert sha(frozen / "dispute_intake_eval.jsonl") == lock["dataset_sha256"]
    assert sha(frozen / "retrieval_fixtures.jsonl") == lock["retrieval_fixtures_sha256"]
    cases = [
        json.loads(line)
        for line in (frozen / "dispute_intake_eval.jsonl").read_text().splitlines()
    ]
    saved = [
        json.loads(line)
        for line in (frozen / "baseline_predictions.jsonl").read_text().splitlines()
    ]
    assert [extract(c["user_utterance"]) for c in cases] == [
        p["prediction"] for p in saved
    ]
    fixtures = [
        json.loads(line)
        for line in (frozen / "retrieval_fixtures.jsonl").read_text().splitlines()
    ]
    metrics = json.loads((frozen / "baseline_metrics.json").read_text())
    for split in ("development", "test"):
        _, actual = retrieval_metrics([f for f in fixtures if f["split"] == split])
        assert actual == metrics["retrieval"][split]
    raw = json.loads((ROOT / "reports/profiling/source_manifest.json").read_text())
    for item in raw:
        assert (ROOT / item["path"]).stat().st_size == item["bytes"]
    print(
        json.dumps(
            {
                "frozen_scope": "PASS",
                "protected_imported_outputs": len(protected),
                "baseline_predictions_identical": len(cases),
                "retrieval_fixtures_identical": len(fixtures),
                "raw_files_size_checked": len(raw),
                "raw_content_rehashed": False,
                "historical_import_manifest_discrepancies": historical_discrepancies,
                "limitation": "Historical import manifest is not repaired or fully passing; baseline/contracts checked separately.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
