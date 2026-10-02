# AI Banking Platform (`ai-banking-platform`)

An enterprise-grade, evidence-grounded customer service orchestration engine designed to reconstruct customer context, analyze digital event histories, enforce safety policies, and deliver grounded AI responses or structured human agent handoffs.

---

## 1. System Objectives & Architectural Standards

The `ai-banking-platform` is engineered around strict financial production standards to ensure reliability, explainability, and safety:

* **Evidence Before Response:** Every operational assertion (balances, transaction status, error causes) must be anchored in verified facts retrieved from underlying serving views via deterministic tools.
* **Controlled Automation & Policy Isolation:** Intent classification and conversational flow are decoupled from business logic and safety guardrails. Deterministic Python rules govern action permissions, escalation triggers, and PII redaction outside LLM-generated text.
* **Strict Identity & Access Control:** Access to customer records requires a validated authentication and session context. Supplying a `customer_id` alone is insufficient to grant record access or execute workflow tools.
* **Data Quality & Lineage:** Designed to process high-volume synthetic enterprise data (~19 million records across 13 tables) while explicitly handling real-world data flaws including ~2% duplicates, ~5% null values, and late arrivals.
* **Auditability & Explainability:** System outputs, tool calls, and policy decisions are logged via OpenTelemetry and structured traces. Audit trails rely on execution logs, verified source IDs, and rule evaluations rather than hidden model chain-of-thought.
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

---

## 3. Directory Structure & Module Responsibilities

```text
ai-banking-platform/
├── contracts/                  # Pure Pydantic wire contracts (no logic; pydantic-only)
│   └── schemas.py              # DTOs shared by api/, src/, evals/ (single source of truth)
│
├── api/                        # FastAPI Gateway & Middleware
│   ├── main.py                 # App initialization, CORS, authentication hooks
│   └── routes/                 # REST routes (/v1/chat, /v1/context, /v1/trace)
│
├── apps/                       # Front-End Presentation Layer
│   └── demo_ui/                # Streamlit UI with live evidence side-panel
│
├── src/                        # Core Application Packages
│   ├── data/                   # Data Access & Ingestion Engine
│   │   ├── db.py               # DuckDB connection & query runner
│   │   ├── ingest.py           # Parquet sync, deduplication & schema validation
│   │   └── views.py            # SQL definitions for pre-aggregated serving views
│   │
│   ├── tools/                  # Tool Implementations (contracts live in contracts/)
│   │   ├── mocks.py            # Mock outputs for isolated component testing
│   │   └── context_tools.py    # DuckDB-backed context lookup tools
│   │
│   ├── retrieval/              # Vector Search & Unstructured Data
│   │   ├── embeddings.py       # Sentence Transformer embedding pipelines
│   │   └── vector_store.py     # FAISS index & semantic transcript retriever
│   │
│   ├── orchestrator/           # LLM Orchestration & State Machine
│   │   ├── state_machine.py    # State engine: UNDERSTAND -> GATHER -> DECIDE -> RESPOND
│   │   ├── prompts.py          # System prompts & function tool definitions
│   │   └── engine.py           # Execution loop & context assembly
│   │
│   ├── policy/                 # Deterministic Safety & Policy Engine
│   │   ├── rules.py            # PII redaction, risk scoring, SLA breach triggers
│   │   └── handoff.py          # Agent handoff generator (verified facts & evidence)
│   │
│   └── telemetry/              # Tracing & Audit Observability
│       └── logger.py           # Structured JSON logging & execution latency tracing
│
├── evals/                      # Benchmarking & Golden Set Evaluation
│   ├── golden_cases.jsonl      # Test scenarios covering standard & high-risk cases
│   └── run_eval.py             # Evaluation runner (Accuracy, Precision, Latency)
│
├── notebooks/                  # Exploratory Data Analysis (EDA)
├── tests/                      # Unit & Integration Tests
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Local multi-container deployment
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
 3. src/tools/ & retrieval/ ────► GATHER EVIDENCE: Executes DuckDB context tools & FAISS search
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

## 6. Local Development Setup
### 6.1 Repository Setup:

```Bash
git clone https://github.com/vexlai/ai-banking-platform.git
cd ai-banking-platform
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 6.2  Environment Variables Configuration:
Create a .env file in the root directory:

```Code snippet
# API Keys & LLM Config
OPENAI_API_KEY=your_openai_api_key
LLM_MODEL=gpt-4o-mini
USE_LLM=true                                   # enable live tool-calling; unset = deterministic heuristics
OPENAI_BASE_URL=https://api.deepseek.com       # optional: DeepSeek or any OpenAI-compatible endpoint

# Front-End
API_BASE_URL=http://localhost:8000

# Data & Storage
DUCKDB_PATH=./data/bank_serving.duckdb
FAISS_INDEX_PATH=./data/transcripts.faiss

# AWS S3 Data Ingestion (Credentials stored locally, never committed)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=us-east-2
```

### 6.3 Ingest & Sync Data:

```Bash
# Sync dataset from S3 to local ./data folder
aws s3 sync s3://factored-datathon-2026-s3-157725502942-us-east-2-an/data/ ./data/

# Run data pipeline to build DuckDB serving views and FAISS index
python -m src.data.ingest
python -m src.retrieval.vector_store
```

### 6.4 Running System Components
Execute components in separate terminal sessions:
```Bash
# Terminal 1: Run FastAPI Gateway
uvicorn api.main:app --reload --port 8000

# Terminal 2: Run Streamlit Demo UI
streamlit run apps/demo_ui/app.py

# Terminal 3: Run Evaluation Benchmarks
python evals/run_eval.py
```

## 7. Docker & Containerized Setup

The repository includes multi-container orchestration via Docker Compose to run the API gateway, frontend, and vector store seamlessly in isolated containers.

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

## 8. Evaluation & Success Metrics

System performance is continuously evaluated against `evals/golden_cases.jsonl` using automated evaluation pipelines:
- Intent Classification Accuracy: $\ge 85\%$ across labeled test scenarios.
- Evidence Precision: $\ge 90\%$ of retrieved tool context directly supports the query.
- Unsupported Claim Rate: $0\%$ (Strict zero tolerance for ungrounded financial statements).
- Escalation Recall: $100\%$ detection for critical complaints, fraud score spikes, and SLA breaches.
- P95 Latency: $< 8\text{ seconds}$ end-to-end processing time.