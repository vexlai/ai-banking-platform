# AI Banking Platform (`ai-banking-platform`)

## Estado actual: repositorio unificado

La analítica 00–05, informes y evaluación congelada están integrados.
La autoridad de alcance es [Frozen MVP Contract](reports/FROZEN_MVP_CONTRACT.md):
**Transaction Dispute Intake & Investigation Copilot — GO WITH CONSTRAINTS**.
El resultado previsto es **HANDOFF_RECORDED**, no resolución de disputas.

Consulte [integración y reproducción](docs/ANALYTICS_INTEGRATION.md).
El runtime descrito debajo es el scaffold anterior con mocks, no una implementación
validada del contrato congelado. Sus afirmaciones de seguridad, volúmenes aproximados,
fraud_score, journeys y búsqueda vectorial no sustituyen los hallazgos analíticos
ni constituyen requisitos aprobados. Autorización por cliente, persistencia y guards
de selección/ownership de ese scaffold no deben confundirse con el núcleo descrito abajo.
No conectar datos reales a las rutas legadas.

### Entrega 1: núcleo determinístico de casos

Ya existe un núcleo independiente con SQLite, versionado, idempotencia, confirmación
explícita, ownership/as_of, evidencia y handoff local durable, probado sin LLM.
Consulte [contratos, estados y ejecución](docs/DETERMINISTIC_CASE_RUNTIME.md).
La demo usa exclusivamente fixtures sintéticos y un verificador de identidad de prueba.
La UI/chat legado NO usa este núcleo; la nueva API de disputas sí lo integra.

    .venv/bin/python -m pytest tests/test_case_runtime.py -q
    .venv/bin/python scripts/demo_dispute_cases.py

### Fase 1: Secure Application Adapter

La API /v1/disputes delega directamente en CaseService, sin LLM ni orchestrator legado.
Incluye create/search/confirm/evidence/handoff y GET autorizado de caso/audit/handoff.
Bearer de cliente, expected_version e Idempotency-Key preservan los guards del núcleo.
Configuración explícita: fixtures sintéticos y credenciales locales, no IAM productivo.
Sin configuración, disputas falla cerrado; X-API-Key no autentica clientes.

Consulte [arranque, requests y seguridad](docs/SECURE_APPLICATION_ADAPTER.md) y
[resultado de entrega](reports/APPLICATION_ADAPTER_DELIVERY.md).

    USE_LLM=false .venv/bin/python -m pytest tests/test_dispute_api.py -q
    USE_LLM=false .venv/bin/python scripts/smoke_dispute_http.py

Para el nuevo MVP ejecutar con ENABLE_LEGACY_API=false; no usar la UI antigua como
demostración del flujo nuevo.

### Fase 2: Dataset-backed Banking Tools

El mismo CaseService y la misma API admiten BANKING_TOOLS_BACKEND=fixture (default)
o dataset. DatasetTools abre una proyección DuckDB indexada read-only de 4,425,008
transacciones, 400,000 productos y 150,000 clientes. SQLite sólo almacena casos.
No se agregaron LLM, matching de complaints ni adjudicación.

Consulte [preparación y arranque](docs/DATASET_BACKED_TOOLS.md),
[entrega y limitaciones](reports/DATASET_BACKED_TOOLS_DELIVERY.md) y
[benchmark local](reports/dataset_tool_benchmark.json).
La demo exige configuración explícita de credenciales locales y política temporal;
no es IAM productivo. Las fechas fuente no documentan timezone. El replay histórico
es exclusivamente un harness de validación, no una opción temporal del cliente HTTP.

    pip install -r requirements.txt -r requirements-dataset-tools.txt
    USE_LLM=false pytest tests/test_dataset_tools.py -q

La identidad de demo se implementó en la fase siguiente, descrita abajo.

### Phase 2 actual: Identity & AI Intake (implementada y evaluada offline)

Para compartir las bases fuera de Git: [distribución privada verificable](docs/PRIVATE_DATA_DISTRIBUTION.md).
Incluye paquetes DuckDB separados para serving y análisis; no requiere FAISS ni repetir EDA.

El plan consolidó las entregas anteriores como Foundation & Secure Runtime.
Ahora hay identidad JWT de demo, extractor estructurado consultivo y harness DEV→freeze→TEST.
CaseService y sus guards no cambiaron. El baseline y sus 384 predicciones permanecen congelados.
El modelo no tiene autoridad; la búsqueda todavía requiere confirmación explícita.

TEST congelado (192 casos): GPT-5.6 Luna obtuvo 167/192 (86,98%) full-schema frente a
144/192 (75%) del baseline; should_clarify 192/192 frente a 180/192.
Dos campos inventados en la salida bruta fueron bloqueados; no se ocultan en las métricas.
Costo estimado DEV + TEST + prueba: USD 0,064654, presupuesto USD 2.
Los mocks prueban integración/fallos; la evaluación live mide extracción, no seguridad end-to-end.
Consulte [configuración y ejecución](docs/IDENTITY_AI_INTAKE.md) y
[reporte y Definition of Done](reports/IDENTITY_AI_INTAKE_DELIVERY.md).

    pip install -r requirements-identity-intake.txt
    python scripts/evaluate_intake.py baseline-check
    USE_LLM=false pytest tests/test_identity_intake.py tests/test_structured_intake.py tests/test_intake_harness.py -q

