"""Read-only indexed banking projection implementing the existing TransactionTools port."""

from datetime import timedelta, timezone
from decimal import Decimal
from pathlib import Path
from statistics import median
from threading import RLock

import duckdb

from contracts.disputes import (
    HistoricalContext,
    Search,
    SearchResult,
    Transaction,
    aware,
)
from src.cases.tools import MAX_CANDIDATES, ToolFailure

FORMAT = "banking-tools-v1"
TIME_POLICY = "naive-as-utc-explicit-assumption"
TX_COLUMNS = (
    "transaction_id",
    "customer_id",
    "product_id",
    "transaction_date",
    "amount",
    "currency",
    "transaction_type",
    "channel",
    "transaction_status",
    "merchant_name",
    "source_ref",
    "available_at",
)
SCHEMA = {
    "transactions": {
        **dict.fromkeys(
            (
                "transaction_id",
                "customer_id",
                "product_id",
                "currency",
                "transaction_type",
                "channel",
                "transaction_status",
                "merchant_name",
                "source_ref",
            ),
            "VARCHAR",
        ),
        "transaction_date": "TIMESTAMP WITH TIME ZONE",
        "available_at": "TIMESTAMP WITH TIME ZONE",
        "amount": "DECIMAL(24,6)",
    },
    "products": {"product_id": "VARCHAR", "customer_id": "VARCHAR"},
    "customers": {"customer_id": "VARCHAR"},
    "serving_meta": {
        "format": "VARCHAR",
        "source_sha256": "VARCHAR",
        "time_policy": "VARCHAR",
        "observation_start": "TIMESTAMP WITH TIME ZONE",
    },
}


