"""Offline build script for the serving layer (INT-01 / INT-02).

Reads the raw extracts under ``RAW_DATA_DIR`` into the DuckDB serving database at
``DUCKDB_PATH`` as the six customer-context views queried by
``src.tools.context_tools``, then builds the FAISS transcript index at
``FAISS_INDEX_PATH`` from ``RAW_DATA_DIR/call_transcripts.parquet``.

Run it from the repository root::

    python -m src.data.ingest                 # full build
    python -m src.data.ingest --dry-run       # print the plan, write nothing
    python -m src.data.ingest --skip-faiss    # serving views only
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.data.config import (
    DUCKDB_PATH,
    FAISS_INDEX_PATH,
    RAW_DATA_DIR,
    REFERENCE_DATE,
)
from src.telemetry.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TRANSCRIPTS_FILE = "call_transcripts.parquet"
DEFAULT_WINDOW_DAYS = 30
DEFAULT_SESSION_HOURS = 24

SERVING_VIEWS = (
    "customer_360_view",
    "recent_transactions",
    "journey_summary",
    "interaction_history",
    "similar_transcripts",
    "open_cases",
)

# Typed zero-row stand-ins registered when a raw extract is absent, so the six
# serving objects always exist and queries then degrade to the deterministic mocks.
_SOURCE_STUBS: dict[str, dict[str, str]] = {
    "customers": {
        "customer_id": "VARCHAR",
        "first_name": "VARCHAR",
        "last_name": "VARCHAR",
        "segment": "VARCHAR",
        "country": "VARCHAR",
    },
    "products": {
        "customer_id": "VARCHAR",
        "product_type": "VARCHAR",
        "credit_limit": "DOUBLE",
        "currency": "VARCHAR",
    },
    "transactions": {
        "transaction_id": "VARCHAR",
        "customer_id": "VARCHAR",
        "amount": "DOUBLE",
        "currency": "VARCHAR",
        "merchant_name": "VARCHAR",
        "transaction_status": "VARCHAR",
        "transaction_type": "VARCHAR",
        "fraud_score": "DOUBLE",
        "transaction_date": "TIMESTAMP",
    },
    "digital_events": {
        "event_id": "VARCHAR",
        "customer_id": "VARCHAR",
        "session_id": "VARCHAR",
        "event_type": "VARCHAR",
        "status": "VARCHAR",
        "event_date": "TIMESTAMP",
    },
    "call_center_interactions": {
        "interaction_id": "VARCHAR",
        "customer_id": "VARCHAR",
        "channel": "VARCHAR",
        "interaction_type": "VARCHAR",
        "contact_reason": "VARCHAR",
        "reason_category": "VARCHAR",
        "interaction_date": "TIMESTAMP",
    },
    "call_transcripts": {
        "transcript_id": "VARCHAR",
        "customer_id": "VARCHAR",
        "interaction_id": "VARCHAR",
        "summary": "VARCHAR",
        "full_text": "VARCHAR",
        "process_date": "TIMESTAMP",
    },
    "complaints": {
        "complaint_id": "VARCHAR",
        "customer_id": "VARCHAR",
        "status": "VARCHAR",
        "priority": "VARCHAR",
        "sla_breached": "BOOLEAN",
        "is_repeat_complainer": "BOOLEAN",
        "creation_date": "TIMESTAMP",
    },
}


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _resolve_relation(raw_dir: Path, table: str) -> str | None:
    """Resolves a table to a DuckDB read expression across the common layouts."""
    single_parquet = raw_dir / f"{table}.parquet"
    if single_parquet.is_file():
        return f"read_parquet({_literal(single_parquet.as_posix())})"
    single_csv = raw_dir / f"{table}.csv"
    if single_csv.is_file():
        return f"read_csv_auto({_literal(single_csv.as_posix())})"
    directory = raw_dir / table
    if directory.is_dir():
        glob_parquet = directory.as_posix() + "/*.parquet"
        if any(directory.glob("*.parquet")):
            return f"read_parquet({_literal(glob_parquet)})"
        glob_csv = directory.as_posix() + "/*.csv"
        if any(directory.glob("*.csv")):
            return f"read_csv_auto({_literal(glob_csv)})"
    return None


def _register_sources(con, raw_dir: Path) -> dict[str, str]:
    """Registers one temp view per source table; returns the relation used per table."""
    relations: dict[str, str] = {}
    for table, stub in _SOURCE_STUBS.items():
        relation = _resolve_relation(raw_dir, table)
        if relation is None:
            logger.warning(
                "Raw source '%s' not found under %s; using an empty stub",
                table,
                raw_dir,
            )
            columns = ", ".join(
                f"CAST(NULL AS {sql_type}) AS {name}" for name, sql_type in stub.items()
            )
            con.execute(
                f"CREATE OR REPLACE TEMP VIEW {table} AS SELECT {columns} WHERE 1=0"
            )
            relations[table] = "<empty stub>"
        else:
            con.execute(
                f"CREATE OR REPLACE TEMP VIEW {table} AS SELECT * FROM {relation}"
            )
            relations[table] = relation
    return relations


def _columns(con, table: str) -> set[str]:
    return {row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()}


def _pick(columns: set[str], *candidates: str) -> str | None:
    for name in candidates:
        if name in columns:
            return name
    return None


def _customer_360_sql(cust: set[str], prod: set[str], cutoff: str) -> str:
    name_parts = [f"c.{part}" for part in ("first_name", "last_name") if part in cust]
    if name_parts:
        full_name = f"trim(concat_ws(' ', {', '.join(name_parts)}))"
    else:
        full_name = "cast(c.customer_id AS VARCHAR)"
    segment = "coalesce(c.segment, 'retail')" if "segment" in cust else "'retail'"
    country = "coalesce(c.country, 'MX')" if "country" in cust else "'MX'"
    if prod:
        type_expr = (
            "product_type" if "product_type" in prod else "cast(product_id AS VARCHAR)"
        )
        products_expr = "coalesce(p.products, [])"
        credit_expr = "coalesce(p.credit_limit, 0.0)"
        currency_expr = "coalesce(p.currency, 'USD')"
        credit_agg = "max(credit_limit::DOUBLE)" if "credit_limit" in prod else "0.0"
        if "currency" in prod and "credit_limit" in prod:
            currency_agg = "arg_max(currency, credit_limit::DOUBLE)"
        elif "currency" in prod:
            currency_agg = "any_value(currency)"
        else:
            currency_agg = "'USD'"
        aggregate = f"""
        LEFT JOIN (
            SELECT customer_id,
                   list(DISTINCT {type_expr}) AS products,
                   {credit_agg} AS credit_limit,
                   {currency_agg} AS currency
            FROM products
            GROUP BY customer_id
        ) AS p USING (customer_id)"""
    else:
        products_expr = "[]::VARCHAR[]"
        credit_expr = "0.0"
        currency_expr = "'USD'"
        aggregate = ""
    return f"""
