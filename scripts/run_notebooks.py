"""Ejecuta únicamente 00 y 01 con el intérprete del entorno actual."""
import os
import argparse
import fcntl
from pathlib import Path
import sys

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("IPYTHONDIR", str(ROOT / ".ipython"))
os.environ.setdefault("JUPYTER_RUNTIME_DIR", str(ROOT / ".jupyter_runtime"))


def cell_done(cell, cell_index, **kwargs):
    print(f"  Celda {cell_index} ejecutada", flush=True)
    for output in cell.get("outputs", []):
        if output.output_type == "stream":
            print(output.text, end="", flush=True)
    nbformat.write(notebook, path)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--only", choices=("00", "01"), help="Reejecutar una sola etapa")
args = parser.parse_args()
lock_path = ROOT / "reports" / "profiling" / ".execution.lock"
lock_path.parent.mkdir(parents=True, exist_ok=True)
lock_stream = lock_path.open("a")
try:
    fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit("Ya hay una ejecución de notebooks activa; consultar execution.log")
for name in ("00_dataset_inventory", "01_ingestion_profiling"):
    if args.only and not name.startswith(args.only):
        continue
    path = ROOT / "notebooks" / f"{name}.ipynb"
    notebook = nbformat.read(path, as_version=4)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
            cell.metadata.pop("execution", None)
    nbformat.write(notebook, path)
    print(f"Ejecutando {name}", flush=True)
    client = NotebookClient(notebook, kernel_name="python3", timeout=7200,
                            on_cell_executed=cell_done,
                            resources={"metadata": {"path": str(ROOT)}})
    try:
        client.execute()
    finally:
        nbformat.write(notebook, path)
    print(f"Completado {name}", flush=True)

sys.path.insert(0, str(ROOT))
from src.reporting import write_summary
if all((ROOT / "reports" / "profiling" / name).exists() for name in
       ("inventory.json", "profiling.json", "inventory_integrity.json", "profiling_integrity.json")):
    write_summary()