class DatasetTools:
    """Immutable source; scoped parameter binding, capped candidates, exact history.

    No raw access, SQL endpoint, fraud signal, complaint link, policy or state logic.
    Product ownership is a snapshot, NOT a historical ownership reconstruction.
    """

    def __init__(self, path: Path, *, time_policy: str):
        if time_policy != TIME_POLICY:
            raise ValueError("Explicit acceptance of naive source time policy required")
        self.path = Path(path)
        if not self.path.is_file():
            raise ValueError(
                "Serving database does not exist; run prepare_banking_serving"
            )
        self._lock = RLock()
        self._con = duckdb.connect(
            str(self.path),
            read_only=True,
            config={"threads": 2, "enable_external_access": False},
        )
        try:
            self._con.execute("SET TimeZone='UTC'")
            tables = {
                r[0]
                for r in self._con.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='main' AND table_type='BASE TABLE'"
                ).fetchall()
            }
            for table, columns in SCHEMA.items():
                if table not in tables:
                    raise ValueError(f"Missing serving table: {table}")
                actual = dict(
                    self._con.execute(
                        "SELECT column_name,data_type FROM information_schema.columns WHERE table_name=? AND table_schema='main'",
                        [table],
                    ).fetchall()
                )
                if any(actual.get(name) != kind for name, kind in columns.items()):
                    raise ValueError(f"Incompatible serving schema: {table}")
            meta = self._con.execute(
                "SELECT format,source_sha256,time_policy,observation_start AT TIME ZONE 'UTC' FROM serving_meta"
            ).fetchall()
            if len(meta) != 1 or meta[0][0] != FORMAT or meta[0][2] != TIME_POLICY:
                raise ValueError("Invalid serving version/time metadata")
            self.source_sha256 = meta[0][1]
            if meta[0][3] is None:
                raise ValueError("Serving observation window missing")
            self.observation_start = meta[0][3].replace(tzinfo=timezone.utc)
            indexed = {
                r[0]
                for r in self._con.execute(
                    "SELECT index_name FROM duckdb_indexes()"
                ).fetchall()
            }
            if "transactions_customer_idx" not in indexed:
                raise ValueError("Required customer index absent")
            keys = {
                r[0]
                for r in self._con.execute(
                    "SELECT table_name FROM duckdb_constraints() WHERE constraint_type='PRIMARY KEY'"
                ).fetchall()
            }
            if not {"transactions", "products", "customers"} <= keys:
                raise ValueError("Required unique primary keys absent")
        except BaseException:
            self._con.close()
            raise

    def close(self):
        with self._lock:
            self._con.close()

    def _query(self, sql, parameters):
        try:
            with self._lock:
                return self._con.execute(sql, parameters).fetchall()
        except duckdb.Error:
            raise ToolFailure("BANKING_SOURCE_UNAVAILABLE") from None

    def search(self, customer_id, as_of, query: Search):
        as_of = aware(as_of)
        query = Search.model_validate(query)
        # Confirmation/currency sufficiency remain CaseService's guard, as with FixtureTools.
        predicates = [
            "customer_id = ?",
            "transaction_date <= ?",
            "(available_at IS NULL OR available_at <= ?)",
        ]
        parameters = [customer_id, as_of, as_of]
        if query.transaction_id:
            predicates.append("transaction_id = ?")
            parameters.append(query.transaction_id)
        else:
            predicates.append("transaction_date >= ?")
            parameters.append(as_of - timedelta(days=query.lookback_days))
        for clue, column in (
            ("amount", "amount"),
            ("currency", "currency"),
            ("merchant", "merchant_name"),
            ("transaction_type", "transaction_type"),
            ("channel", "channel"),
        ):
            value = getattr(query, clue)
            if value is not None:
                predicates.append(
                    column + " = ?"
                )  # column from constant allowlist ONLY
                parameters.append(value)
        if query.date is not None:
            predicates.append("CAST(transaction_date AT TIME ZONE 'UTC' AS DATE) = ?")
            parameters.append(query.date)
        sql = (
            "SELECT "
            + ",".join(
                (column + " AT TIME ZONE 'UTC' AS " + column)
                if column in {"transaction_date", "available_at"}
                else column
                for column in TX_COLUMNS
            )
            + " FROM transactions WHERE "
            + " AND ".join(predicates)
            + " ORDER BY transaction_date DESC, transaction_id DESC LIMIT ?"
        )
        parameters.append(MAX_CANDIDATES + 1)
        records = self._query(sql, parameters)

        def transaction(row):
            values = dict(zip(TX_COLUMNS, row, strict=True))
            for column in ("transaction_date", "available_at"):
                if values[column] is not None:
                    values[column] = values[column].replace(tzinfo=timezone.utc)
            return Transaction.model_validate(values)

        return SearchResult(
            candidates=tuple(transaction(r) for r in records[:MAX_CANDIDATES]),
            truncated=len(records) > MAX_CANDIDATES,
        )

    def get(self, customer_id, transaction_id, as_of):
        result = self.search(
            customer_id, as_of, Search(confirmed=True, transaction_id=transaction_id)
        )
        return result.candidates[0] if result.candidates else None

    def product_owner(self, product_id, as_of):
        aware(as_of)
        # Port has no customer argument. Only CaseService calls after a scoped transaction lookup.
        rows = self._query(
            "SELECT customer_id FROM products WHERE product_id = ?", [product_id]
        )
        return rows[0][0] if rows else None

    def history(self, tx: Transaction, as_of):
        aware(as_of)
        start = tx.transaction_date - timedelta(days=30)
        if tx.transaction_date > as_of:
            raise ToolFailure("FUTURE_HISTORY_TARGET")
        rows = self._query(
            "SELECT amount,currency FROM transactions WHERE customer_id = ? "
            "AND transaction_date >= ? AND transaction_date < ? "
            "AND (available_at IS NULL OR available_at < ?)",
            [tx.customer_id, start, tx.transaction_date, tx.transaction_date],
        )
        # Bounded customer/window slice, not a dataframe or event-table materialization.
        # Python Decimal median preserves half-unit precision exactly like FixtureTools.
        amounts = [r[0] for r in rows if r[1] == tx.currency]
        return HistoricalContext(
            transaction_count_prior_30d=len(rows),
            same_currency_count_prior_30d=len(amounts),
            median_amount_same_currency_prior_30d=Decimal(median(amounts))
            if amounts
            else None,
            currency=tx.currency,
            window_start=start,
            window_end_exclusive=tx.transaction_date,
            complete_window_observed=self.observation_start <= start,
            source_ref=f"dataset:{self.source_sha256}:history:strict-prior-30d:{TIME_POLICY}",
        )
