"""FAISS-backed semantic transcript retrieval (INT-02).

Target contract: embed ``data/call_transcripts.parquet``, persist a FAISS index,
and serve the top-k nearest transcripts as ``contracts.TranscriptMatch`` records
for the ``similar_transcripts`` serving view described in the README. Not
implemented yet: every entry point raises ``NotImplementedError``, so callers
keep falling back to the deterministic fixtures in ``src.tools.mocks``.
"""

from __future__ import annotations

from contracts import TranscriptMatch

DEFAULT_TOP_K = 3
"""Nearest transcripts returned by ``search`` (README: FAISS top-3 match)."""


def build_index(source_path: str, index_path: str) -> None:
    """Embed the transcript corpus and persist a FAISS index to ``index_path``.

    # TODO: Implement FAISS vector store over data/call_transcripts.parquet
    """
    raise NotImplementedError("INT-02: FAISS index build is not implemented yet")


def load_index(index_path: str) -> None:
    """Load a previously built FAISS index for querying.

    # TODO: Implement FAISS vector store over data/call_transcripts.parquet
    """
    raise NotImplementedError("INT-02: FAISS index loading is not implemented yet")


def search(query: str, *, k: int = DEFAULT_TOP_K) -> list[TranscriptMatch]:
    """Return the ``k`` nearest transcripts to ``query`` as contract matches.

    # TODO: Implement FAISS vector store over data/call_transcripts.parquet
    """
    raise NotImplementedError(
        "INT-02: semantic transcript search is not implemented yet"
    )