CREATE OR REPLACE TABLE customer_360_view AS
SELECT c.customer_id AS customer_id,
       {full_name} AS full_name,
       {segment} AS segment,
       {country} AS country,
       {products_expr} AS products,
       {credit_expr} AS credit_limit,
       {currency_expr} AS currency,
       CAST(TIMESTAMP '{cutoff} 00:00:00' AS TIMESTAMP) AS as_of
FROM customers AS c{aggregate}
"""


def _recent_transactions_sql(cols: set[str], window_days: int) -> str:
    merchant = _pick(cols, "merchant_name", "merchant")
    status = _pick(cols, "transaction_status", "status", "transaction_type")
    merchant_expr = f"coalesce({merchant}, '')" if merchant else "''"
    status_expr = f"coalesce({status}, 'posted')" if status else "'posted'"
    if "fraud_score" in cols:
        fraud_expr = "coalesce(try_cast(fraud_score AS DOUBLE), 0.0)"
    else:
        fraud_expr = "0.0"
    return f"""
CREATE OR REPLACE TABLE recent_transactions AS
SELECT transaction_id AS transaction_id,
       customer_id AS customer_id,
       try_cast(amount AS DOUBLE) AS amount,
       currency AS currency,
       {merchant_expr} AS merchant,
       {status_expr} AS status,
       {fraud_expr} AS fraud_score,
       transaction_date::TIMESTAMP AS occurred_at
FROM transactions
WHERE transaction_date::TIMESTAMP > (
    SELECT max(transaction_date::TIMESTAMP) FROM transactions
) - INTERVAL '{window_days} days'
"""


def _journey_summary_sql(cols: set[str], session_hours: int) -> str:
    status = _pick(cols, "status", "event_status")
    status_expr = f"lower(coalesce({status}, 'success'))" if status else "'success'"
    return f"""
