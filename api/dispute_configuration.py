"""Explicit composition selection only; API routes never know dataset or SQL details."""

import os
from pathlib import Path

from api.dispute_fixture import from_environment as fixture_environment
from api.dispute_fixture import local_credential_verifier
from src.cases.service import CaseService
from src.cases.store import CaseStore


def from_environment():
    backend = os.getenv("BANKING_TOOLS_BACKEND", "fixture")
    if backend == "fixture":
        return fixture_environment()
    if backend != "dataset":
        raise ValueError("BANKING_TOOLS_BACKEND must be fixture or dataset")
    if os.getenv("ENABLE_LEGACY_API") != "false":
        raise ValueError("Dataset demo requires ENABLE_LEGACY_API=false")
    if os.getenv("DISPUTE_DATASET_DEMO_MODE") != "true":
        raise ValueError(
            "Explicit local dataset demo configuration required; no IAM production"
        )
    try:
        source = Path(os.environ["BANKING_SERVING_PATH"])
        policy = os.environ["BANKING_TIME_POLICY"]
        resolve = local_credential_verifier(
            os.environ["DISPUTE_DEMO_TOKEN_A"],
            os.environ["DISPUTE_DEMO_TOKEN_B"],
            os.environ["DISPUTE_DEMO_CUSTOMER_A"],
            os.environ["DISPUTE_DEMO_CUSTOMER_B"],
        )
    except KeyError:
        raise ValueError(
            "Missing explicit serving path/time policy/demo identity mapping"
        ) from None
    from src.cases.dataset_tools import DatasetTools

    operational = Path(
        os.getenv("DISPUTE_DB_PATH", ".tmp/disputes/dataset-cases.sqlite3")
    )
    if operational.resolve() == source.resolve():
        raise ValueError(
            "Operational SQLite must differ from read-only banking serving"
        )
    tools = DatasetTools(
        source, time_policy=policy
    )  # Fail fast before serving requests.
    try:
        return CaseService(CaseStore(operational), tools, resolve)
    except BaseException:
        tools.close()
        raise
