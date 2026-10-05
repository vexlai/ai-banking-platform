"""Graceful-degradation tests for FAISS transcript retrieval."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.retrieval import vector_store


def test_load_index_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(vector_store, "FAISS_INDEX_PATH", tmp_path / "missing.faiss")

    assert vector_store.load_index() is None


def test_search_returns_empty_without_index(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(vector_store, "FAISS_INDEX_PATH", tmp_path / "missing.faiss")

    assert vector_store.load_index() is None
    assert vector_store.search("why was my card declined?") == []


def test_build_index_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        vector_store.build_index(tmp_path / "absent.parquet", tmp_path / "out.faiss")


def test_build_index_without_faiss_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(vector_store, "faiss", None)
    source = tmp_path / "transcripts.csv"
    source.write_text(
        "transcript_id,summary,transcript_text\n"
        "T1,Card decline,Customer reports the card was declined\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError):
        vector_store.build_index(source, tmp_path / "out.faiss")


def test_build_and_search_round_trip_from_partitioned_directory(tmp_path: Path) -> None:
    source = tmp_path / "transcripts"
    day_one = source / "year=2024" / "month=01" / "day=01"
    day_one.mkdir(parents=True)
    (day_one / "transcripts_20240101.csv").write_text(
        "transcript_id,summary,full_text\n"
        "T1,Card decline,Customer reports the card was declined at the merchant\n",
        encoding="utf-8",
    )
    day_two = source / "year=2024" / "month=01" / "day=02"
    day_two.mkdir(parents=True)
    (day_two / "transcripts_20240102.csv").write_text(
        "transcript_id,summary,full_text\n"
        "T2,Balance inquiry,Customer asks about the account balance\n",
        encoding="utf-8",
    )
    destination = tmp_path / "transcripts.faiss"

    assert vector_store.build_index(source, destination) == 2
    assert vector_store.load_index(destination) is not None

    matches = vector_store.search("card declined", k=1)

    assert matches
    assert matches[0].transcript_id == "T1"


def test_build_and_search_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "transcripts.csv"
    source.write_text(
        "transcript_id,summary,transcript_text\n"
        "T1,Card decline,Customer reports the card was declined at the merchant\n"
        "T2,Balance inquiry,Customer asks about the account balance\n",
        encoding="utf-8",
    )
    destination = tmp_path / "transcripts.faiss"

    assert vector_store.build_index(source, destination) == 2
    assert vector_store.load_index(destination) is not None

    matches = vector_store.search("card declined", k=1)

    assert matches
    assert matches[0].transcript_id == "T1"
    assert 0.0 <= matches[0].similarity <= 1.0
