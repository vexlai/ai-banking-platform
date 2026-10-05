"""Private offline DuckDB distribution. No raw ingestion, credentials or FAISS."""

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
NAMES = {"serving": "transactions-v1.duckdb", "analytics": "analysis.duckdb"}


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_destination(path):
    path = Path(path).resolve()
    for protected in (ROOT / "dataset", ROOT / "data/raw"):
        if path.is_relative_to(protected.resolve()):
            raise ValueError("Never write into raw/dataset")
    return path


def build(source, output, kind):
    import duckdb

    source, output = Path(source).resolve(), safe_destination(output)
    if not source.is_file() or Path(str(source) + ".wal").exists():
        raise ValueError("Require a closed/checkpointed DuckDB without WAL")
    if output.exists() or source == output:
        raise ValueError("Output must be new")
    before = source.stat()
    # Hold read-only connection throughout copying; never checkpoint/modify original.
    with duckdb.connect(str(source), read_only=True) as con:
        if kind == "serving":
            from src.cases.dataset_tools import TIME_POLICY, DatasetTools

            # Use the same connection configuration as DatasetTools in a separate validation
            # after this connection closes (DuckDB disallows differing configs).
            tables = ["transactions", "products", "customers", "serving_meta"]
        else:
            tables = [
                r[0]
                for r in con.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='main' AND table_type='BASE TABLE' ORDER BY table_name"
                ).fetchall()
            ]
            if not {"cache_info", "transactions", "products", "customers"} <= set(
                tables
            ):
                raise ValueError("Not the expected analytical cache")
        counts = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            counts[table] = con.execute(f"SELECT count(*) FROM {quoted}").fetchone()[0]
        digest = sha(source)
        manifest = {
            "format": "private-banking-bundle-v1",
            "kind": kind,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "duckdb_version": duckdb.__version__,
            "file": NAMES[kind],
            "bytes": before.st_size,
            "sha256": digest,
            "table_counts": counts,
            "classification": "PRIVATE; authorized hackathon team only; not anonymization-certified",
            "excludes": [
                "raw files",
                "auth tokens",
                "environment secrets",
                "case SQLite",
                "FAISS",
            ],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation and private permissions; failures retain .building for inspection.
        staging = output.with_name(output.name + ".building")
        fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with (
            os.fdopen(fd, "wb") as stream,
            zipfile.ZipFile(
                stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1
            ) as archive,
        ):
            archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
            archive.write(source, NAMES[kind])
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (
            after.st_size,
            after.st_mtime_ns,
        ) or sha(source) != digest:
            raise ValueError("Source changed; unpublished .building retained")
    if kind == "serving":
        tools = DatasetTools(source, time_policy=TIME_POLICY)
        tools.close()
    os.link(staging, output)  # No replacement if another writer publishes first.
    staging.unlink()
    checksum = sha(output)
    with output.with_suffix(output.suffix + ".sha256").open("x") as stream:
        stream.write(f"{checksum}  {output.name}\n")
    return {
        "bundle": output.name,
        "bytes": output.stat().st_size,
        "sha256": checksum,
        "manifest": manifest,
    }


def verify(bundle, expected_sha256):
    bundle = Path(bundle)
    if sha(bundle) != expected_sha256:
        raise ValueError("Bundle checksum mismatch")
    with zipfile.ZipFile(bundle) as archive:
        if archive.getinfo("manifest.json").file_size > 65536:
            raise ValueError("Oversized manifest")
        manifest = json.loads(archive.read("manifest.json"))
        kind = manifest.get("kind")
        name = NAMES.get(kind)
        if (
            manifest.get("format") != "private-banking-bundle-v1"
            or not name
            or manifest.get("file") != name
        ):
            raise ValueError("Unsupported bundle")
        if sorted(archive.namelist()) != sorted(["manifest.json", name]):
            raise ValueError("Unexpected or duplicate archive members")
        if archive.getinfo(name).file_size != manifest["bytes"]:
            raise ValueError("Database size mismatch")
        with archive.open(name) as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != manifest["sha256"]:
                raise ValueError("Database checksum mismatch")
    return manifest


def install(bundle, expected_sha256, destination):
    manifest = verify(bundle, expected_sha256)
    destination = safe_destination(destination)
    destination.mkdir(parents=True, exist_ok=False)
    os.chmod(destination, 0o700)
    # Fixed allowlisted basename; never extractall or trust archive paths/permissions.
    output = destination / manifest["file"]
    with zipfile.ZipFile(bundle) as archive, archive.open(manifest["file"]) as source:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            shutil.copyfileobj(source, stream, length=1024 * 1024)
    if sha(output) != manifest["sha256"]:
        raise ValueError("Installed hash mismatch; do not use this directory")
    os.chmod(output, 0o400)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"installed": str(output), "read_only": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--source", type=Path, required=True)
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--kind", choices=NAMES, required=True)
    for command in ("verify", "install"):
        child = sub.add_parser(command)
        child.add_argument("--bundle", type=Path, required=True)
        child.add_argument("--sha256", required=True)
        if command == "install":
            child.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        result = build(args.source, args.output, args.kind)
    elif args.command == "verify":
        result = verify(args.bundle, args.sha256)
    else:
        result = install(args.bundle, args.sha256, args.destination)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
