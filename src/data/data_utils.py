"""Strict reads, traceability and aggregate results; never writes to sources."""

import csv
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb

from src.data.config import DATA, EXCLUDED_LAYERS, REPORTS, ROOT


def ident(value):
    return '"' + value.replace('"', '""') + '"'


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def discover():
    groups = {}
    for entry in sorted(DATA.iterdir()):
        if entry.name in EXCLUDED_LAYERS:
            continue
        files = [entry] if entry.is_file() else sorted(entry.rglob("*.csv"))
        files = [p for p in files if p.suffix.lower() == ".csv"]
        if files:
            groups[entry.stem] = files
    return groups


def manifest():
    records = []
    for dataset, files in discover().items():
        for path in files:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            with path.open(encoding="utf-8-sig", newline="") as stream:
                header = next(csv.reader(stream))
            if len(header) != len(set(header)):
                raise ValueError(f"Duplicate columns: {path.relative_to(ROOT)}")
            records.append(
                {
                    "dataset": dataset,
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": digest,
                    "columns": header,
                }
            )
    return records


def check_previous_manifest(current):
    """Accepts a root directory relocation only when all content matches."""
    previous_path = REPORTS / "source_manifest.json"
    if not current:
        raise ValueError(f"No CSV files in {DATA.relative_to(ROOT)}")
    if not previous_path.exists():
        return
    previous = json.loads(previous_path.read_text())
    if previous == current:
        return

    def without_root(records):
        return {
            str(Path(r["path"]).relative_to(Path(r["path"]).parts[0])): {
                k: v for k, v in r.items() if k != "path"
            }
            for r in records
        }

    if without_root(previous) != without_root(current):
        raise AssertionError(
            "Sources differ from the previous manifest in content or structure"
        )
    save_json("source_manifest.previous.json", previous)
    save_json(
        "source_relocation.json",
        {
            "previous_root": str(Path(previous[0]["path"]).parts[0]),
            "current_root": str(DATA.relative_to(ROOT)),
            "files_verified": len(current),
            "sha256_unchanged": True,
            "note": "Relocation detected on resume; not performed by the analysis.",
        },
    )


def save_json(name, value):
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / name).write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def save_csv(name, records):
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not records:
        return
    with (REPORTS / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


@contextmanager
def connect():
    # A temporary on-disk database enables compression and avoids keeping the
    # large uncompressed VARCHAR table in memory buffers across many queries.
    scratch = ROOT / ".tmp"
    scratch.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="profiling-", dir=scratch) as directory:
        con = duckdb.connect(str(Path(directory) / "working.duckdb"))
        try:
            con.execute("SET memory_limit='2GB'")
            con.execute("SET threads=4")
            con.execute("SET preserve_insertion_order=false")
            yield con
        finally:
            con.close()


def load(con, files):
    """One table at a time; strings preserve IDs, leading zeros and invalid dates.

    Empty CSV cells are read as NULL. Hive columns are not inferred.
    Structure errors stop execution; no records are skipped.
    """
    paths = ",".join(literal(p) for p in files)
    con.execute("DROP TABLE IF EXISTS current_data")
    con.execute(f"""CREATE TABLE current_data AS SELECT * FROM read_csv(
        [{paths}], header=true, all_varchar=true, hive_partitioning=false,
        filename='_source_file', delim=',', quote='"', escape='"',
        strict_mode=true, ignore_errors=false, null_padding=false,
        union_by_name=false)""")
    con.execute("CHECKPOINT")
    return [
        row[0]
        for row in con.execute("DESCRIBE current_data").fetchall()
        if row[0] != "_source_file"
    ]


def verify_manifest(before):
    after = manifest()
    if before != after:
        raise AssertionError("Source files changed during the analysis")
    return {"files_verified": len(after), "sha256_unchanged": True}
