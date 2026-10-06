import os
import sys
from pathlib import Path

if sys.version_info < (3, 12):
    raise RuntimeError("Python >= 3.12 is required")

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset"

DATA_DIR = ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
SERVING_DIR = Path(os.getenv("SERVING_DATA_DIR") or DATA_DIR / "serving")
DUCKDB_PATH = SERVING_DIR / "bank_serving.duckdb"
FAISS_INDEX_PATH = SERVING_DIR / "transcripts.faiss"

ARTIFACTS_DIR = DATA_DIR / "artifacts"
REPORTS_DIR = DATA_DIR / "reports"
REPORTS = REPORTS_DIR / "profiling"

REFERENCE_DATE = "2026-09-28"
EXCLUDED_LAYERS = {"raw", "interim", "processed"}
USE_MOCKS_DEFAULT = False
