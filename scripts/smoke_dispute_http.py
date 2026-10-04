"""Run real loopback HTTP against Uvicorn, then restart and inspect durable effects.

Synthetic local credentials never appear in stdout/logs. No LLM or raw access.
"""

import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    scratch = ROOT / ".tmp/disputes"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="http-smoke-", dir=scratch) as directory:
        database = Path(directory) / "cases.sqlite3"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        token_a, token_b = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        env = {
            **os.environ,
            "USE_LLM": "false",
            "USE_MOCKS": "true",
            "ENABLE_LEGACY_API": "false",
            "DISPUTE_FIXTURE_MODE": "true",
            "DISPUTE_DEMO_TOKEN_A": token_a,
            "DISPUTE_DEMO_TOKEN_B": token_b,
            "DISPUTE_FIXTURE_ANCHOR": datetime.now(timezone.utc).isoformat(),
            "DISPUTE_DB_PATH": str(database),
        }
        fixtures = [
            json.loads(line)
            for line in (ROOT / "artifacts/evaluation/retrieval_fixtures.jsonl")
            .read_text()
            .splitlines()
        ]
        example = next(
            f
            for f in fixtures
            if f["split"] == "development" and f["fixture_type"] == "A_explicit_id"
        )
        transaction_id = example["request"]["transaction_id"]
        results = []
        snapshots = []
        with (Path(directory) / "server.log").open("w") as logs:
            for iteration in range(2):
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "api.main:app",
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
                        base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False
                    ) as client:
                        for _ in range(100):
                            if process.poll() is not None:
                                raise RuntimeError("Uvicorn exited before readiness")
                            try:
                                if client.get("/health").status_code == 200:
                                    break
                            except httpx.ConnectError:
                                pass
                            time.sleep(0.1)
                        else:
                            raise RuntimeError("Local Uvicorn did not become ready")
                        assert client.post("/v1/chat", json={}).status_code == 404

                        def post(path, body, key, status=200):
                            response = client.post(
                                path,
                                json=body,
                                headers={
                                    "Authorization": f"Bearer {token_a}",
                                    "Idempotency-Key": key,
                                },
                            )
                            assert response.status_code == status, response.text
                            assert response.headers["cache-control"] == "no-store"
                            assert response.headers["x-request-id"]
                            return response.json()

                        current = []
                        for scenario in ("explicit", "multiple", "none"):
                            case = post(
                                "/v1/disputes",
                                {
                                    "user_utterance": "No reconozco un cargo",
                                    "language": "es",
                                },
                                f"{scenario}:create",
                                201,
                            )
                            base = f"/v1/disputes/{case['case_id']}"
                            query = {"confirmed": True}
                            if scenario != "multiple":
                                query["transaction_id"] = (
                                    transaction_id
                                    if scenario == "explicit"
                                    else "missing"
                                )
                            case = post(
                                base + "/search",
                                {
                                    "expected_version": case["version"],
                                    "query": query,
                                },
                                f"{scenario}:search",
                            )
                            branch = case["state"]
                            expected = {
                                "explicit": "AWAITING_CONFIRMATION",
                                "multiple": "MULTIPLE_CANDIDATES",
                                "none": "NO_CANDIDATE",
                            }[scenario]
                            assert branch == expected and case["selection"] is None
                            if scenario == "explicit":
                                case = post(
                                    base + "/confirm",
                                    {
                                        "expected_version": case["version"],
                                        "selection": {
                                            "transaction_id": transaction_id,
                                            "confirmed": True,
                                        },
                                    },
                                    f"{scenario}:confirm",
                                )
                                assert case["state"] == "OWNERSHIP_VERIFIED"
                                case = post(
                                    base + "/evidence",
                                    {"expected_version": case["version"]},
                                    f"{scenario}:evidence",
                                )
                                assert case["state"] == "ASSESSMENT_READY"
                            body = {"expected_version": case["version"]}
                            case = post(base + "/handoff", body, f"{scenario}:handoff")
                            assert case["state"] == "HANDOFF_RECORDED"
                            assert (
                                post(base + "/handoff", body, f"{scenario}:handoff")
                                == case
                            )
                            for suffix in ("", "/audit", "/handoff"):
                                denied = client.get(
                                    base + suffix,
                                    headers={"Authorization": f"Bearer {token_b}"},
                                )
                                assert denied.status_code == 404
                                assert case["case_id"] not in denied.text
                            events = client.get(
                                base + "/audit",
                                headers={"Authorization": f"Bearer {token_a}"},
                            ).json()
                            assert len(events) == (5 if scenario == "explicit" else 3)
                            current.append(
                                {
                                    "scenario": scenario,
                                    "branch": branch,
                                    "case_id": case["case_id"],
                                    "handoff_id": case["handoff_id"],
                                    "state": case["state"],
                                    "audit_events": len(events),
                                }
                            )
                        results.append(current)
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                with sqlite3.connect(database) as db:
                    counts = {
                        table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                        for table in ("cases", "handoffs", "commands", "audit")
                    }
                    assert counts == {
                        "cases": 3,
                        "handoffs": 3,
                        "commands": 11,
                        "audit": 11,
                    }
                    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
                    snapshots.append(counts)
            assert results[0] == results[1] and snapshots[0] == snapshots[1]
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "transport": "real HTTP on loopback / Uvicorn",
                    "source_type": "synthetic/team-generated",
                    "server_restarts": 1,
                    "cases": results[0],
                    "sqlite_counts_after_replay": snapshots[-1],
                    "cross_customer_denials": 18,
                    "llm_calls": 0,
                    "raw_reads": 0,
                    "temporary_database_removed_after_check": True,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
