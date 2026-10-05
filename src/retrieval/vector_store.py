"""FAISS-backed semantic transcript retrieval (INT-02).

Loads the index persisted at ``src.data.config.FAISS_INDEX_PATH`` and serves
the top-k nearest transcripts as ``contracts.TranscriptMatch`` records for the
``similar_transcripts`` serving view. When faiss is missing or the index file
is absent, ``search`` returns an empty list instead of raising.
"""

from __future__ import annotations

import json
import re
import zlib
from pathlib import Path
from typing import Any

import numpy as np

from contracts import TranscriptMatch
from src.data.config import FAISS_INDEX_PATH, RAW_DATA_DIR
from src.telemetry.logger import get_logger

try:
    import faiss
except ImportError:
    faiss = None  # type: ignore[assignment]

logger = get_logger(__name__)

DEFAULT_TOP_K = 3
EMBEDDING_DIM = 256
DEFAULT_SOURCE_PATH = RAW_DATA_DIR / "call_transcripts.parquet"

_METADATA_SUFFIX = ".meta.json"
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

_INDEX: Any | None = None
_RECORDS: list[dict[str, str]] = []


def _token_index(token: str) -> int:
    return zlib.crc32(token.encode("utf-8")) % EMBEDDING_DIM


def _embed(text: str) -> np.ndarray:
    vector = np.zeros(EMBEDDING_DIM, dtype="float32")
    for token in _TOKEN_PATTERN.findall(text.lower()):
        vector[_token_index(token)] += 1.0
    norm = float(np.linalg.norm(vector))
    if norm:
        vector /= norm
    return vector


def _embed_many(texts: list[str]) -> np.ndarray:
    matrix = np.zeros((len(texts), EMBEDDING_DIM), dtype="float32")
    for position, text in enumerate(texts):
        matrix[position] = _embed(text)
    return matrix


def _metadata_path(index_path: Path) -> Path:
    return index_path.with_name(index_path.name + _METADATA_SUFFIX)


def _read_records(index_path: Path) -> list[dict[str, str]]:
    metadata = _metadata_path(index_path)
    if not metadata.exists():
        return []
    payload = json.loads(metadata.read_text(encoding="utf-8"))
    return list(payload.get("records", []))


def load_index(index_path: str | Path | None = None) -> Any | None:
    global _INDEX, _RECORDS
    path = Path(index_path) if index_path is not None else FAISS_INDEX_PATH
    if faiss is None:
        logger.warning(
            "faiss is not installed; semantic search returns no matches: %s", path
        )
        _INDEX, _RECORDS = None, []
        return None
    if not path.exists():
        logger.warning(
            "FAISS index not found; semantic search returns no matches: %s", path
        )
        _INDEX, _RECORDS = None, []
        return None
    try:
        index = faiss.read_index(str(path))
        records = _read_records(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load FAISS index %s: %s", path, exc)
        _INDEX, _RECORDS = None, []
        return None
    _INDEX, _RECORDS = index, records
    return index


def search(query: str, *, k: int = DEFAULT_TOP_K) -> list[TranscriptMatch]:
    if _INDEX is None:
        load_index()
    if _INDEX is None or not _RECORDS:
        logger.info(
            "Semantic transcript search served no matches: %s chars", len(query)
        )
        return []
    limit = max(1, min(k, len(_RECORDS)))
    scores, indices = _INDEX.search(_embed(query).reshape(1, -1), limit)
    matches: list[TranscriptMatch] = []
    for score, position in zip(scores[0], indices[0], strict=True):
        if position < 0 or position >= len(_RECORDS):
            continue
        record = _RECORDS[position]
        matches.append(
            TranscriptMatch(
                transcript_id=str(record.get("transcript_id", position)),
                similarity=min(1.0, max(0.0, float(score))),
                summary=str(record.get("summary", "")),
            )
        )
    return matches


def _load_transcripts(source: Path) -> list[dict[str, str]]:
    import pandas as pd

    if source.suffix.lower() == ".csv":
        frame = pd.read_csv(source)
    else:
        frame = pd.read_parquet(source)
    records: list[dict[str, str]] = []
    for position, row in frame.iterrows():
        text = str(
            row.get("transcript_text") or row.get("text") or row.get("transcript") or ""
        ).strip()
        if not text:
            continue
        records.append(
            {
                "transcript_id": str(
                    row.get("transcript_id") or row.get("call_id") or position
                ),
                "summary": str(row.get("summary") or text[:200]),
                "text": text,
            }
        )
    return records


def build_index(source_path: str | Path, index_path: str | Path) -> int:
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Transcript source not found: {source}")
    if faiss is None:
        raise RuntimeError(
            "faiss is required to build the transcript index; install requirements.txt"
        )
    records = _load_transcripts(source)
    if not records:
        raise ValueError(f"No transcript text found in {source}")
    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index.add(_embed_many([record["text"] for record in records]))
    destination = Path(index_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(destination))
    metadata = {
        "dimension": EMBEDDING_DIM,
        "records": [
            {"transcript_id": record["transcript_id"], "summary": record["summary"]}
            for record in records
        ],
    }
    _metadata_path(destination).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info(
        "Built FAISS transcript index %s: %s records", destination, len(records)
    )
    return len(records)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m src.retrieval.vector_store``."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build the FAISS transcript index (INT-02)."
    )
    parser.add_argument("--source", default=str(DEFAULT_SOURCE_PATH))
    parser.add_argument("--output", default=str(FAISS_INDEX_PATH))
    args = parser.parse_args(argv)
    count = build_index(args.source, args.output)
    logger.info("Indexed %s transcript(s)", count)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
