"""Execute only 02b, persisting outputs per cell and recording failure/completion."""
import fcntl
import json
import os
import sys
from pathlib import Path
import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/eda_transaction_dispute"
ART.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("IPYTHONDIR", str(ROOT / ".ipython"))
os.environ.setdefault("JUPYTER_RUNTIME_DIR", str(ROOT / ".jupyter_runtime"))
os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
lock = (ART / ".execution.lock").open("a")
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
path = ROOT / "notebooks/02b_transaction_dispute_eda_addendum.ipynb"
nb = nbformat.read(path, as_version=4)
for cell in nb.cells:
    if cell.cell_type == "code":
        cell.outputs = []
        cell.execution_count = None


def started(cell, cell_index, **kwargs):
    if cell.cell_type == "code":
        print(f"Starting code cell {cell_index}", flush=True)


def completed(cell, cell_index, **kwargs):
    nbformat.write(nb, path)
    if cell.cell_type == "code":
        print(f"Completed code cell {cell_index}", flush=True)
        for output in cell.get("outputs", []):
            if output.output_type == "stream":
                print(output.text, flush=True)


client = NotebookClient(nb, kernel_name="python3", timeout=7200, startup_timeout=120,
    iopub_timeout=180, on_cell_start=started, on_cell_executed=completed,
    resources={"metadata": {"path": str(ROOT)}})
client.km = client.create_kernel_manager()
client.km.transport = "ipc"
status = ART / "execution_status.json"
status.write_text(json.dumps({"status":"running"}) + "\n")
try:
    client.execute()
    status.write_text(json.dumps({"status":"complete",
        "executed_code_cells":sum(c.cell_type=="code" for c in nb.cells)}) + "\n")
except BaseException as exc:
    status.write_text(json.dumps({"status":"failed","error_type":type(exc).__name__,
                                  "error":str(exc)}) + "\n")
    raise
finally:
    nbformat.write(nb, path)
