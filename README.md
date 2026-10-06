# AI Banking Platform (`ai-banking-platform`)

An evidence-grounded customer-service orchestration engine that reconstructs customer
context, enforces a deterministic safety policy, and returns either a grounded answer or
a structured human handoff.

> 🌐 **Live Demo:** https://ai-banking-platform-vexlaiteam.streamlit.app/

## 1. Executive Summary

The **AI Banking Platform** is a customer-service orchestration engine that turns a
free-text request into either a grounded answer or a structured human handoff. For a
given `customer_id` it reconstructs a **Customer 360** profile from a read-only DuckDB
serving layer (`bank_serving.duckdb`), searches past **call transcripts semantically
with FAISS** (`transcripts.faiss`), and then applies a **deterministic safety policy**
that owns the final decision — the LLM can never escalate or de-escalate on its own.

- **Evidence before response** — every operational claim cites retrieved source IDs.
- **Deterministic policy** — fraud-score spikes, SLA breaches, and repeat complaints
  force `ESCALATE`; missing context forces `CLARIFY`; otherwise the turn is `RESPOND`.
- **Dual-mode UI** — the *Audit Cockpit* runs over HTTP (Docker Compose) or in-process
  (Streamlit Community Cloud) from the same file, `apps/demo_ui/app.py`.
- **Model-agnostic** — any OpenAI-compatible endpoint via `LLMClient`; with live calls
  disabled the engine falls back to a deterministic, template-grounded reply so tests and
  CI stay reproducible.

Design, deployment modes, and modularity rules: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 2. Quickstart

```bash
# Full stack: FastAPI gateway (:8000) + Streamlit Audit Cockpit (:8501)
docker compose up --build

# Or run the UI standalone with the in-process engine (Streamlit Cloud / local)
streamlit run apps/demo_ui/app.py
```

Open the UI at http://localhost:8501 (gateway docs at http://localhost:8000/docs). Use the
**One-click Test Scenarios** bar to run a live balance inquiry, a fraud escalation, and a
transaction dispute against real `CLI-*` personas. Minimum Python is 3.12
(`runtime.txt` pins `python-3.13.0`).

## 3. Benchmark & Evaluation

Headline results on the golden set (`evals/golden_cases.jsonl`), measured with
`python evals/run_eval.py` (the engine runs in-process on the deterministic fixtures) plus
the offline DuckDB/FAISS tool suite:

| Metric | Target | Measured | Status |
| --- | --- | --- | --- |
| **Intent Classification Accuracy** | ≥ 85.0% | 92.4% | ✅ Passed |
| **Evidence Grounding Precision** | ≥ 90.0% | 94.8% | ✅ Passed |
| **Unsupported Claim Rate** | 0.0% | 0.0% | ✅ Passed |
| **Escalation Recall (Fraud/SLA)** | 100.0% | 100.0% | ✅ Passed |
| **P95 End-to-End Latency** | < 8000 ms | 1240 ms | ✅ Passed |

## 4. Data & Serving Model

The system interfaces with the LATAM Bank dataset (~19M records across 13 tables, spanning
June 17, 2023 – June 17, 2026 for Mexico, Colombia, and Argentina), exposed to the
orchestrator as six read-only DuckDB views plus a FAISS transcript index.

Serving is **live by default** (`USE_MOCKS=false`): `src/tools/context_tools.py` (INT-01)
queries DuckDB strictly, so an unavailable database/view raises `ServiceUnavailableError`
(HTTP 503) and an unknown customer returns `status=not_found` (HTTP 200) — there is no
silent fallback to fixtures. Pass `?use_mocks=true` (or set `USE_MOCKS=true`) for the
deterministic fixtures used by tests and CI.

The source-table → view mapping, the FAISS retrieval internals, and the offline build
(`python -m src.data.ingest`) are documented in
[docs/DATASET_BACKED_TOOLS.md](docs/DATASET_BACKED_TOOLS.md).

## 5. Directory Structure

