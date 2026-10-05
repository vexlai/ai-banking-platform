# AI Banking Platform (`ai-banking-platform`)

An enterprise-grade, evidence-grounded customer service orchestration engine designed to reconstruct customer context, analyze digital event histories, enforce safety policies, and deliver grounded AI responses or structured human agent handoffs.

## 0. Delivery Status

| Scope | Status | Notes |
| :--- | :--- | :--- |
| `api/`, `src/orchestrator/`, `src/policy/`, `src/telemetry/` | **Completed** | Gateway, orchestrator state machine, policy engine, telemetry tracing. |
| `src/data/` (`config`, `data_utils`, `eda/`, `workflows/`, `evaluation/`) | **Completed** | Analytics & EDA modules. |
| `src/data/ingest.py` | **Completed** | Offline build: DuckDB serving views + FAISS transcript index. |
| `src/tools/context_tools.py` (INT-01) | **Completed** | DuckDB-backed context tools over the six serving views; strict by default (NOT_FOUND / SERVICE_ERROR), fixtures only when `strict=False`. |
| `src/retrieval/vector_store.py` (INT-02) | **Completed** | FAISS semantic transcript retrieval over the built index. |
| `notebooks/`, `docs/` | **Completed** | 7 EDA notebooks plus the analytics docs and EDA runbook. |

---

## 1. System Objectives & Architectural Standards

The `ai-banking-platform` is engineered around strict financial production standards to ensure reliability, explainability, and safety:

* **Evidence Before Response:** Every operational assertion (balances, transaction status, error causes) must be anchored in verified facts retrieved from underlying serving views via deterministic tools.
* **Controlled Automation & Policy Isolation:** Intent classification and conversational flow are decoupled from business logic and safety guardrails. Deterministic Python rules govern action permissions, escalation triggers, and PII redaction outside LLM-generated text.
* **Model-Agnostic Reasoning with Deterministic Fallback:** The orchestrator reaches any OpenAI-compatible endpoint (OpenAI `gpt-4o-mini`, DeepSeek `deepseek-chat`, or a custom `base_url`) through a provider-agnostic `LLMClient` abstraction, with tool-calling over the shared contracts. When live calls are disabled or fail, the engine falls back to a deterministic, template-grounded reply so tests, CI, and evals stay reproducible.
* **Strict Identity & Access Control:** Access to customer records requires a validated authentication and session context. Supplying a `customer_id` alone is insufficient to grant record access or execute workflow tools.
* **Data Quality & Lineage:** Designed to process high-volume synthetic enterprise data (~19 million records across 13 tables) while explicitly handling real-world data flaws including ~2% duplicates, ~5% null values, and late arrivals.
* **Auditability & Explainability:** System outputs, tool calls, and policy decisions are logged via OpenTelemetry and structured traces. Audit trails rely on execution logs, verified source IDs, and rule evaluations rather than hidden model chain-of-thought. *Current implementation:* structured JSON logs plus an in-memory trace ring buffer keyed by `trace_id` (served via `GET /v1/trace/{request_id}`); OpenTelemetry export remains a planned extension.
* **Credit & Financial Safety Boundaries:** The conversational model is strictly prohibited from executing financial transactions, moving money, or independently approving credit/eligibility.

---

## 2. Dataset Overview & Serving Boundaries

The system interfaces with the LATAM Bank dataset (~19M records spanning June 17, 2023 to June 17, 2026 across Mexico, Colombia, and Argentina):

| Table Category | Key Source Tables | Volume & Target Serving Views |
| :--- | :--- | :--- |
| **Identity & Products** | `customers`, `products`, `branches` | **`customer_360_view`**: Compact view of segment, country, active products, limits, and accent metadata. |
| **Financial Movements** | `transactions` (5M rows) | **`recent_transactions`**: 30-day temporal window, max 20 rows, normalized status & fraud flags. |
| **Digital Journeys** | `digital_events` (10M rows) | **`journey_summary`**: 24-hour window / active session summary prioritizing error logs & form submissions. |
| **Customer Support** | `call_center_interactions`, `call_transcripts`, `service_agents` | **`interaction_history`** & **`similar_transcripts`**: Last 5–10 interactions + FAISS top-3 semantic transcript match. |
| **Cases & Feedback** | `complaints`, `satisfaction_surveys` | **`open_cases`**: Active cases, SLA breach indicators, and repeat complaint flags. |

