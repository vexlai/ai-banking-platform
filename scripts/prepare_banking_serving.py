"""One-time narrow indexed projection from EXISTING EDA DuckDB; originals read-only."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cases.dataset_tools import FORMAT, TIME_POLICY
from src.data_utils import literal


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(source: Path, output: Path, *, time_policy: str):
    source, output = source.resolve(), output.resolve()
    if time_policy != TIME_POLICY or not source.is_file():
        raise ValueError("Existing EDA cache and explicit time policy required")
    if output.exists() or source == output:
        raise ValueError(
            "Output must be NEW; never overwrite source or serving snapshot"
        )
    if output.is_relative_to((ROOT / "dataset").resolve()):
        raise ValueError("Serving output must not be placed inside immutable dataset")
    before = (source.stat().st_size, source.stat().st_mtime_ns)
    source_hash = sha(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve new file privately; DuckDB needs an absent file for initialization.
    # Builder refuses overwrite and publishes only after a committed validation.
    temporary = output.with_name(output.name + ".building")
    if temporary.exists():
        raise ValueError("Existing .building file requires operator inspection")
    con = duckdb.connect(str(temporary))
    os.chmod(temporary, 0o600)
    try:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='1500MB'")
        con.execute("SET TimeZone='UTC'")
        # DuckDB ATTACH cannot bind placeholders; escaped operator path, never HTTP input.
        con.execute(f"ATTACH {literal(source)} AS upstream (READ_ONLY)")
        manifest = json.loads(
            (ROOT / "reports/profiling/source_manifest.json").read_text()
        )
        signature = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest()
        for domain in ("transactions", "products", "customers"):
            row = con.execute(
                "SELECT signature FROM upstream.cache_info WHERE dataset=?", [domain]
            ).fetchone()
            if row is None or row[0].split("|")[0] != signature:
                raise ValueError(
                    f"Source cache lineage differs from profiling: {domain}"
                )
        bad = con.execute("""
            SELECT count(*) FROM upstream.transactions
            WHERE transaction_date IS NULL
               OR NOT regexp_full_match(transaction_date, '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]{1,6})?')
               OR try_cast(transaction_date AS TIMESTAMP) IS NULL
               OR amount IS NULL OR NOT regexp_full_match(amount, '[+-]?[0-9]+(\\.[0-9]{1,6})?')
               OR try_cast(amount AS DECIMAL(24,6)) IS NULL
               OR currency IS NULL OR NOT regexp_full_match(currency, '[A-Z]{3}')
               OR transaction_id IS NULL OR trim(transaction_id)=''
               OR customer_id IS NULL OR trim(customer_id)=''
               OR product_id IS NULL OR trim(product_id)=''
               OR transaction_type IS NULL OR trim(transaction_type)=''
               OR channel IS NULL OR trim(channel)=''
               OR transaction_status IS NULL OR trim(transaction_status)=''
               OR _source_file IS NULL OR regexp_extract(_source_file,'dataset/.*$')=''
        """).fetchone()[0]
        if bad:
            raise ValueError(
                f"Source rows incompatible with contract: {bad}; no repair applied"
            )
        con.execute("BEGIN TRANSACTION")
        con.execute("CREATE TABLE customers(customer_id VARCHAR PRIMARY KEY)")
        con.execute("INSERT INTO customers SELECT customer_id FROM upstream.customers")
        con.execute(
            "CREATE TABLE products(product_id VARCHAR PRIMARY KEY, customer_id VARCHAR NOT NULL)"
        )
        con.execute(
            "INSERT INTO products SELECT product_id,customer_id FROM upstream.products"
        )
        con.execute("""
            CREATE TABLE transactions(
                transaction_id VARCHAR PRIMARY KEY, customer_id VARCHAR NOT NULL,
                product_id VARCHAR NOT NULL, transaction_date TIMESTAMPTZ NOT NULL,
                amount DECIMAL(24,6) NOT NULL, currency VARCHAR NOT NULL,
                transaction_type VARCHAR NOT NULL, channel VARCHAR NOT NULL,
                transaction_status VARCHAR NOT NULL, merchant_name VARCHAR,
                source_ref VARCHAR NOT NULL, available_at TIMESTAMPTZ)
        """)
        con.execute(
            """
            INSERT INTO transactions SELECT transaction_id,customer_id,product_id,
                transaction_date::TIMESTAMP AT TIME ZONE 'UTC',amount::DECIMAL(24,6),
                currency,transaction_type,channel,transaction_status,merchant_name,
                concat('dataset:', ?, ':', regexp_extract(_source_file,'dataset/.*$'),
                       '#',transaction_id,':time-policy:',?), NULL::TIMESTAMPTZ
            FROM upstream.transactions ORDER BY customer_id,transaction_date,transaction_id
        """,
            [source_hash, TIME_POLICY],
        )
        violations = con.execute("""
            SELECT count(*) FROM transactions t
            LEFT JOIN products p ON t.product_id=p.product_id
            LEFT JOIN customers c ON t.customer_id=c.customer_id
            WHERE p.product_id IS NULL OR c.customer_id IS NULL OR p.customer_id<>t.customer_id
        """).fetchone()[0]
        product_orphans = con.execute("""
            SELECT count(*) FROM products p LEFT JOIN customers c USING(customer_id)
            WHERE c.customer_id IS NULL
        """).fetchone()[0]
        if violations or product_orphans:
            raise ValueError(
                f"Ownership/orphan violations: {violations}/{product_orphans}; no repair"
            )
        con.execute(
            "CREATE INDEX transactions_customer_idx ON transactions(customer_id)"
        )
        con.execute("""
            CREATE TABLE serving_meta(format VARCHAR,source_sha256 VARCHAR,time_policy VARCHAR,
                                      observation_start TIMESTAMPTZ)
        """)
        con.execute(
            "INSERT INTO serving_meta SELECT ?,?,?,min(transaction_date) FROM transactions",
            [FORMAT, source_hash, TIME_POLICY],
        )
        counts = dict(
            zip(
                ("transactions", "products", "customers"),
                con.execute(
                    "SELECT (SELECT count(*) FROM transactions),(SELECT count(*) FROM products),(SELECT count(*) FROM customers)"
                ).fetchone(),
                strict=True,
            )
        )
        for domain, count in counts.items():
            if (
                count
                != con.execute("SELECT count(*) FROM upstream." + domain).fetchone()[0]
            ):
                raise ValueError("Projection lost rows")
        con.execute("COMMIT")
        con.execute("CHECKPOINT")
    finally:
        con.close()
    if (
        before != (source.stat().st_size, source.stat().st_mtime_ns)
        or sha(source) != source_hash
    ):
        raise ValueError(
            "Source changed during preparation; inspect unpublished projection"
        )
    # Hard-link publication fails if target appeared concurrently, no replacement.
    os.link(temporary, output)
    temporary.unlink()
    return {
        "format": FORMAT,
        "counts": counts,
        "source_sha256": source_hash,
        "serving_bytes": output.stat().st_size,
        "time_policy": TIME_POLICY,
        "ownership_violations": violations,
        "product_orphans": product_orphans,
        "invalid_time_amount_currency": bad,
        "deduplicated_rows": 0,
        "source_unchanged_sha256": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--time-policy", required=True, choices=[TIME_POLICY])
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(args.source, args.output, time_policy=args.time_policy), indent=2
        )
    )
