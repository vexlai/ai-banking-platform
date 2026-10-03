"""Offline synthetic demonstration. No HTTP, live IAM, raw data, or model calls."""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.disputes import Intake, Principal, Search, Selection, Transaction
from src.cases.service import CaseService
from src.cases.store import CaseStore, Rejected
from src.cases.tools import FixtureTools


def run(path):
    now = datetime(2026, 6, 17, 12, tzinfo=timezone.utc)
    principal = Principal(
        subject="synthetic-demo-subject",
        customer_id="synthetic-customer",
        provider="OFFLINE_FIXTURE_NOT_REAL_AUTH",
        scopes=frozenset({"dispute:read", "dispute:write"}),
        verified_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=1),
    )

    def resolve(credential):
        if credential != "offline-fixture":
            raise Rejected("Invalid fixture credential")
        return principal

    transactions = [
        Transaction(
            transaction_id=f"synthetic-tx-{number}",
            customer_id=principal.customer_id,
            product_id="synthetic-product",
            transaction_date=now - timedelta(days=number),
            amount=amount,
            currency="USD",
            transaction_type="Purchase",
            channel="App",
            transaction_status="Approved",
            source_ref=f"synthetic:transaction:{number}",
        )
        for number, amount in ((1, "10.00"), (2, "20.00"), (3, "30.00"))
    ]
    tools = FixtureTools(
        transactions,
        {"synthetic-product": principal.customer_id},
        now - timedelta(days=60),
    )
    service = CaseService(CaseStore(path), tools, resolve, lambda: now)
    result = []
    for scenario in ("explicit", "ambiguous", "no_candidate"):
        case = service.create(
            "offline-fixture",
            Intake(
                user_utterance="No reconozco un cargo; solicito ayuda para investigarlo.",
                language="es",
            ),
            key=f"{scenario}:create",
        )
        query = Search(
            confirmed=True,
            transaction_id=(
                "synthetic-tx-1"
                if scenario == "explicit"
                else "synthetic-missing"
                if scenario == "no_candidate"
                else None
            ),
        )
        case = service.search(
            "offline-fixture",
            case.case_id,
            query,
            version=case.version,
            key=f"{scenario}:search",
        )
        branching = case.state.value
        if scenario == "explicit":
            case = service.confirm(
                "offline-fixture",
                case.case_id,
                Selection(transaction_id="synthetic-tx-1", confirmed=True),
                version=case.version,
                key=f"{scenario}:confirm",
            )
            case = service.collect(
                "offline-fixture",
                case.case_id,
                version=case.version,
                key=f"{scenario}:collect",
            )
        case = service.handoff(
            "offline-fixture",
            case.case_id,
            version=case.version,
            key=f"{scenario}:handoff",
        )
        result.append(
            {
                "scenario": scenario,
                "search_state": branching,
                "state": case.state.value,
                "case_id": case.case_id,
                "handoff_id": case.handoff_id,
                "audit_events": len(service.audit("offline-fixture", case.case_id)),
                "queue_status": service.get_handoff(
                    "offline-fixture", case.case_id
                ).queue_status,
            }
        )
    return {
        "source_type": "synthetic/team-generated",
        "real_authentication": False,
        "llm_calls": 0,
        "raw_data_reads": 0,
        "financial_actions": 0,
        "cases": result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / ".tmp/disputes/demo.sqlite3")
    args = parser.parse_args()
    print(json.dumps(run(args.db), indent=2))
