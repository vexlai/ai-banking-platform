"""Reproducible summary of stored metrics; does not query or modify raw data."""

import json
from src.data.config import REPORTS


def table(headers, rows):
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        + ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    )


def write_summary():
    inventory = json.loads((REPORTS / "inventory.json").read_text())
    profile = json.loads((REPORTS / "profiling.json").read_text())
    columns = profile["columns"]
    lines = [
        "# Inventory and ingestion: results",
        "",
        "Completed scope: 00 and 01. No EDA, cleaning, imputation or modeling was performed.",
        "",
        "## Datasets",
        "",
        table(
            ["Dataset", "CSV files", "Rows", "Columns", "Bytes", "MiB"],
            [
                (
                    d["dataset"],
                    d["files"],
                    d["rows"],
                    d["columns"],
                    d["bytes"],
                    f"{d['bytes'] / 2**20:.2f}",
                )
                for d in inventory["datasets"]
            ],
        ),
        "",
        f"Total: {sum(d['files'] for d in inventory['datasets']):,} files; "
        f"{sum(d['rows'] for d in inventory['datasets']):,} rows; "
        f"{sum(d['bytes'] for d in inventory['datasets']):,} bytes.",
        "",
        "## Verified candidate keys",
        "",
        "They are unique and non-null in this delivery; this does not prove stability or business meaning.",
        "",
        table(
            ["Dataset", "Columns", "Distinct values"],
            [
                (k["dataset"], k["columns"], k["distinct"])
                for k in profile["keys"]
                if k["candidate_key"]
            ],
        ),
        "",
        "The complete list, including IDs that fail uniqueness, is in `candidate_keys.csv`.",
        "",
        "Accidental uniqueness of addresses, phones, coordinates or external references does not make them recommended business keys. Prefer each entity's own IDs and check references against their targets.",
        "",
        "## Duplicate rows",
        "",
        table(
            ["Dataset", "Extra duplicate rows"],
            [(d["dataset"], d["duplicate_rows_excess"]) for d in profile["datasets"]],
        ),
        "",
        "## Candidate relationships: value checks",
        "",
        "Nulls and missing references are reported separately. Target uniqueness must be reviewed before joining. Semantics remain pending validation.",
        "",
        table(
            [
                "Source",
                "Target",
                "Nulls",
                "Orphans",
                "Non-null match %",
                "Target ID repeats",
            ],
            [
                (
                    f"{r['source_dataset']}.{r['source_column']}",
                    f"{r['target_dataset']}.{r['target_column']}",
                    r["null_rows"],
                    r["orphan_rows"],
                    f"{r['match_pct_non_null']:.4f}"
                    if r["match_pct_non_null"] is not None
                    else "N/A",
                    r["parent_duplicate_excess"],
                )
                for r in profile["relationships"]
            ],
        ),
        "",
        "Additional pending hypothesis: relate `transactions.transaction_date` and `transactions.currency` to `daily_exchange_rates.date` and `source_currency`, fixing the required target currency. This composite link was not validated in this phase.",
        "",
        "## Column quality",
        "",
        f"Fully null columns: {sum(c['nulls'] == c['rows'] for c in columns)}. "
        f"Constant among non-nulls: {sum(c['constant'] for c in columns)}. "
        f"Nearly constant: {sum(c['almost_constant'] for c in columns)}.",
        "",
        "Highest missing percentage (up to 25 columns; full detail in `column_profiles.csv`):",
        "",
        table(
            ["Dataset", "Column", "Nulls", "%"],
            [
                (c["dataset"], c["column"], c["nulls"], f"{c['null_pct']:.2f}")
                for c in sorted(
                    columns, key=lambda x: x["null_pct"] or 0, reverse=True
                )[:25]
            ],
        ),
        "",
        "Missing values may depend on optional fields; no business defects are assumed without evidence.",
        "",
        "## Dates",
        "",
        table(
            [
                "Dataset",
                "Column",
                "Invalid",
                "After cutoff",
                "Minimum",
                "Maximum",
            ],
            [
                (
                    c["dataset"],
                    c["column"],
                    c["invalid_dates"],
                    c["future_dates"],
                    c["minimum"],
                    c["maximum"],
                )
                for c in columns
                if c["possible_date"]
            ],
        ),
        "",
        "Reproducible cutoff: 2026-09-28. A future expiration or campaign-end date may be legitimate.",
        "",
        "## Possible outliers",
        "",
        table(
            ["Dataset", "Column", "Minimum", "Maximum", "Outside 1.5×IQR"],
            [
                (
                    c["dataset"],
                    c["column"],
                    c["minimum"],
                    c["maximum"],
                    c["possible_outliers"],
                )
                for c in columns
                if c["possible_outliers"]
            ],
        ),
        "",
        "These are profiling signals, not proven errors. Mixed currencies and scales can produce them; no value was removed.",
        "",
        "## Technical decisions and limits",
        "",
        "- Python 3.12, DuckDB for full data and pandas only for small summaries.",
        "- Strict VARCHAR reads preserve IDs and leading zeros. Types are candidates verified by conversion, not changes to the source.",
        "- Empty CSV values are read as NULL; whitespace is recorded without normalization.",
        "- All headers are verified; Hive partitions are not added as columns.",
        "- Exact counts and quartiles; no sampling was used.",
        "- Nearly constant: dominant frequency ≥99% of non-null values.",
        "- Only one composite key is explicitly tested: date, source currency and target currency in exchange rates.",
        "- ID coverage does not validate customer/product/agent consistency or cross-table timing.",
        "- No business dictionary exists to confirm all valid ranges or required fields.",
        "- Originals remain in their initial locations, treated as immutable raw.",
        "",
        "## Source integrity",
        "",
    ]
    findings = ["## Key findings", ""]
    for r in profile["relationships"]:
        if r["orphan_rows"]:
            findings.append(
                f"- `{r['source_dataset']}.{r['source_column']}`: {r['orphan_rows']:,} references without a match out of {r['source_rows'] - r['null_rows']:,} non-null in `{r['target_dataset']}.{r['target_column']}`."
            )
    for c in columns:
        if c["nulls"] == c["rows"]:
            findings.append(
                f"- `{c['dataset']}.{c['column']}`: completely null ({c['rows']:,} rows)."
            )
        if c["column"] == "last_updated" and c["future_dates"]:
            findings.append(
                f"- `{c['dataset']}.last_updated`: {c['future_dates']:,} values after the 2026-09-28 cutoff; maximum {c['maximum']}. Temporal clarification required."
            )
    findings.extend(
        [
            f"- Extra duplicate rows within tables: {sum(d['duplicate_rows_excess'] for d in profile['datasets']):,}. Non-convertible date values in evaluated columns: {sum(c['invalid_dates'] or 0 for c in columns):,}.",
            f"- {sum(bool(c['possible_outliers']) for c in columns)} numeric columns contain possible IQR outliers; none were corrected or removed.",
            "",
        ]
    )
    lines[4:4] = findings
    for name in ("inventory_integrity.json", "profiling_integrity.json"):
        lines.extend([f"`{name}`: `{(REPORTS / name).read_text().strip()}`", ""])
    (REPORTS / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_summary()