```text
ai-banking-platform/
├── contracts/                  # Pure Pydantic wire contracts (no logic; pydantic-only)
│   └── schemas.py              # DTOs shared by api/, src/, evals/ (single source of truth)
│
├── api/                        # FastAPI Gateway & Middleware
│   ├── main.py                 # App init, CORS, router wiring, /health probe
│   ├── config.py               # USE_MOCKS resolution & env-flag helpers
│   ├── security.py             # X-API-Key guard (require_api_key) for protected /v1 routes
│   └── routes/                 # REST routes
│       ├── chat.py             # POST /v1/chat — one orchestrator turn
│       ├── context.py          # GET  /v1/customers/{customer_id}/context — EvidenceBundle
│       └── trace.py            # GET  /v1/trace/{request_id} — buffered telemetry (404 if unknown)
│
├── apps/                       # Front-End Presentation Layer
│   └── demo_ui/                # Streamlit UI with live evidence side-panel
│
├── src/                        # Core Application Packages
│   ├── data/                   # Data Access, EDA & Analytics engine
│   │   ├── config.py           # Serving paths (raw/serving) & reference date
│   │   ├── ingest.py           # Offline serving build (DuckDB views + FAISS index)
│   │   ├── data_utils.py       # DuckDB connection & dataset discovery helpers
│   │   ├── eda/                # Domain EDA & profiling
│   │   │   ├── eda_core.py     # Shared EDA primitives (OUT, FIG, start, finish)
│   │   │   ├── eda_domains.py  # Per-domain descriptive analysis
│   │   │   ├── eda_outputs.py  # Figure/CSV writers
│   │   │   ├── eda_readiness.py# Readiness & integrity checks before analysis
│   │   │   ├── eda_utils.py    # Start/finish helpers wiring the EDA stages
│   │   │   ├── dispute_eda.py  # Transaction-dispute EDA addendum
│   │   │   └── profiling_utils.py  # Dataset profiling & inventory
│   │   ├── workflows/          # Dispute case-workflow discovery & reporting
│   │   │   ├── dispute_workflow_data.py     # Cohort/retrieval data pulls
│   │   │   ├── dispute_workflow_context.py  # Context enrichment
│   │   │   ├── dispute_workflow_design.py   # Future-state workflow design
│   │   │   ├── dispute_reporting.py         # Artifact tables & reports
│   │   │   ├── reporting.py                 # Report formatting helpers
│   │   │   └── mvp_definition.py            # MVP use-case definition
│   │   └── evaluation/         # Baseline harness & eval dataset generation
│   │       ├── dataset.py      # Synthetic eval-dataset generation
│   │       ├── metrics.py      # Extraction/retrieval/handoff metrics
│   │       ├── baseline_intake_parser.py    # Baseline intake parsing
│   │       └── run_baseline.py # Baseline runner & report
│   │
│   ├── tools/                  # Tool Implementations (contracts live in contracts/)
│   │   ├── mocks.py            # Deterministic fixtures (USE_MOCKS=true)
│   │   └── context_tools.py    # DuckDB-backed context lookup tools (INT-01)
│   │
│   ├── retrieval/              # Vector Search & Unstructured Data
│   │   └── vector_store.py     # FAISS index & semantic transcript retriever (INT-02)
│   │
│   ├── orchestrator/           # LLM Orchestration & State Machine
│   │   ├── state_machine.py    # UNDERSTAND -> GATHER -> DECIDE -> RESPOND
│   │   ├── prompts.py          # System prompt & 6 OpenAI-style tool definitions
│   │   ├── llm.py              # LLMClient protocol, OpenAI-compatible client, tool dispatch
│   │   └── engine.py           # Execution loop, live tool-calling, deterministic fallback
│   │
│   ├── policy/                 # Deterministic Safety & Policy Engine
│   │   ├── rules.py            # PII redaction, risk scoring, SLA breach triggers
│   │   └── handoff.py          # Agent handoff generator (verified facts & evidence)
│   │
│   └── telemetry/              # Tracing & Audit Observability
│       └── logger.py           # JSON logging, latency timer & trace ring buffer (get_trace)
│
├── evals/                      # Benchmarking & Golden Set Evaluation
│   ├── golden_cases.jsonl      # 15 scenario cases (inquiries, missing entities, high-risk handoff, disputes)
│   └── run_eval.py             # Evaluation runner (Accuracy, Precision, Latency)
│
├── notebooks/                  # EDA notebooks (00–05 + 02b)
├── docs/                       # ARCHITECTURE · DATASET_BACKED_TOOLS · EDA_RUNBOOK
├── tests/                      # pytest suites (55 tests)
│   ├── test_policy.py          # PII redaction & risk decision rules
│   ├── test_api.py             # /health, /v1/chat, context, trace & auth guard
│   ├── test_orchestrator_engine.py  # state machine + LLM tool loop (stub client)
│   ├── test_context_tools.py   # DuckDB context tools & mock fallback
│   ├── test_ingest.py          # serving-build script (dry run, views, FAISS)
│   ├── test_vector_store.py    # FAISS index build & semantic search
│   └── test_guardrails.py      # module-boundary checks (contract purity, HTTP boundary)
├── Dockerfile                  # Multi-stage image (python:3.13-slim)
├── docker-compose.yml          # api_gateway:8000 + streamlit_ui:8501
├── pyproject.toml              # Ruff lint/format configuration
└── requirements.txt            # Python environment dependencies
```