> **Implementation note:** The serving views and FAISS index above are the live contract: `src/tools/context_tools.py` (INT-01) queries the DuckDB serving database and `src/retrieval/vector_store.py` (INT-02) performs FAISS semantic search, both built offline by `python -m src.data.ingest`. Serving is live by default (`USE_MOCKS=false`): the context tools run in strict mode, so an unavailable database or view raises `ServiceUnavailableError` (HTTP 503) and an unknown customer returns `status=not_found` (HTTP 200). There is no silent fallback to fixtures; pass `?use_mocks=true` (or set `USE_MOCKS=true`) for the deterministic fixtures used by tests and CI. On boot the gateway verifies both artifacts and refuses to start when they are missing (bypass with `SKIP_SERVING_CHECK=1`).

---

## 3. Directory Structure & Module Responsibilities

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
│   │   ├── mocks.py            # Deterministic fixtures — default source & fallback
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
├── notebooks/                  # EDA notebooks (00–05: inventory → baseline/eval)
├── docs/                       # Analytics docs & EDA runbook
├── tests/                      # pytest suites (54 tests)
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

## 4. Modularity Guardrails (Non-Negotiable)

To keep the codebase modular and prevent it from devolving into a monolithic "spaghetti" system, all contributors must adhere to these four guardrails.

### Guardrail 1 — Strict HTTP Boundary for the Front-End

- `apps/demo_ui/app.py` must never import modules from `src/` directly; it imports only the shared `contracts/` package.
- It operates strictly as an HTTP client, calling the gateway over the network (`POST http://localhost:8000/v1/chat`) with mandatory request timeouts (`timeout=30`).

### Guardrail 2 — Contract-First Integration (`contracts/schemas.py`)

- The wire contract is defined once in the pure `contracts/` package and imported directly by every layer (`api/`, `src/**`, `evals/`); there is no re-export shim.
- All tools, database queries, and orchestrator engines accept and return strongly typed Pydantic objects from that contract.
- The orchestrator stays agnostic as to whether data originates from `src/tools/mocks.py` or `src/tools/context_tools.py`.

### Guardrail 3 — Strict Directory Partitioning

- Scope ownership is split cleanly between data engineers and AI engineers:
  - **Data Scope:** `src/data/` and `src/retrieval/`.
  - **AI & Platform Scope:** `api/`, `apps/`, `src/orchestrator/`, `src/policy/`, `src/telemetry/`, and `evals/`.
  - **Shared:** `contracts/` (pure types, dependency-light; owned by neither scope).
- `.gitignore` uses root-anchored rules (`/data/`) so local DuckDB databases are ignored without ignoring source code under `src/data/`.

### Guardrail 4 — Container & Process Isolation

- The API gateway and the Streamlit UI run in separate processes and separate Docker containers (port 8000 vs 8501).
- UI containers reach the gateway dynamically via environment variables (`API_BASE_URL`).

These boundaries are enforced automatically by `tests/test_guardrails.py`, which fails the build if `apps/**` imports `src/`, if `contracts/**` depends on anything beyond the standard library plus `pydantic`, or if the removed `src.tools.schemas` re-export shim reappears.

## 5. End-to-End Execution Flow

``` text
[ Customer Query + Session Context ]
               │
               ▼
 1. api/routes/chat.py  ────────► Validates session authentication & initializes request trace
               │
               ▼
 2. src/orchestrator/   ────────► UNDERSTAND: Classifies intent & missing parameters
               │
               ▼
 3. src/tools/ & retrieval/ ────► GATHER EVIDENCE: Context tools & FAISS search
                                  (DuckDB + FAISS, mock fallback via USE_MOCKS)
               │
               ▼
 4. src/policy/         ────────► DECIDE: Sanitizes PII, checks fraud triggers & SLA breaches
               │
        ┌──────┴─────────────────────────┐
        ▼                                ▼
[ RESPOND / CLARIFY ]            [ ESCALATE TO HUMAN ]
Low Risk / Evidence Grounded     High Risk / Fraud Alert / SLA Breach / Missing Context
        │                                │
        ▼                                ▼
Direct Answer with Source IDs    Structured Handoff with Verified Facts & Evidence
```

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
### 7.1 Repository Setup:

