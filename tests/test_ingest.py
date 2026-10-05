"""Relation-resolution tests for the serving build script."""

from __future__ import annotations

from pathlib import Path

from src.data import ingest


def test_resolve_relation_single_flat_csv(tmp_path: Path) -> None:
    (tmp_path / "customers.csv").write_text("customer_id\nC1\n", encoding="utf-8")

    relation = ingest._resolve_relation(tmp_path, "customers")

    assert relation is not None
    assert relation.startswith("read_csv_auto(")
    assert "hive_partitioning" not in relation


def test_resolve_relation_partitioned_csv_directory(tmp_path: Path) -> None:
    partition = tmp_path / "transactions" / "year=2024" / "month=03" / "day=10"
    partition.mkdir(parents=True)
    (partition / "transactions_20240310.csv").write_text(
        "transaction_id\nT1\n", encoding="utf-8"
    )

    relation = ingest._resolve_relation(tmp_path, "transactions")

    assert relation is not None
    assert "**/*.csv" in relation
    assert "hive_partitioning=true" in relation


def test_resolve_relation_partitioned_parquet_directory(tmp_path: Path) -> None:
    partition = tmp_path / "transactions" / "year=2024" / "month=03" / "day=10"
    partition.mkdir(parents=True)
    (partition / "part-0.parquet").write_bytes(b"")

    relation = ingest._resolve_relation(tmp_path, "transactions")

    assert relation is not None
    assert "**/*.parquet" in relation
    assert "hive_partitioning=true" in relation


def test_resolve_relation_missing_returns_none(tmp_path: Path) -> None:
    assert ingest._resolve_relation(tmp_path, "transactions") is None


def test_resolve_transcripts_source_prefers_explicit(tmp_path: Path) -> None:
    explicit = tmp_path / "custom_source"

    assert ingest._resolve_transcripts_source(tmp_path, explicit) == explicit


def test_resolve_transcripts_source_uses_partitioned_folder(tmp_path: Path) -> None:
    folder = tmp_path / "call_transcripts"
    folder.mkdir()

    assert ingest._resolve_transcripts_source(tmp_path, None) == folder


def test_resolve_transcripts_source_prefers_legacy_file(tmp_path: Path) -> None:
    legacy = tmp_path / "call_transcripts.parquet"
    legacy.write_bytes(b"")
    (tmp_path / "call_transcripts").mkdir()

    assert ingest._resolve_transcripts_source(tmp_path, None) == legacy