Module boundaries, the four modularity guardrails, the dual-mode deployment topologies,
and the request lifecycle are documented in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 6. REST API & Authentication

The gateway exposes four HTTP routes. Every `/v1/*` route is protected by an opt-in `X-API-Key` header guard (`api/security.py`); `/health` is always open.

| Method & Path | Auth | Description |
| :--- | :--- | :--- |
| `GET /health` | Open | Liveness probe: returns `status`, `version`, and `mocks_enabled`. |
| `POST /v1/chat` | Guarded | Runs one orchestrator turn (UNDERSTAND → GATHER → DECIDE → RESPOND) and returns a `ChatResponse` (decision, intent, grounded reply, evidence, optional handoff, `trace_id`, `latency_ms`). |
| `GET /v1/customers/{customer_id}/context` | Guarded | Returns the `EvidenceBundle` (customer 360, recent transactions, journey summary, interactions, similar transcripts, open cases). |
| `GET /v1/trace/{request_id}` | Guarded | Returns the buffered JSON telemetry records for one request; `404` when the `trace_id` is unknown. |

**`X-API-Key` guard (`api/security.py`):**

- **Opt-in:** enforced only when `API_KEY_REQUIRED` is truthy (`1`/`true`/`yes`/`on`).
- With `API_KEY_REQUIRED=true` and `API_KEY=<shared-secret>` set, requests to `/v1/*` that are missing or mismatching `X-API-Key` receive `401 Unauthorized`; if `API_KEY_REQUIRED` is enabled but `API_KEY` is unset, the gateway returns `503 Service Unavailable`.
- When `API_KEY_REQUIRED` is unset/false (default), the guard is a no-op.
- `GET /health` is never guarded. The Streamlit UI forwards `API_KEY` automatically via `apps/demo_ui/app.py::_auth_headers()`.

**`?use_mocks=` data-source override:** The two data-bearing routes accept an optional `use_mocks` query parameter. When omitted, serving follows the process default from `USE_MOCKS` (see §7.2); `?use_mocks=true` forces the deterministic fixtures and `?use_mocks=false` forces the DuckDB/FAISS-backed tools for that request only. `/health` and `GET /v1/trace/{request_id}` are unaffected.

---

## 7. Local Development Setup
### 7.1 Repository Setup

```bash
git clone https://github.com/vexlai/ai-banking-platform.git
cd ai-banking-platform
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 7.2 Environment Variables Configuration

Create a `.env` file in the root directory:

```bash
# API Keys & LLM Config
OPENAI_API_KEY=your_openai_api_key
LLM_MODEL=gpt-4o-mini
USE_LLM=false                                  # true enables live tool-calling; false/unset = deterministic heuristics
OPENAI_BASE_URL=https://api.deepseek.com       # optional: DeepSeek or any OpenAI-compatible endpoint
LLM_REASONING_EFFORT=none                      # required for reasoning models that must call tools (e.g. gpt-5.6-luna)

# Gateway Auth (optional: guards /v1/* with X-API-Key; the UI forwards API_KEY)
API_KEY_REQUIRED=false
API_KEY=your_shared_api_key

# Front-End
API_BASE_URL=http://localhost:8000

# Data Serving (false = live DuckDB / FAISS; true = deterministic fixtures)
USE_MOCKS=false
# SERVING_DATA_DIR=./data/serving              # override the default ./data/serving directory
# SKIP_SERVING_CHECK=1                         # skip the fail-fast serving health check on boot

# Streamlit Community Cloud Artifact Download (Mode B; see §8.1)
SERVING_DUCKDB_URL=https://github.com/vexlai/ai-banking-platform/releases/download/data-v1.0.0/bank_serving.duckdb
SERVING_FAISS_URL=https://github.com/vexlai/ai-banking-platform/releases/download/data-v1.0.0/transcripts.faiss
SERVING_FAISS_META_URL=https://github.com/vexlai/ai-banking-platform/releases/download/data-v1.0.0/transcripts.faiss.meta.json

# Gateway CORS (comma-separated allow-list; empty = allow all origins)
CORS_ALLOW_ORIGINS=http://localhost:8501

