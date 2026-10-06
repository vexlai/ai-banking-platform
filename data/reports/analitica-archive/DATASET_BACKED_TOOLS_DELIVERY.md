# Phase 2 — Dataset-backed Banking Tools

## Result

**PASS for local/demo serving, with explicit temporal limits.** The same deterministic
runtime works with real data and fixtures with no changes to CaseService,
state machine, domain contracts or frozen artifacts. Not authorization for
production, adjudication, fraud or reimbursement. Outcome: HANDOFF_RECORDED.

## Source and architecture

The EDA DuckDB cache was reused, not CSV per request. Source SHA-256:
bd6d87c315103fa6d4e771b52dae2df69a382d7e223378a6464ecb1adecf2b8d.

FastAPI -> CaseService -> TransactionTools -> DatasetTools -> DuckDB read-only.
SQLite stays dedicated to cases/commands/audit/handoff. FixtureTools remains the
default. The dataset configuration is explicit and requires disabling legacy routes.

The analytical cache had strings and no indexes; a new operational projection was
created, ordered by customer/date and indexed, without mutating the cache. Size:
900,214,784 bytes. The other ten domains were not duplicated and the file was not versioned.

| Table | Rows | Operational fields |
|---|---:|---|
| transactions | 4,425,008 | ID, customer/product, timestamp, Decimal amount, currency, type, channel, status, merchant, provenance, available_at unknown |
| products | 400,000 | product_id, customer_id |
| customers | 150,000 | customer_id |

complaints, personal text, coordinates and fraud scores are not included.

## Files

- src/cases/dataset_tools.py: implementation of the existing port.
- scripts/prepare_banking_serving.py: validated projection, publish without overwrite.
- api/dispute_configuration.py: fixture/dataset selection; api/main.py changes composition only.
- api/dispute_fixture.py: reuses the existing local verifier; no new IAM.
- tests/test_dataset_tools.py: contract parity and configuration.
- scripts/validate_dataset_tools.py: benchmark and real Uvicorn, restart and SQLite.
- requirements-dataset-tools.txt, CI, README and plan: installation and delivery status.
- docs/DATASET_BACKED_TOOLS.md: full instructions and semantics.
- reports/dataset_tool_validation.json and dataset_tool_benchmark.json: reproducible evidence.

## Contract, security and timing

search/get/history restrict the customer through parameters. product_owner keeps its
existing internal signature and is called after an authorized lookup by CaseService.
A foreign ID returns the same absence as a nonexistent ID. Principal, confirmation,
ownership, version, idempotency and access to audit/handoff controls are kept.

Search: inclusive window [as_of - lookback, as_of], lookback <= 30 days; an exact ID may
be older. Exact comparisons per Search, with no scoring/fuzzy or currency conversion.
An amount without currency is rejected in the runtime's current guard. Order date/ID
descending, maximum 50 and an explicit truncation flag. Never automatic selection.

History is strictly before the candidate, last 30 days; Decimal median in the same
currency. The precision of the means of the two central values is preserved and
complete_window_observed=false is declared at the start of observation.

Provenance: cache hash, relative file, transaction ID and time-policy. The runtime keeps
as_of, rules, guards and audit. Parameterized bank SQL; column names belong to a static
allowlist. DuckDB is opened read_only with external access disabled. No SQL access from
FastAPI or the frontend.

**Temporal limitation:** source without timezone; naive-as-utc-explicit-assumption is an
express demo acceptance, not confirmation of banking UTC. Wall-clock horizon:
2023-06-17 06:01:30 - 2026-06-18 05:59:41. Without certified ingestion/revision timestamps,
available_at stays null. Do not promise certified historical availability or historical
ownership: products/customers are snapshots. process_date/last_updated are not used as
substitutes. Production requires resolving these semantics.

## Data quality

Preparation: zero transaction-product-customer violations and zero product issues,
without deduplication or row loss. Mandatory serving fields have no nulls/empty values.
A null merchant is kept; channel/type/status are required by the real contract, so an
incompatible source fails during preparation instead of being imputed. Outliers are
preserved. Schema/config errors fail before requests.

## Tests and regressions

- Prior baseline: **103 PASS**. Full suite after: **115 PASS** (55.55 s).
- New tests: **12 PASS**, including fixture/dataset parity, scope, temporality,
  edges, precision, currency, SQL injection, truncation, optional merchant, startup,
  read-only reading, PK and HTTP flow through the same CaseService.
- The 30 pre-existing HTTP tests are part of the full suite.
- Uvicorn/HTTP fixture: happy/multiple/none, restart and 18 cross-customer denials;
  replay left 3 cases, 3 handoffs, 11 commands, 11 audit events.
- Uvicorn/HTTP dataset: real clock and controlled historical replay, each with restart;
  confirm/evidence/handoff and replay without duplicates. Per mode: 3 cases, 3 handoffs,
  11 commands and 11 audit events. Foreign case/audit/handoff denied.
- Dataset get: own ID, foreign, after cutoff and currency mismatch checked.
- Planner: customer Index Scan verified, not just assumed pushdown.
- Ruff check/format and diff review; no changes to core, notebooks or frozen outputs.

The frozen verifier confirms 232 protected outputs, 384 baseline predictions and 132
identical retrieval results. The harness also compares hashes of the 122 files present
in artifacts/notebooks before/after. Source cache: SHA before and after preparation equal;
serving: SHA before/after serving equal. Raw: 7,671 files with sizes/mtime unchanged;
full raw contents were not re-hashed.

**Inherited debt, not hidden:** verify_analytics_integration.py does not fully pass due to
an outdated historical manifest (three missing notebook placeholders and four previously
changed files). It was like this before this phase. It was neither repaired nor were
outputs modified to reach green; the analytics-integrity CI keeps that debt. The
runtime/API suite and the separate frozen-output verification do pass.

## 0/1/N demonstration and latency

Selection for tests is reproducible: first customers by sorted ID with at least two
transactions in the last 30 observed days, not manually chosen IDs or links from complaints.
An own ID yields 1; a nonexistent ID yields 0; a search without more clues yields N in
historical replay. One candidate requires confirmation.

With the real operational clock (October 2026), that same historical ID lookup works, but
a last-30-days search returns 0: this is correct behavior. N is demonstrated via a test
factory with a controlled historical clock, not via HTTP input or a runtime/date change.
That replay is not presented as contemporaneous evidence.

Benchmark **local/offline**, warm process, concurrency 1: 250 calls (50 per operation),
lexically ordered customers, no startup. p50/p95 per operation are published in
dataset_tool_benchmark.json; they are not a production SLO or HTTP end-to-end latency.

## Limits and next step

No LLM, new retrieval logic, production IAM, external queue or financial actions. Explicit
local credentials only for demo; do not select real customers from free inputs. One DuckDB
connection serializes access via a lock: production concurrent load was not tested.
Preparation requires disk for the indexed projection. Startup validates format/keys/schema,
not rescanning millions of rows per boot; use only projections produced by the validated preparer.

No new functional blocker for the explicit local scope. Timezone, snapshots and historical
availability remain limits; the analytical manifest debt prevents claiming that the whole
historical CI pipeline is green.

Next task: **Phase 3 — Trusted Demo Identity / IAM Adapter**, not implemented here.