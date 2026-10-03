"""One-time, collision-safe import of completed analytics; never edits the source."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    if source == ROOT:
        raise SystemExit("Source and destination must differ")
    plan = []
    for directory in ("notebooks", "reports", "artifacts", "scripts", "src", "tests"):
        for path in sorted((source / directory).rglob("*")):
            relative = path.relative_to(source)
            if not path.is_file() or any(p.startswith(".") or p == "__pycache__" for p in relative.parts):
                continue
            if path.suffix in {".pyc", ".log"} or relative.as_posix() == "src/__init__.py":
                continue
            plan.append((path, ROOT / relative))
    plan += [(source / "AGENTS.md", ROOT / "AGENTS.md"),
             (source / "requirements.txt", ROOT / "requirements-analytics.txt"),
             (source / "README.md", ROOT / "docs/ANALYTICS_ORIGINAL_README.md")]
    manifest_path = ROOT / "artifacts/integration/analytics_import_manifest.json"
    if manifest_path.exists():
        raise SystemExit("Import already recorded; use verification, not a second migration")
    for origin, target in plan:
        if target.exists() and sha(origin) != sha(target):
            raise SystemExit(f"Conflicting destination: {target.relative_to(ROOT)}")
    data = source / "dataset"
    link = ROOT / "dataset"
    if not data.is_dir() or link.exists() or link.is_symlink():
        raise SystemExit("Source dataset missing or destination dataset already exists")
    raw_manifest = json.loads((source / "reports/profiling/source_manifest.json").read_text())
    raw_before = {r["path"]: ((source / r["path"]).stat().st_size,
                             (source / r["path"]).stat().st_mtime_ns) for r in raw_manifest}
    original = {str(p.relative_to(ROOT)): sha(p) for p in ROOT.rglob("*")
                if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts}
    records = []
    for origin, target in plan:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(origin, target)
        records.append({"source": str(origin.relative_to(source)),
                        "destination": str(target.relative_to(ROOT)), "sha256": sha(origin)})
        assert sha(target) == records[-1]["sha256"]
    link.symlink_to(os.path.relpath(data, ROOT), target_is_directory=True)
    assert raw_before == {r["path"]: ((source / r["path"]).stat().st_size,
                                     (source / r["path"]).stat().st_mtime_ns) for r in raw_manifest}
    assert all(sha(ROOT / p) == value for p, value in original.items())
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({
        "version": "analytics-import-v1",
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "source_repository": source.name,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip(),
        "platform_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "files": records, "raw_files_stat_checked": len(raw_before),
        "dataset_link": os.readlink(link),
        "raw_copied": False, "cache_copied": False,
        "note": "Original notebooks and manifests retain historical provenance; no analyses rerun."
    }, indent=2) + "\n")
    print(f"Imported and SHA256-verified {len(records)} files; raw files untouched: {len(raw_before)}")


if __name__ == "__main__":
    main()