CREATE OR REPLACE TABLE journey_summary AS
WITH scoped AS (
    SELECT customer_id,
           session_id,
           event_id,
           event_type,
           {status_expr} AS status,
           event_date::TIMESTAMP AS occurred_at
    FROM digital_events
    WHERE customer_id IS NOT NULL AND session_id IS NOT NULL
),
latest AS (
    SELECT customer_id, max(occurred_at) AS latest_at
    FROM scoped
    GROUP BY customer_id
),
active_session AS (
    SELECT s.customer_id, s.session_id, max(s.occurred_at) AS session_end
    FROM scoped AS s
    JOIN latest AS l USING (customer_id)
    WHERE s.occurred_at <= l.latest_at
      AND s.occurred_at > l.latest_at - INTERVAL '{session_hours} hours'
    GROUP BY s.customer_id, s.session_id
    QUALIFY row_number() OVER (
        PARTITION BY s.customer_id ORDER BY session_end DESC
    ) = 1
),
events AS (
    SELECT s.customer_id,
           list(struct_pack(
               event_id := s.event_id,
               event_type := s.event_type,
               status := s.status,
               occurred_at := s.occurred_at
           )) AS events,
           count(*) FILTER (
               WHERE s.status IN ('error', 'failed', 'failure')
                  OR lower(coalesce(s.event_type, '')) LIKE '%error%'
           ) AS error_count,
           count(*) FILTER (
               WHERE lower(coalesce(s.event_type, '')) LIKE '%form%'
                 AND s.status NOT IN ('success', 'completed', 'ok')
           ) AS abandoned_forms,
           max(s.occurred_at) AS as_of
    FROM scoped AS s
    JOIN active_session AS x
      ON s.customer_id = x.customer_id AND s.session_id = x.session_id
    GROUP BY s.customer_id
)
SELECT e.customer_id AS customer_id,
       x.session_id AS session_id,
       {session_hours} AS window_hours,
       e.events AS events,
       e.error_count AS error_count,
       e.abandoned_forms AS abandoned_forms,
       e.as_of AS as_of
FROM events AS e
JOIN active_session AS x USING (customer_id)
"""


def _interaction_history_sql(cols: set[str]) -> str:
    channel = _pick(cols, "channel", "interaction_channel")
    channel_expr = f"coalesce({channel}, 'call')" if channel else "'call'"
    summary_sources = [
        name
        for name in ("contact_reason", "reason_category", "interaction_type")
        if name in cols
    ]
    summary_expr = (
        "coalesce(" + ", ".join([*summary_sources, "''"]) + ")"
        if summary_sources
        else "''"
    )
    return f"""
CREATE OR REPLACE TABLE interaction_history AS
SELECT interaction_id AS interaction_id,
       customer_id AS customer_id,
       {channel_expr} AS channel,
       {summary_expr} AS summary,
       interaction_date::TIMESTAMP AS occurred_at
FROM call_center_interactions
WHERE customer_id IS NOT NULL
"""


def _similar_transcripts_sql(cols: set[str]) -> str:
    if "summary" in cols and "full_text" in cols:
        summary_expr = "coalesce(summary, left(full_text, 200), '')"
    elif "summary" in cols:
        summary_expr = "coalesce(summary, '')"
    elif "full_text" in cols:
        summary_expr = "coalesce(left(full_text, 200), '')"
    else:
        summary_expr = "''"
    # Real semantic scores are computed by FAISS at request time; this view is a
    # static per-customer projection so the DuckDB tool path stays usable alone.
    return f"""
CREATE OR REPLACE TABLE similar_transcripts AS
SELECT transcript_id AS transcript_id,
       customer_id AS customer_id,
       0.0 AS similarity,
       {summary_expr} AS summary
FROM call_transcripts
WHERE customer_id IS NOT NULL
"""


def _open_cases_sql(cols: set[str]) -> str:
    priority = _pick(cols, "priority", "severity")
    if priority:
        severity_expr = (
            f"CASE lower(coalesce({priority}, '')) "
            "WHEN 'critical' THEN 'high' WHEN 'urgent' THEN 'high' "
            "WHEN 'high' THEN 'high' WHEN 'medium' THEN 'medium' "
            "WHEN 'low' THEN 'low' ELSE 'low' END"
        )
    else:
        severity_expr = "'low'"
    if "sla_breached" in cols:
        sla_expr = "coalesce(try_cast(sla_breached AS BOOLEAN), false)"
    else:
        sla_expr = "false"
    if "is_repeat_complainer" in cols:
        repeat_expr = "coalesce(try_cast(is_repeat_complainer AS BOOLEAN), false)"
    else:
        repeat_expr = "false"
    return f"""
