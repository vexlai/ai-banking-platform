"""Boot-time fetcher for the serving artifacts (Streamlit Community Cloud, Mode B)."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from src.data.config import DUCKDB_PATH, FAISS_INDEX_PATH, SERVING_DIR
from src.telemetry.logger import get_logger

logger = get_logger(__name__)

FAISS_METADATA_PATH = FAISS_INDEX_PATH.with_name(FAISS_INDEX_PATH.name + ".meta.json")


def _download(url: str, destination: Path) -> None:
    logger.info("Downloading serving artifact: %s -> %s", url, destination)
    urllib.request.urlretrieve(url, destination)


def ensure_serving_artifacts(
    duckdb_url: str = "",
    faiss_url: str = "",
    faiss_meta_url: str = "",
) -> bool:
    SERVING_DIR.mkdir(parents=True, exist_ok=True)

    if not DUCKDB_PATH.exists() and duckdb_url:
        _download(duckdb_url, DUCKDB_PATH)
    if not FAISS_INDEX_PATH.exists() and faiss_url:
        _download(faiss_url, FAISS_INDEX_PATH)
    if not FAISS_METADATA_PATH.exists() and faiss_meta_url:
        _download(faiss_meta_url, FAISS_METADATA_PATH)

    has_duckdb = DUCKDB_PATH.exists()
    has_faiss = FAISS_INDEX_PATH.exists()
    if not has_duckdb and not has_faiss:
        logger.warning(
            "Serving artifacts absent with no URLs configured: %s", SERVING_DIR
        )
    elif has_faiss and not FAISS_METADATA_PATH.exists():
        logger.warning("FAISS index without metadata sidecar: %s", FAISS_METADATA_PATH)
    else:
        logger.info("Serving artifacts present on disk: %s", SERVING_DIR)
    return has_duckdb and has_faiss
