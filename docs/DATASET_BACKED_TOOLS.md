# Dataset-Backed Banking Tools (INT-01 / INT-02)

This document describes the dataset-backed serving layer that replaces the deterministic
fixtures: the DuckDB context tools (INT-01), the FAISS transcript retriever (INT-02), and
the offline build script (`src/data/ingest.py`) that produces both.

## Architecture

```
API / orchestrator
      |
      v
src/tools/context_tools.py    --> DuckDB (read-only) --> six serving views
src/retrieval/vector_store.py --> FAISS index --------> top-k transcript matches
      |
      +-- on any failure --> src/tools/mocks.py (deterministic fixtures)
```

- `src/tools/context_tools.py` serves the six customer-context views over the read-only
  DuckDB database at `src.data.config.DUCKDB_PATH`, with the same signatures as
  `src.tools.mocks`.
- `src/retrieval/vector_store.py` loads the FAISS index at
  `src.data.config.FAISS_INDEX_PATH` and returns the nearest transcripts as
  `contracts.TranscriptMatch` records.
- Tools run in strict mode by default: a missing database, view, or query error raises
  `ServiceUnavailableError`, and an unknown `customer_id` raises `CustomerNotFoundError`.
  Pass `strict=False` to serve the deterministic fixtures instead of raising.

`USE_MOCKS` selects the default source for the process (`false` = live DuckDB + FAISS, the
default; `true` = fixtures). Any request may override it with the `?use_mocks=` parameter.

## Serving views

`python -m src.data.ingest` materializes six tables in the serving database:

| View | Source table(s) | Shape |
| --- | --- | --- |
| `customer_360_view` | `customers`, `products` | One row per customer: full name, segment, country, products, credit limit, currency. |
| `recent_transactions` | `transactions` | 30-day window (`--window-days`), max 20 rows per customer, newest first. |
| `journey_summary` | `digital_events` | 24-hour session window (`--session-hours`): events, error count, abandoned forms. |
| `interaction_history` | `call_center_interactions` | Last 10 interactions per customer. |
| `similar_transcripts` | `call_transcripts` | Static per-customer projection; live similarity comes from FAISS at request time. |
| `open_cases` | `complaints` | Active cases with severity, SLA-breach and repeat-complainer flags. |

## Building the serving layer

Requires Python 3.12+ and the pins in `requirements.txt` (DuckDB, pandas, FAISS, numpy).
Run from the repository root:

```bash
# Full build: serving views + FAISS index
python -m src.data.ingest

# Print the resolved sources and the plan without writing anything
python -m src.data.ingest --dry-run

# Serving views only, skip the FAISS index
python -m src.data.ingest --skip-faiss

# Standalone FAISS rebuild
python -m src.retrieval.vector_store --source ./data/raw/call_transcripts --output ./data/serving/transcripts.faiss
```

Flags: `--raw-dir` (default `./data/raw/`), `--duckdb` / `--faiss` (defaults under
`./data/serving/`), `--transcripts` (file or partitioned folder), `--cutoff` (reproducible
as-of date, default `config.REFERENCE_DATE`), `--window-days` (default 30) and
`--session-hours` (default 24).

Each source may be a single `.parquet`/`.csv` file or a Hive-partitioned folder, matched
with a recursive glob. Missing extracts are registered as typed zero-row stand-ins, so the
six serving objects always exist; strict tools then report NOT_FOUND for an unknown
customer instead of failing.

## Retrieval internals

The index is a 256-dimensional, L2-normalized FAISS `IndexFlatIP` (inner product = cosine
similarity). Text is embedded with a deterministic CRC32 feature hash of lowercased
`[a-z0-9]+` tokens, so builds and tests need no external model or network call. A sidecar
`<index>.meta.json` stores the dimension and the per-record `transcript_id`/`summary`
payload and must travel with the `.faiss` file. Transcript text is read from the
`transcript_text`, `full_text`, `text` or `transcript` column; the summary falls back to
the first 200 characters.

## Configuration

| Variable | Default | Responsibility |
| --- | --- | --- |
| `USE_MOCKS` | `false` | Process-wide serving source: live DuckDB/FAISS vs. fixtures. |
| `CORS_ALLOW_ORIGINS` | `*` | Comma-separated gateway CORS allow-list. |

Paths are constants in `src/data/config.py` (`RAW_DATA_DIR`, `DUCKDB_PATH`,
`FAISS_INDEX_PATH`), not environment variables.

## Validation

```bash
pytest tests/                        # 54 tests, incl. test_context_tools / test_ingest / test_vector_store
ruff check . && ruff format --check .
python evals/run_eval.py             # golden-set evaluation
```

`tests/test_ingest.py` builds the views and index from temporary fixtures,
`tests/test_context_tools.py` covers both the DuckDB path and the mock fallback, and
`tests/test_vector_store.py` round-trips a build and search. No organizer data is required
for the suite.

## Known limitations

- `similar_transcripts.similarity` is `0.0` in the DuckDB view; real scores are produced by
  FAISS at request time.
- Raw timestamps carry no timezone and are projected as wall-clock `TIMESTAMP` values, an
  explicit demo assumption rather than certified bank time.
- `open_cases` derives severity from `priority`/`severity` and treats
  `closed`/`resolved`/`cancelled`/`canceled` statuses as non-open.
