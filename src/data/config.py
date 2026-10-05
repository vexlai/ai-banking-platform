import sys
from pathlib import Path

if sys.version_info < (3, 12):
    raise RuntimeError("Se requiere Python >= 3.12")

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset"  # Ubicación real inspeccionada al reanudar la tarea.
REPORTS = ROOT / "reports" / "profiling"
REFERENCE_DATE = "2026-09-28"  # Fecha de corte reproducible, no fecha máxima esperada.
EXCLUDED_LAYERS = {"raw", "interim", "processed"}

RAW_DATA_DIR = ROOT / "data" / "raw"
SERVING_DIR = ROOT / "data" / "serving"
DUCKDB_PATH = SERVING_DIR / "bank_serving.duckdb"
FAISS_INDEX_PATH = SERVING_DIR / "transcripts.faiss"