CREATE OR REPLACE TABLE open_cases AS
SELECT complaint_id AS case_id,
       customer_id AS customer_id,
       coalesce(status, 'open') AS status,
       {severity_expr} AS severity,
       {sla_expr} AS sla_breach,
       {repeat_expr} AS repeat_complaint,
       creation_date::TIMESTAMP AS opened_at
FROM complaints
WHERE customer_id IS NOT NULL
  AND lower(coalesce(status, 'open')) NOT IN (
      'closed', 'resolved', 'cancelled', 'canceled'
  )
"""


def _build_serving_views(
    con, raw_dir: Path, *, cutoff: str, window_days: int, session_hours: int
) -> list[str]:
    """Registers the raw sources and materializes the six serving tables."""
    _register_sources(con, raw_dir)
    cols = {table: _columns(con, table) for table in _SOURCE_STUBS}
    statements = {
        "customer_360_view": _customer_360_sql(
            cols["customers"], cols["products"], cutoff
        ),
        "recent_transactions": _recent_transactions_sql(
            cols["transactions"], window_days
        ),
        "journey_summary": _journey_summary_sql(cols["digital_events"], session_hours),
        "interaction_history": _interaction_history_sql(
            cols["call_center_interactions"]
        ),
        "similar_transcripts": _similar_transcripts_sql(cols["call_transcripts"]),
        "open_cases": _open_cases_sql(cols["complaints"]),
    }
    for name in SERVING_VIEWS:
        con.execute(statements[name])
        logger.info("Serving view built: %s", name)
    return list(SERVING_VIEWS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.data.ingest",
        description="Build the DuckDB serving views and the FAISS transcript index.",
    )
    parser.add_argument("--raw-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--duckdb", type=Path, default=DUCKDB_PATH)
    parser.add_argument("--faiss", type=Path, default=FAISS_INDEX_PATH)
    parser.add_argument(
        "--transcripts",
        type=Path,
        default=None,
        help="FAISS source (default: RAW_DATA_DIR/call_transcripts.parquet).",
    )
    parser.add_argument(
        "--cutoff", default=REFERENCE_DATE, help="Reproducible as-of date."
    )
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--session-hours", type=int, default=DEFAULT_SESSION_HOURS)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the plan without writing files."
    )
    parser.add_argument(
        "--skip-faiss", action="store_true", help="Build the serving views only."
    )
    return parser


def _dry_run(args: argparse.Namespace, transcripts: Path) -> int:
    """Reports what a real build would read and write, without touching disk."""
    logger.info("Dry run: no files will be written")
    logger.info("Raw directory: %s", args.raw_dir)
    for table in _SOURCE_STUBS:
        relation = _resolve_relation(args.raw_dir, table)
        logger.info("  %-24s -> %s", table, relation or "<missing: empty stub>")
    logger.info("Serving database: %s", args.duckdb)
    logger.info("Serving views: %s", ", ".join(SERVING_VIEWS))
    faiss_state = "skipped (--skip-faiss)" if args.skip_faiss else str(args.faiss)
    logger.info("FAISS index: %s", faiss_state)
    if not args.skip_faiss:
        state = "found" if transcripts.exists() else "missing"
        logger.info("Transcript source: %s (%s)", transcripts, state)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    transcripts = args.transcripts or (args.raw_dir / DEFAULT_TRANSCRIPTS_FILE)

    if args.dry_run:
        return _dry_run(args, transcripts)

    if not args.raw_dir.exists():
        logger.error("Raw data directory not found: %s", args.raw_dir)
        return 1

    import duckdb  # local import keeps `--help` usable without the serving deps

    args.duckdb.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(args.duckdb))
    try:
        _build_serving_views(
            con,
            args.raw_dir,
            cutoff=args.cutoff,
            window_days=args.window_days,
            session_hours=args.session_hours,
        )
    finally:
        con.close()
    logger.info("Serving database written: %s", args.duckdb)

    if args.skip_faiss:
        logger.info("FAISS index build skipped (--skip-faiss)")
        return 0
    if not transcripts.exists():
        logger.error("Transcript source not found: %s", transcripts)
        return 1
    from src.retrieval import vector_store

    count = vector_store.build_index(transcripts, args.faiss)
    logger.info("FAISS index written: %s (%s transcripts)", args.faiss, count)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
