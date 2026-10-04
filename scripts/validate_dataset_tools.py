"""Local data-backed tool benchmark and real HTTP validation; no analytical reruns."""

import argparse
import hashlib
import json
import os
import secrets
import socket
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.disputes import Search
from src.cases.dataset_tools import TIME_POLICY, DatasetTools


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def create_validation_app():
    """Uvicorn test factory: controlled historical replay, NEVER an HTTP date input."""
    from api.dispute_configuration import from_environment
    from api.main import create_app

    service = from_environment()
    if os.getenv("DATASET_TEST_REPLAY_AS_OF"):
        as_of = datetime.fromisoformat(os.environ["DATASET_TEST_REPLAY_AS_OF"])
        original = service.resolve_principal

        def historical_principal(credential):
            principal = original(credential)
            return principal.model_copy(
                update={
                    "verified_at": as_of - timedelta(hours=1),
                    "expires_at": as_of + timedelta(hours=1),
                    "provider": "CONTROLLED_HISTORICAL_TEST_NOT_REAL_IAM",
                }
            )

        service.resolve_principal = historical_principal
        service.clock = lambda: as_of
    return create_app(service, include_legacy=False)


def validate(path: Path):
    path = path.resolve()
    before = sha(path)
    raw_manifest = json.loads(
        (ROOT / "reports/profiling/source_manifest.json").read_text()
    )
    raw_before = {
        r["path"]: (
            (ROOT / r["path"]).stat().st_size,
            (ROOT / r["path"]).stat().st_mtime_ns,
        )
        for r in raw_manifest
    }
    protected = {
        str(p.relative_to(ROOT)): sha(p)
        for base in ("artifacts", "notebooks")
        for p in (ROOT / base).rglob("*")
        if p.is_file()
    }
    tools = DatasetTools(path, time_policy=TIME_POLICY)
    end = tools._query(
        "SELECT max(transaction_date) AT TIME ZONE 'UTC' FROM transactions", []
    )[0][0].replace(tzinfo=timezone.utc)
    # Deterministic test workload, NOT complaint matching or demo customer selection.
    customers = [
        r[0]
        for r in tools._query(
            "SELECT customer_id FROM transactions WHERE transaction_date >= ? AND transaction_date <= ? "
            "GROUP BY customer_id HAVING count(*)>=2 ORDER BY customer_id LIMIT 51",
            [end - timedelta(days=30), end],
        )
    ]
    assert len(customers) == 51
    a, b = customers[:2]
    candidates = tools.search(a, end, Search(confirmed=True))
    selected = candidates.candidates[0]
    foreign = tools.search(b, end, Search(confirmed=True)).candidates[0]
    assert len(candidates.candidates) >= 2
    assert tools.get(a, selected.transaction_id, end) is not None
    assert tools.get(a, foreign.transaction_id, end) is None
    assert (
        tools.get(
            a,
            selected.transaction_id,
            selected.transaction_date - timedelta(microseconds=1),
        )
        is None
    )
    assert not tools.search(
        a,
        end,
        Search(
            confirmed=True,
            transaction_id=selected.transaction_id,
            amount=selected.amount,
            currency="ZZZ",
        ),
    ).candidates
    latencies = {}
    for customer in customers[:50]:
        target = tools.search(customer, end, Search(confirmed=True)).candidates[0]
        operations = {
            "window_search": partial(
                tools.search, customer, end, Search(confirmed=True)
            ),
            "exact_id": partial(tools.get, customer, target.transaction_id, end),
            "missing_id": partial(tools.get, customer, "validation-missing-id", end),
            "amount_currency": partial(
                tools.search,
                customer,
                end,
                Search(confirmed=True, amount=target.amount, currency=target.currency),
            ),
            "history": partial(tools.history, target, end),
        }
        for name, operation in operations.items():
            start = time.perf_counter()
            operation()
            latencies.setdefault(name, []).append((time.perf_counter() - start) * 1000)
    benchmark = {
        k: {
            "n": len(v),
            "p50_ms": statistics.median(v),
            "p95_ms": statistics.quantiles(v, n=100, method="inclusive")[94],
        }
        for k, v in latencies.items()
    }
    # Verify planner actually selects the customer ART index, not only claim pushdown.
    plan = tools._query(
        "EXPLAIN ANALYZE SELECT transaction_id FROM transactions WHERE customer_id=?",
        [a],
    )
    index_scan = "Index Scan" in str(plan)
    assert index_scan, "Customer filter did not use index"
    count = tools._query("SELECT count(*) FROM transactions", [])[0][0]
    source_hash = tools.source_sha256
    tools.close()
    scratch = ROOT / ".tmp/disputes"
    scratch.mkdir(parents=True, exist_ok=True)
    summary = []
    with tempfile.TemporaryDirectory(prefix="dataset-http-", dir=scratch) as directory:
        token_a, token_b = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        env = {
            **os.environ,
            "USE_LLM": "false",
            "USE_MOCKS": "true",
            "ENABLE_LEGACY_API": "false",
            "BANKING_TOOLS_BACKEND": "dataset",
            "BANKING_SERVING_PATH": str(path),
            "BANKING_TIME_POLICY": TIME_POLICY,
            "DISPUTE_DATASET_DEMO_MODE": "true",
            "DISPUTE_DEMO_TOKEN_A": token_a,
            "DISPUTE_DEMO_TOKEN_B": token_b,
            "DISPUTE_DEMO_CUSTOMER_A": a,
            "DISPUTE_DEMO_CUSTOMER_B": b,
        }
        for historical in (False, True):
            operational = Path(directory) / f"cases-{historical}.sqlite3"
            env["DISPUTE_DB_PATH"] = str(operational)
            env.pop("DATASET_TEST_REPLAY_AS_OF", None)
            if historical:
                env["DATASET_TEST_REPLAY_AS_OF"] = end.isoformat()
            states = {}
            with (Path(directory) / "server.log").open("w") as logs:
                for stage in ("search_before_restart", "continue_after_restart"):
                    with socket.socket() as sock:
                        sock.bind(("127.0.0.1", 0))
                        port = sock.getsockname()[1]
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "uvicorn",
                            "scripts.validate_dataset_tools:create_validation_app",
                            "--factory",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(port),
                            "--no-access-log",
                        ],
                        cwd=ROOT,
                        env=env,
                        stdout=logs,
                        stderr=logs,
                    )
                    try:
                        with httpx.Client(
                            base_url=f"http://127.0.0.1:{port}",
                            timeout=30,
                            trust_env=False,
                        ) as client:
                            for _ in range(200):
                                if process.poll() is not None:
                                    raise RuntimeError(
                                        "Dataset Uvicorn failed to start; inspect configuration"
                                    )
                                try:
                                    if client.get("/health").status_code == 200:
                                        break
                                except httpx.ConnectError:
                                    pass
                                time.sleep(0.1)
                            else:
                                raise RuntimeError("Dataset server readiness timeout")

                            def post(url, body, key):
                                response = client.post(
                                    url,
                                    json=body,
                                    headers={
                                        "Authorization": f"Bearer {token_a}",
                                        "Idempotency-Key": key,
                                    },
                                )
                                assert response.status_code in (200, 201), (
                                    response.json().get("code")
                                )
                                return response.json()

                            for scenario in ("single", "multiple", "none"):
                                if stage == "search_before_restart":
                                    case = post(
                                        "/v1/disputes",
                                        {
                                            "user_utterance": "No reconozco un cargo",
                                            "language": "es",
                                        },
                                        scenario + ":create",
                                    )
                                    query = {"confirmed": True}
                                    if scenario == "single":
                                        query["transaction_id"] = (
                                            selected.transaction_id
                                        )
                                    if scenario == "none":
                                        query["transaction_id"] = (
                                            "validation-missing-id"
                                        )
                                    case = post(
                                        f"/v1/disputes/{case['case_id']}/search",
                                        {
                                            "expected_version": case["version"],
                                            "query": query,
                                        },
                                        scenario + ":search",
                                    )
                                    expected = (
                                        "AWAITING_CONFIRMATION"
                                        if scenario == "single"
                                        else "MULTIPLE_CANDIDATES"
                                        if historical and scenario == "multiple"
                                        else "NO_CANDIDATE"
                                    )
                                    assert (
                                        case["state"] == expected
                                        and case["selection"] is None
                                    )
                                    states[scenario] = case
                                else:
                                    case = states[scenario]
                                    base = f"/v1/disputes/{case['case_id']}"
                                    restored = client.get(
                                        base,
                                        headers={"Authorization": f"Bearer {token_a}"},
                                    ).json()
                                    assert restored == case
                                    if scenario == "single":
                                        case = post(
                                            base + "/confirm",
                                            {
                                                "expected_version": case["version"],
                                                "selection": {
                                                    "transaction_id": selected.transaction_id,
                                                    "confirmed": True,
                                                },
                                            },
                                            scenario + ":confirm",
                                        )
                                        assert case["state"] == "OWNERSHIP_VERIFIED"
                                        case = post(
                                            base + "/evidence",
                                            {"expected_version": case["version"]},
                                            scenario + ":evidence",
                                        )
                                        assert case["state"] == "ASSESSMENT_READY"
                                    body = {"expected_version": case["version"]}
                                    case = post(
                                        base + "/handoff", body, scenario + ":handoff"
                                    )
                                    assert case["state"] == "HANDOFF_RECORDED"
                                    assert (
                                        post(
                                            base + "/handoff",
                                            body,
                                            scenario + ":handoff",
                                        )
                                        == case
                                    )
                                    for suffix in ("", "/audit", "/handoff"):
                                        denied = client.get(
                                            base + suffix,
                                            headers={
                                                "Authorization": f"Bearer {token_b}"
                                            },
                                        )
                                        assert (
                                            denied.status_code == 404
                                            and a not in denied.text
                                        )
                    finally:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=10)
            with sqlite3.connect(operational) as db:
                counts = {
                    t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                    for t in ("cases", "handoffs", "audit", "commands")
                }
                assert counts == {
                    "cases": 3,
                    "handoffs": 3,
                    "audit": 11,
                    "commands": 11,
                }
            summary.append(
                {
                    "clock": "historical-controlled-replay"
                    if historical
                    else "real-server-UTC",
                    "branches": {k: v["state"] for k, v in states.items()},
                    "restart_continued": True,
                    "counts": counts,
                }
            )
    assert sha(path) == before
    assert raw_before == {
        r["path"]: (
            (ROOT / r["path"]).stat().st_size,
            (ROOT / r["path"]).stat().st_mtime_ns,
        )
        for r in raw_manifest
    }
    assert all(sha(ROOT / p) == value for p, value in protected.items())
    result = {
        "status": "PASS",
        "transactions": count,
        "source_sha256": source_hash,
        "serving_sha256": before,
        "time_policy": TIME_POLICY,
        "customer_index_scan_verified": index_scan,
        "exact_cross_customer_future_currency_checks": True,
        "http": summary,
        "source_type": "real organizer data; authored request and controlled principal",
        "raw_files_metadata_unchanged": len(raw_before),
        "frozen_files_unchanged": len(protected),
    }
    output = ROOT / "reports"
    (output / "dataset_tool_validation.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    (output / "dataset_tool_benchmark.json").write_text(
        json.dumps(
            {
                "label": "local/offline warm-process benchmark, not production",
                "selection": "first 50 lexical customer IDs with >=2 transactions in last observed 30 days",
                "seed": "not sampled; deterministic SQL ordering",
                "n_requests": 250,
                "includes_startup": False,
                "concurrency": 1,
                "metrics": benchmark,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(result, indent=2))
    print(json.dumps(benchmark, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serving", type=Path, required=True)
    validate(parser.parse_args().serving)
