# EDA Runbook

How to run and read the exploratory data analysis (EDA). The analysis lives in
`notebooks/` and writes every output under `reports/` (**generated, not committed** —
`.gitignore` excludes `*.parquet`, so re-run the notebooks to reproduce the artifacts).

> Related: [ARCHITECTURE.md](./ARCHITECTURE.md) · [DATASET_BACKED_TOOLS.md](./DATASET_BACKED_TOOLS.md) · [../README.md](../README.md)

## Notebooks

Run them in order from the repository root (Jupyter, JupyterLab, or VS Code); each notebook
is self-contained and keeps the outputs of its last run.

| Notebook | Purpose |
| --- | --- |
| `00_dataset_inventory.ipynb` | Dataset inventory: tables, files, and row counts. |
| `01_ingestion_profiling.ipynb` | Ingestion profiling: source manifest and per-dataset profiles. |
| `02_eda.ipynb` | Cross-domain EDA — the primary reviewable notebook. |
| `02b_transaction_dispute_eda_addendum.ipynb` | Transaction-dispute addendum to `02`. |
| `03_dispute_case_workflow_discovery.ipynb` | Dispute case-workflow discovery. |
| `04_mvp_use_case_definition.ipynb` | MVP use-case definition. |
| `05_baseline_and_eval_dataset.ipynb` | Baseline and evaluation-dataset generation. |

`02_eda.ipynb` reuses the profiling results from step 01 instead of re-running `00`/`01`.
For example:

```bash
.venv/bin/jupyter lab notebooks/02_eda.ipynb
```

## Outputs (generated under `reports/`)

- `reports/profiling/` — `source_manifest.json` and `datasets.csv` (from step 01), reused by later steps.
- `reports/eda/` — `EDA_FINDINGS.md`, `semantic_validation*.csv`, temporal/coverage tables, `*_customer_features.parquet`, `feature_cardinality.csv`, `key_eda_metrics.csv`, and `source_integrity.json`.
- `reports/figures/eda/` — focused figures: coverage, financial tails, duration/wait, and selection.

## Execution notes

- The SHA-256 source manifest is verified at the start and end of the run; `source_integrity.json` records the final check.
- DuckDB uses two threads, 1.5 GB of memory, and compressed projections in `.tmp/eda/analysis.duckdb`. The cache excludes PII/useless text and is invalidated when sources or columns change.
- CSVs are read with an explicit `VARCHAR` schema and strict validation. No sampling, imputation, row-dropping, or outlier removal.
- `execution.log` records stages; `notebook_execution.log` records cells. An intermediate result does not prove completion — confirm the notebook ran without errors and that `source_integrity.json` reflects the final run.

## Interpretation decisions

- Readiness precedes descriptive analysis. FK matches and customer/agent coherence are distinct checks.
- Each domain has its own event-date window; transcripts carry only a process date. Post-cutoff claim/campaign milestones are reported separately.
- `process_date` is daily-grained; hour-level offsets from midnight are nominal, not technical latency.
- Features use the last shared process day (inclusive), excluding outcomes dated after the cutoff and snapshot attributes of unknown validity.
- `open_complaint_count` stays `NULL`: no historical status is reconstructed without a validity date. A distinct count of complaints with no observed resolution at the cutoff is kept instead.
- CSAT, NPS, and CES are never mixed; `avg_satisfaction`/`latest_satisfaction` use CSAT only, and averages describe observed responses.
- `NULL`s after aggregate joins mean no observations in that domain; they are not replaced with zero but flagged with presence indicators.
- Complaint→product links cannot attribute ownership when `customer_id` disagrees; counts by `affected_product_id` describe declared references.
- Global transaction amounts use `amount_usd`; `amount`, balances, and limits are split by currency. Currency for income/cost/conversion value is undocumented.
- FX: both directions/formulas are contrasted with the exact date and a tolerance of `max(0.02 USD, 1%)`. The empirical fit alone does not confirm contractual units.
- Per-customer associations are descriptive, conditional on observations in both domains, and not causal.

Notebook `03` is not implemented or executed.

## See Also

- [ARCHITECTURE.md](./ARCHITECTURE.md) — system boundaries, deployment modes, and modularity guardrails.
- [DATASET_BACKED_TOOLS.md](./DATASET_BACKED_TOOLS.md) — serving views, FAISS retrieval, and the offline build.
- [../README.md](../README.md) — quickstart, benchmark scorecard, and the docs index.

