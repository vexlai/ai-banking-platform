"""Read-only tool contract and controlled-fixture backend. No raw-data adapter yet."""

from datetime import timedelta, timezone
from decimal import Decimal
from statistics import median
from typing import Protocol

from contracts.disputes import HistoricalContext, Search, SearchResult, Transaction

MAX_CANDIDATES = 50


class ToolFailure(RuntimeError):
    pass


def eligible(tx: Transaction, customer_id, as_of, query: Search):
    if tx.customer_id != customer_id or tx.transaction_date > as_of:
        return False
    if tx.available_at is not None and tx.available_at > as_of:
        return False
    if query.transaction_id:
        if tx.transaction_id != query.transaction_id:
            return False
    elif tx.transaction_date < as_of - timedelta(days=query.lookback_days):
        return False
    if query.amount is not None and tx.amount != query.amount:
        return False
    for clue, field in (
        ("currency", "currency"),
        ("merchant", "merchant_name"),
        ("transaction_type", "transaction_type"),
        ("channel", "channel"),
    ):
        value = getattr(query, clue)
        if value is not None and value != getattr(tx, field):
            return False
    return (
        query.date is None
        or tx.transaction_date.astimezone(timezone.utc).date() == query.date
    )


class TransactionTools(Protocol):
    """All customer/as_of arguments come from the trusted service, not model tools."""

    def search(self, customer_id, as_of, query: Search) -> SearchResult: ...
    def get(self, customer_id, transaction_id, as_of) -> Transaction | None: ...
    def product_owner(self, product_id, as_of) -> str | None: ...
    def history(self, tx: Transaction, as_of) -> HistoricalContext: ...


class FixtureTools:
    """Synthetic tables only. NOT a banking authorization or production data service."""

    def __init__(self, transactions, product_owners, observation_start):
        records = tuple(Transaction.model_validate(t) for t in transactions)
        if len({t.transaction_id for t in records}) != len(records):
            raise ValueError("Duplicate fixture transaction IDs")
        self.transactions = {t.transaction_id: t for t in records}
        self.product_owners = dict(product_owners)
        self.observation_start = observation_start

    def search(self, customer_id, as_of, query):
        items = sorted(
            (
                t
                for t in self.transactions.values()
                if eligible(t, customer_id, as_of, query)
            ),
            key=lambda t: (t.transaction_date, t.transaction_id),
            reverse=True,
        )
        return SearchResult(
            candidates=tuple(items[:MAX_CANDIDATES]),
            truncated=len(items) > MAX_CANDIDATES,
        )

    def get(self, customer_id, transaction_id, as_of):
        tx = self.transactions.get(transaction_id)
        query = Search(confirmed=True, transaction_id=transaction_id)
        return tx if tx and eligible(tx, customer_id, as_of, query) else None

    def product_owner(self, product_id, as_of):
        return self.product_owners.get(product_id)

    def history(self, tx, as_of):
        start = tx.transaction_date - timedelta(days=30)
        prior = [
            t
            for t in self.transactions.values()
            if t.customer_id == tx.customer_id
            and start <= t.transaction_date < tx.transaction_date
            and (t.available_at is None or t.available_at < tx.transaction_date)
        ]
        amounts = [t.amount for t in prior if t.currency == tx.currency]
        return HistoricalContext(
            transaction_count_prior_30d=len(prior),
            same_currency_count_prior_30d=len(amounts),
            median_amount_same_currency_prior_30d=Decimal(median(amounts))
            if amounts
            else None,
            currency=tx.currency,
            window_start=start,
            window_end_exclusive=tx.transaction_date,
            complete_window_observed=self.observation_start <= start,
            source_ref="fixture:history:strict-prior-30d",
        )