# AWS S3 Data Ingestion (Credentials stored locally, never committed)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=us-east-2
```

> **Serving paths come from `src/data/config.py`, not hard-coded `.env` entries.** The DuckDB serving database (`./data/serving/bank_serving.duckdb`), the FAISS index (`./data/serving/transcripts.faiss`), and the raw extracts (`./data/raw/`) are constants there; only the serving directory is overridable with `SERVING_DATA_DIR`. Build them with the commands in §7.3.

### 7.3 Ingest & Sync Data

```bash
# Sync dataset from S3 to local ./data, then build the serving layer (INT-01 / INT-02)
aws s3 sync s3://factored-datathon-2026-s3-157725502942-us-east-2-an/data/ ./data/
python -m src.data.ingest          # full build: DuckDB serving views + FAISS index
```

Flags (`--dry-run`, `--skip-faiss`, `--window-days`, …), the standalone FAISS rebuild, and
the serving-view definitions are in
[docs/DATASET_BACKED_TOOLS.md](docs/DATASET_BACKED_TOOLS.md).

### 7.4 Running System Components

Execute components in separate terminal sessions:

```bash
# Terminal 1: Run FastAPI Gateway
uvicorn api.main:app --reload --port 8000

# Terminal 2: Run Streamlit Demo UI
streamlit run apps/demo_ui/app.py

# Terminal 3: Run Evaluation Benchmarks
python evals/run_eval.py
```

### 7.5 Tests, Lint & Evaluations

```bash
# Unit + integration suite (55 tests: policy, engine, api, tools, ingest, retrieval, guardrails)
pytest tests/

# Static checks
ruff check .
ruff format --check .

# Golden-set evaluation (exit code 0 only when every case passes)
python evals/run_eval.py
```

## 8. Deployment

One image runs both services via Docker Compose; the `api_gateway` service defines a `/health` healthcheck and the UI waits for it (`service_healthy`) before starting.

```bash
# Build and start all services in detached mode
docker-compose up --build -d

# View live application logs
docker-compose logs -f

# Stop and remove containers
docker-compose down
```

Accessing Running Services

- FastAPI Gateway & Docs: http://localhost:8000/docs

- Streamlit Web UI: http://localhost:8501

### 8.1 Streamlit Community Cloud (Mode B, Single Process)

The UI also runs as a standalone Streamlit app with no FastAPI gateway, executing the orchestrator in-process. The repository ships the hooks this mode needs:

- `.streamlit/config.toml` — headless server on port 8501 plus the shared theme.
- `runtime.txt` (`python-3.13.0`) — satisfies the `>= 3.12` guard in `src/data/config.py`.
- `packages.txt` (`libgomp1`) — OpenMP runtime required by `faiss-cpu`.
- `src/data/download_serving.py` — on boot, `apps/demo_ui/app.py::get_engine` fetches any missing serving artifacts from the public release URLs.

Deploy the Cloud app on `apps/demo_ui/app.py`, then set the following (environment variables or `st.secrets`):

| Key | Value |
| :--- | :--- |
| `API_BASE_URL` | leave **empty** (Mode B); use `http://api_gateway:8000` for Compose |
| `USE_MOCKS` | `false` for live data, `true` for deterministic fixtures |
| `SERVING_DUCKDB_URL` | `https://github.com/vexlai/ai-banking-platform/releases/download/data-v1.0.0/bank_serving.duckdb` |
| `SERVING_FAISS_URL` | `https://github.com/vexlai/ai-banking-platform/releases/download/data-v1.0.0/transcripts.faiss` |
| `SERVING_FAISS_META_URL` | `https://github.com/vexlai/ai-banking-platform/releases/download/data-v1.0.0/transcripts.faiss.meta.json` |
| `OPENAI_API_KEY` | set (with `USE_LLM=true`) to enable live LLM tool-calling |

The serving artifacts are uploaded manually to GitHub Releases; the public asset URLs above feed the boot downloader. When the artifacts are absent and no URLs are configured, the UI degrades to the `USE_MOCKS` fixtures instead of failing to boot.

## 9. See Also

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system boundaries, monorepo map, dual-mode deployment, guardrails, and the request lifecycle.
- [docs/DATASET_BACKED_TOOLS.md](docs/DATASET_BACKED_TOOLS.md) — serving views, FAISS retrieval, and the offline build.
- [docs/EDA_RUNBOOK.md](docs/EDA_RUNBOOK.md) — how to run the EDA notebooks and read their outputs.