## Legacy scaffold — referencia histórica

Las secciones siguientes describen el scaffold anterior, no garantías del MVP actual.

An enterprise-grade, evidence-grounded customer service orchestration engine designed to reconstruct customer context, analyze digital event histories, enforce safety policies, and deliver grounded AI responses or structured human agent handoffs.

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

> **Implementation note:** The serving views and FAISS index above are the target contract. Until Developer A delivers `src/tools/context_tools.py` (INT-01) and `src/retrieval/vector_store.py` (INT-02), every tool is served from the deterministic fixtures in `src/tools/mocks.py`; the orchestrator and HTTP layers are agnostic to the data source.

---

## 3. Directory Structure & Module Responsibilities

```text
ai-banking-platform/
├── contracts/                  # Pure Pydantic wire contracts (no logic; pydantic-only)
│   └── schemas.py              # DTOs shared by api/, src/, evals/ (single source of truth)
│
├── api/                        # FastAPI Gateway & Middleware
│   ├── main.py                 # App init, CORS, router wiring, /health probe
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
│   ├── data/                   # Data Access & Ingestion Engine        [Dev A · INT-01, planned]
│   │   ├── db.py               # DuckDB connection & query runner      (planned)
│   │   ├── ingest.py           # Parquet sync, dedup & schema validation (planned)
│   │   └── views.py            # SQL definitions for serving views     (planned)
│   │
│   ├── tools/                  # Tool Implementations (contracts live in contracts/)
│   │   ├── mocks.py            # Deterministic fixtures — active today
│   │   └── context_tools.py    # DuckDB-backed context lookup tools    [Dev A · INT-01, planned]
│   │
│   ├── retrieval/              # Vector Search & Unstructured Data      [Dev A · INT-02, planned]
│   │   ├── embeddings.py       # Sentence Transformer embedding pipelines (planned)
│   │   └── vector_store.py     # FAISS index & semantic transcript retriever (planned)
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
│   ├── golden_cases.jsonl      # Test scenarios covering standard & high-risk cases
│   └── run_eval.py             # Evaluation runner (Accuracy, Precision, Latency)
│
├── notebooks/                  # Exploratory Data Analysis (EDA)
├── tests/                      # pytest suites (19 tests)
│   ├── test_policy.py          # PII redaction & risk decision rules
│   ├── test_api.py             # /health, /v1/chat, context, trace & auth guard
│   ├── test_orchestrator_engine.py  # state machine + LLM tool loop (stub client)
│   └── test_guardrails.py      # module-boundary checks (contract purity, HTTP boundary)
├── Dockerfile                  # Multi-stage image (python:3.13-slim)
├── docker-compose.yml          # api_gateway:8000 + streamlit_ui:8501
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
                                  (mock-backed until INT-01/INT-02 land)
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

The legacy scaffold exposes the four routes below. Its legacy routes use an opt-in X-API-Key guard; this does NOT apply to the new dispute API, which requires a customer Bearer credential. Health remains open.

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
USE_LLM=true                                   # enable live tool-calling; unset = deterministic heuristics
OPENAI_BASE_URL=https://api.deepseek.com       # optional: DeepSeek or any OpenAI-compatible endpoint

# Gateway Auth (optional: guards /v1/* with X-API-Key; the UI forwards API_KEY)
API_KEY_REQUIRED=false
API_KEY=your_shared_api_key

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

### 7.3 Ingest & Sync Data:

```Bash
# Sync dataset from S3 to local ./data folder
aws s3 sync s3://factored-datathon-2026-s3-157725502942-us-east-2-an/data/ ./data/

# Run data pipeline to build DuckDB serving views and FAISS index
python -m src.data.ingest
python -m src.retrieval.vector_store
```

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
# Unit + integration suite (19 tests: policy, engine, api, guardrails)
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

System performance is continuously evaluated against `evals/golden_cases.jsonl` by `evals/run_eval.py`, which runs the orchestrator in-process on the deterministic mock fixtures and reports accuracy, intent accuracy, evidence precision, escalation recall, unsupported-claim rate, and p95 latency. The runner exits non-zero unless every golden case passes.
- Intent Classification Accuracy: $\ge 85\%$ across labeled test scenarios.
- Evidence Precision: $\ge 90\%$ of retrieved tool context directly supports the query.
- Unsupported Claim Rate: $0\%$ (Strict zero tolerance for ungrounded financial statements).
- Escalation Recall: $100\%$ detection for critical complaints, fraud score spikes, and SLA breaches.
- P95 Latency: $< 8\text{ seconds}$ end-to-end processing time.

The same guarantees are enforced in CI (`.github/workflows/lint-test.yml`): `ruff check`, `ruff format --check`, `pytest tests/`, and `python evals/run_eval.py` must all pass before a pull request into `main`/`develop` can merge.
