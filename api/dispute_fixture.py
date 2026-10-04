"""Explicit local synthetic composition. No endpoint issues identities or tokens."""

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from contracts.disputes import Principal, Transaction, aware
from src.cases.service import CaseService
from src.cases.store import CaseStore, Rejected
from src.cases.tools import FixtureTools

ROOT = Path(__file__).resolve().parents[1]


def fixture_service(path: Path, token_a: str, token_b: str, anchor: datetime):
    """Reuse development A/C fixtures; translate timestamps by a server-configured offset.

    Product/type/channel/status are explicitly synthetic additions required by the
    runtime's typed fixture contract, not newly inferred banking facts.
    Anchor must remain fixed across server restarts; the AUTH clock stays live.
    """
    aware(anchor)
    if len(token_a) < 32 or len(token_b) < 32 or token_a == token_b:
        raise ValueError(
            "Two distinct fixture credentials of at least 32 characters required"
        )
    fixture_path = ROOT / "artifacts/evaluation/retrieval_fixtures.jsonl"
    fixtures = [json.loads(line) for line in fixture_path.read_text().splitlines()]
    explicit = next(
        f
        for f in fixtures
        if f["split"] == "development" and f["fixture_type"] == "A_explicit_id"
    )
    multiple = next(
        f
        for f in fixtures
        if f["group_id"] == explicit["group_id"] and f["fixture_type"] == "C_multiple"
    )
    offset = anchor - datetime.fromisoformat(explicit["request"]["as_of_time"]).replace(
        tzinfo=timezone.utc
    )
    owner_a = explicit["request"]["principal"]
    owner_b = next(
        t["owner"] for t in explicit["transactions"] if t["owner"] != owner_a
    )
    rows = {
        r["transaction_id"]: r for f in (explicit, multiple) for r in f["transactions"]
    }
    transactions = [
        Transaction(
            transaction_id=r["transaction_id"],
            customer_id=r["owner"],
            product_id=f"synthetic-product:{r['owner']}",
            transaction_date=datetime.fromisoformat(r["timestamp"]).replace(
                tzinfo=timezone.utc
            )
            + offset,
            amount=r["amount"],
            currency=r["currency"],
            transaction_type="Purchase",
            channel="App",
            transaction_status="Approved",
            source_ref=f"fixture:retrieval-v1:{explicit['group_id']}:{r['transaction_id']}:anchor:{anchor.isoformat()}",
        )
        for r in rows.values()
    ]
    resolve = local_credential_verifier(token_a, token_b, owner_a, owner_b)
    tools = FixtureTools(
        transactions,
        {f"synthetic-product:{owner}": owner for owner in (owner_a, owner_b)},
        anchor - timedelta(days=30),
    )
    return CaseService(CaseStore(path), tools, resolve)


def local_credential_verifier(token_a, token_b, owner_a, owner_b):
    """Existing one-hour LOCAL DEMO verifier; mapping is server configuration only."""
    if (
        len(token_a) < 32
        or len(token_b) < 32
        or token_a == token_b
        or owner_a == owner_b
    ):
        raise ValueError("Distinct local credentials and customers required")
    now = datetime.now(timezone.utc)
    principals = [
        Principal(
            subject=owner,
            customer_id=owner,
            provider="LOCAL_FIXTURE_NOT_PRODUCTION_IAM",
            scopes=frozenset({"dispute:read", "dispute:write"}),
            verified_at=now,
            expires_at=now + timedelta(hours=1),
        )
        for owner in (owner_a, owner_b)
    ]

    def resolve(credential):
        if isinstance(credential, str):
            for token, principal in zip((token_a, token_b), principals, strict=True):
                if secrets.compare_digest(credential.encode(), token.encode()):
                    return principal
        raise Rejected("AUTH_DENIED")

    return resolve


def from_environment():
    if os.getenv("DISPUTE_FIXTURE_MODE") != "true":
        return None  # Fail closed; no default credential or implicit principal.
    try:
        anchor = aware(datetime.fromisoformat(os.environ["DISPUTE_FIXTURE_ANCHOR"]))
        token_a = os.environ["DISPUTE_DEMO_TOKEN_A"]
        token_b = os.environ["DISPUTE_DEMO_TOKEN_B"]
    except (KeyError, ValueError):
        raise RuntimeError(
            "Explicit fixture credentials and timezone-aware anchor required"
        ) from None
    path = Path(os.getenv("DISPUTE_DB_PATH", ".tmp/disputes/http.sqlite3"))
    return fixture_service(path, token_a, token_b, anchor)