```Bash
git clone https://github.com/vexlai/ai-banking-platform.git
cd ai-banking-platform
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 7.2  Environment Variables Configuration:
Create a .env file in the root directory:

```Code snippet
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

# Gateway CORS (comma-separated allow-list; empty = allow all origins)
CORS_ALLOW_ORIGINS=http://localhost:8501

# AWS S3 Data Ingestion (Credentials stored locally, never committed)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=us-east-2
```

> **Serving paths come from `src/data/config.py`, not hard-coded `.env` entries.** The DuckDB serving database (`./data/serving/bank_serving.duckdb`), the FAISS index (`./data/serving/transcripts.faiss`), and the raw extracts (`./data/raw/`) are constants there; only the serving directory is overridable with `SERVING_DATA_DIR`. Build them with the commands in §7.3.

### 7.3 Ingest & Sync Data:

```Bash
# Sync dataset from S3 to local ./data folder
aws s3 sync s3://factored-datathon-2026-s3-157725502942-us-east-2-an/data/ ./data/

# Build the DuckDB serving views and the FAISS index (INT-01 / INT-02)
python -m src.data.ingest               # full build: serving views + FAISS index
python -m src.data.ingest --dry-run     # print the plan; write nothing
python -m src.data.ingest --skip-faiss  # build the serving views only

# Standalone FAISS rebuild (equivalent to the index step above)
python -m src.retrieval.vector_store
```

> **Tip:** The build reads raw extracts from `./data/raw/` and writes the serving database
> and index under `./data/serving/`. Extracts that are absent are registered as typed
> zero-row stand-ins, so the six serving objects always exist. With the default
> `USE_MOCKS=false`, an unknown customer returns `status=not_found`; `?use_mocks=true`
> serves the deterministic fixtures.

### 7.4 Running System Components
Execute components in separate terminal sessions:
```Bash
# Terminal 1: Run FastAPI Gateway
uvicorn api.main:app --reload --port 8000

# Terminal 2: Run Streamlit Demo UI
streamlit run apps/demo_ui/app.py

# Terminal 3: Run Evaluation Benchmarks
python evals/run_eval.py
```

### 7.5 Tests, Lint & Evaluations

```Bash
# Unit + integration suite (54 tests: policy, engine, api, tools, ingest, retrieval, guardrails)
pytest tests/

# Static checks
ruff check .
ruff format --check .

# Golden-set evaluation (exit code 0 only when every case passes)
python evals/run_eval.py
```

## 8. Docker & Containerized Setup

The repository includes multi-container orchestration via Docker Compose to run the API gateway and Streamlit frontend in isolated containers. The `api_gateway` service defines a `/health` healthcheck, and the UI waits for it (`service_healthy`) before starting.

```Bash
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

## 9. Evaluation & Success Metrics

System performance is continuously evaluated against `evals/golden_cases.jsonl` by `evals/run_eval.py`, which runs the orchestrator in-process on the deterministic mock fixtures and reports accuracy, intent accuracy, evidence precision, escalation recall, unsupported-claim rate, and p95 latency. The runner exits non-zero unless every golden case passes. The golden set spans 15 representative journeys: standard inquiries (balances, transaction status, digital login issues), missing/invalid entities (unknown customer → `not_found`, valid customer with no transactions → grounded empty answer), high-risk handoffs (fraud score ≥ 0.80, SLA breach, unresolved critical/repeat complaints) and disputes/boundary rules (charge disputes, unauthorized ATM withdrawals, credit-limit requests, PII redaction).
- Intent Classification Accuracy: $\ge 85\%$ across labeled test scenarios.
- Evidence Precision: $\ge 90\%$ of retrieved tool context directly supports the query.
- Unsupported Claim Rate: $0\%$ (Strict zero tolerance for ungrounded financial statements).
- Escalation Recall: $100\%$ detection for critical complaints, fraud score spikes, and SLA breaches.
- P95 Latency: $< 8\text{ seconds}$ end-to-end processing time.

The same guarantees are enforced in CI (`.github/workflows/lint-test.yml`): `ruff check`, `ruff format --check`, `pytest tests/`, and `python evals/run_eval.py` must all pass before a pull request into `main`/`develop` can merge.