# EDA — stage 02

The reviewable entry point is the notebook `notebooks/02_eda.ipynb`. Run it from the
repository root; generated outputs land in `data/reports/eda/` and the figures in
`data/reports/figures/eda/`.

## Sources and runtime

- Results from `data/reports/profiling` are reused; stages 00 and 01 are not re-run.
- The SHA-256 manifest is verified at the start and at the end. source_integrity.json records the final check.
- DuckDB uses two threads, 1.5 GB of memory and compressed projections in .tmp/eda/analysis.duckdb. The cache excludes PII/text not useful for this analysis; it is invalidated by changes to sources or columns.
- CSVs are read with an explicit VARCHAR schema and strict validation. There is no sampling, imputation, row dropping or outlier removal.
- pandas/matplotlib outputs are small aggregates. Event tables stay in DuckDB.

## Interpretation decisions

- Readiness precedes the descriptive analysis. FK matching and customer/agent consistency are distinct checks.
- Each domain has its own event-date window; transcripts only have a process date. Later complaint/campaign milestones are reported separately.
- process_date has daily granularity. Hour differences against midnight are nominal and must not be read as technical latency.
- Features use the last shared process day, inclusive. They exclude outcomes dated after the cutoff and snapshot attributes of unknown validity.
- open_complaint_count stays NULL: a historical state is not reconstructed from status without a validity date. A distinct count of complaints with no resolution observed at the cutoff is kept.
- CSAT, NPS and CES are not mixed. avg_satisfaction/latest_satisfaction use CSAT only. Averages describe observed responses.
- NULLs after aggregate joins indicate no observations in the domain. They are not replaced by zero; presence indicators are added.
- Complaint-to-product links cannot attribute ownership when customer_id disagrees; counts by affected_product_id describe declared references.
- Global transactional amounts use amount_usd. amount, balances and limits are segmented by currency. Currency for income/costs/conversion value is undocumented.
- FX: both directions/formulas are checked on the exact date with tolerance max(0.02 USD, 1%). The empirical fit alone does not confirm contractual units.
- Per-customer associations are descriptive, conditional on having observations in both domains and without causal inference.

## Main results

- semantic_validation.csv and semantic_validation_examples.csv: consistency and pseudonymized examples.
- temporal_coverage.csv, temporal_delays.csv, lifecycle_windows.csv: horizons and temporal consistency.
- coverage_daily/monthly.csv, partition_day_check.csv, temporal_gaps.csv, abrupt_volume_changes.csv: coverage and partitions.
- transcript_coverage.csv, survey_coverage.csv and *_selection_*: denominators and representativeness.
- *_customer_features.parquet, customer_360_eda.parquet and feature_cardinality.csv: aggregates, joins and one-row-per-customer validation.
- cross_domain_associations.csv and cross_domain_groups.csv: interpretable associations.
- key_eda_metrics.csv: metric index with source.
- EDA_FINDINGS.md: confirmed findings, limitations and hypotheses to review before stage 03.
- `data/reports/figures/eda/`: four figures focused on coverage, financial tails, duration/wait and selection.

execution.log records stages; notebook_execution.log records cells. An intermediate result does not prove completion: check the notebook ran without errors and source_integrity.json from the final run.

Notebook 03 is neither implemented nor run.
