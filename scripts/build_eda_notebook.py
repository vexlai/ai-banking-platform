"""Compatibilidad: genera el notebook EDA con scripts/build_eda.py."""
from pathlib import Path
from runpy import run_path

if __name__ == "__main__":
    run_path(str(Path(__file__).with_name("build_eda.py")), run_name="__main__")
