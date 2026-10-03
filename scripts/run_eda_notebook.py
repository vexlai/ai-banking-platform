"""Ejecuta solo notebooks/02_eda.ipynb y persiste cada celda completada."""
import fcntl
import json
import os
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("IPYTHONDIR", str(ROOT / ".ipython"))
os.environ.setdefault("JUPYTER_RUNTIME_DIR", str(ROOT / ".jupyter_runtime"))
os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
path = ROOT / "notebooks" / "02_eda.ipynb"
log = ROOT / "reports" / "eda" / "notebook_execution.log"
log.parent.mkdir(parents=True, exist_ok=True)
lock = (log.parent / ".execution.lock").open("a")
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
notebook = nbformat.read(path, as_version=4)
for cell in notebook.cells:
    if cell.cell_type == "code":
        cell.outputs = []
        cell.execution_count = None

def completed(cell, cell_index, **kwargs):
    nbformat.write(notebook, path)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(f"completed cell {cell_index}\n")
        for output in cell.get("outputs", []):
            if output.output_type == "stream":
                stream.write(output.text)

def started(cell, cell_index, **kwargs):
    with log.open("a", encoding="utf-8") as stream:
        stream.write(f"starting cell {cell_index}\n")

client = NotebookClient(notebook, kernel_name="python3", timeout=7200,
                        startup_timeout=120, iopub_timeout=180,
                        on_cell_start=started, on_cell_executed=completed,
                        resources={"metadata": {"path": str(ROOT)}})
# Use nbclient's own asynchronous manager and lifecycle, with local IPC transport.
client.km = client.create_kernel_manager()
client.km.transport = "ipc"
status_path = log.parent / "execution_status.json"
status_path.write_text(json.dumps({"status": "running"}) + "\n")
try:
    client.execute()
    status_path.write_text(json.dumps({"status": "complete", "executed_code_cells": sum(c.cell_type == "code" for c in notebook.cells)}) + "\n")
except BaseException as exc:
    status_path.write_text(json.dumps({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}) + "\n")
    raise
finally:
    nbformat.write(notebook, path)
