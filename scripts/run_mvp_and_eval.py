"""Execute only canonical 04/05 with prior-output and raw-stat preservation checks."""
import fcntl
import hashlib
import json
import os
import sys
from pathlib import Path
import nbformat
from nbclient import NotebookClient

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"artifacts/evaluation"
OUT.mkdir(parents=True,exist_ok=True)
os.environ.setdefault("IPYTHONDIR",str(ROOT/".ipython"))
os.environ.setdefault("JUPYTER_RUNTIME_DIR",str(ROOT/".jupyter_runtime"))
os.environ["PATH"]=str(Path(sys.executable).parent)+os.pathsep+os.environ.get("PATH","")
lock=(OUT/".execution.lock").open("a")
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


manifest=json.loads((ROOT/"reports/profiling/source_manifest.json").read_text())
raw_before={r["path"]:((ROOT/r["path"]).stat().st_size,(ROOT/r["path"]).stat().st_mtime_ns) for r in manifest}
protected=[ROOT/"AGENTS.md"]
protected += [p for p in (ROOT/"notebooks").glob("*.ipynb") if p.name[:2] in {"00","01","02","03"}]
for directory in ["reports/profiling","reports/eda","artifacts/eda_transaction_dispute","artifacts/dispute_case_workflow"]:
    protected += [p for p in (ROOT/directory).rglob("*") if p.is_file()]
protected += [ROOT/"reports/EDA_TRANSACTION_DISPUTE_ADDENDUM.md",ROOT/"reports/DISPUTE_CASE_WORKFLOW_FINDINGS.md"]
before={str(p.relative_to(ROOT)):digest(p) for p in protected}
status=OUT/"execution_status.json"
status.write_text(json.dumps({"status":"running"})+"\n")
completed_notebooks=[]
try:
    for name in ["04_mvp_use_case_definition.ipynb","05_baseline_and_eval_dataset.ipynb"]:
        path=ROOT/"notebooks"/name
        nb=nbformat.read(path,as_version=4)
        for cell in nb.cells:
            if cell.cell_type=="code":
                cell.outputs=[]
                cell.execution_count=None
        def started(cell,cell_index,**kwargs):
            if cell.cell_type=="code":
                print(f"{name}: starting cell {cell_index}",flush=True)
        def completed(cell,cell_index,**kwargs):
            nbformat.write(nb,path)
            if cell.cell_type=="code":
                print(f"{name}: completed cell {cell_index}",flush=True)
        client=NotebookClient(nb,kernel_name="python3",timeout=7200,startup_timeout=120,iopub_timeout=180,
            on_cell_start=started,on_cell_executed=completed,resources={"metadata":{"path":str(ROOT)}})
        client.km=client.create_kernel_manager()
        client.km.transport="ipc"
        try:
            client.execute()
        finally:
            nbformat.write(nb,path)
        completed_notebooks.append({"notebook":name,"executed_cells":sum(c.cell_type=="code" for c in nb.cells)})
    assert before=={str(p.relative_to(ROOT)):digest(p) for p in protected}
    assert raw_before=={r["path"]:((ROOT/r["path"]).stat().st_size,(ROOT/r["path"]).stat().st_mtime_ns) for r in manifest}
    (OUT/"integrity.json").write_text(json.dumps({"prior_files_sha256_unchanged":len(before),
        "raw_size_mtime_unchanged":len(raw_before),"AGENTS_user_changes_preserved":True},indent=2)+"\n")
    status.write_text(json.dumps({"status":"complete","notebooks":completed_notebooks},indent=2)+"\n")
except BaseException as exc:
    status.write_text(json.dumps({"status":"failed","completed":completed_notebooks,"error":str(exc)},indent=2)+"\n")
    raise
