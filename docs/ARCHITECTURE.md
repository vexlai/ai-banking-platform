# System Architecture — AI Banking Platform

This document describes the system boundaries, deployment topologies, and the
modularity guardrails that keep the AI Banking Platform composable. It is the
single reference for *how the pieces fit together*; the data-serving and tool
mechanics live in [DATASET_BACKED_TOOLS.md](./DATASET_BACKED_TOOLS.md) and the
analytics runbook in [EDA_RUNBOOK.md](./EDA_RUNBOOK.md).

---

## 1. System Boundary

The platform reconstructs customer context, enforces deterministic safety policy,
and returns either a grounded answer or a structured human handoff. Two execution
surfaces consume the same core engine:

```text
┌──────────────────────────────┐    HTTP + X-API-Key    ┌───────────────────────────┐
│ Mode A — Streamlit UI         │ ─────────────────────► │ FastAPI Gateway            │
│ apps/demo_ui/app.py           │  POST /v1/chat          │ api/main.py                │
└──────────────────────────────┘                        └─────────────┬─────────────┘
                                                                      │
┌──────────────────────────────┐        in-process                    ▼
│ Mode B — Streamlit UI         │ ───────────────► ┌────────────────────────────────┐
│ apps/demo_ui/app.py           │                  │ OrchestratorEngine  (src/)     │
└──────────────────────────────┘                  │ UNDERSTAND→GATHER→DECIDE→      │
                                                  │ RESPOND                        │
                                                  └────────────────────────────────┘
```

- **Mode A (HTTP REST Gateway):** the UI is a thin client. It forwards each turn to
  `POST /v1/chat`; the gateway owns the engine, the serving artifacts, and the
  `X-API-Key` guard.
- **Mode B (In-Process Engine Fallback):** with no gateway configured, the UI
  constructs the `OrchestratorEngine` in-process and runs the identical pipeline.

All business logic lives under `src/`, `api/`, and `contracts/`. `apps/` is a
presentation layer with no business logic of its own.

---

## 2. Domain-Driven Monorepo Structure

| Path | Responsibility | Key modules |
| --- | --- | --- |
| `contracts/` | Pure, provider-agnostic wire contracts (Pydantic only). Single source of truth shared by `api/`, `src/`, and `evals/`. | `schemas.py` |
| `api/` | FastAPI gateway: routing, CORS, `X-API-Key` auth, boot readiness gate. No UI imports. | `main.py`, `config.py`, `security.py`, `routes/{chat,context,trace}.py` |
| `apps/demo_ui/` | Streamlit presentation layer (Audit Cockpit). Renders chat, Customer 360, policy pill, and evidence. | `app.py` |
| `src/data/` | Data access, EDA, and the offline serving build. | `config.py`, `ingest.py`, `download_serving.py`, `eda/`, `workflows/`, `evaluation/` |
| `src/retrieval/` | FAISS semantic transcript retrieval (INT-02). | `vector_store.py` |
| `src/orchestrator/` | Intent classification, evidence assembly, and the `UNDERSTAND→GATHER→DECIDE→RESPOND` state machine. | `engine.py`, `state_machine.py`, `prompts.py`, `llm.py` |
| `src/policy/` | Deterministic safety rules that override LLM generation: PII redaction, fraud/SLA escalation, handoff assembly. | `rules.py`, `handoff.py` |
| `src/tools/` | Dataset-backed context tools and their error taxonomy. | `context_tools.py`, `errors.py`, `mocks.py` (test fixtures) |
| `src/telemetry/` | Structured JSON logging, latency timer, and the in-memory trace ring buffer. | `logger.py` |

## 3. Dual-Mode Deployment Architecture

The same UI file supports two topologies, selected at runtime by `API_BASE_URL`.

### Mode A — HTTP REST Gateway (multi-container)

- `docker compose up --build` starts two services from one image: `api_gateway`
  (FastAPI, `:8000`) and `streamlit_ui` (`:8501`).
- The UI sets `API_BASE_URL=http://api_gateway:8000` and calls the gateway over the
  Compose network. Each turn is `POST /v1/chat` with the customer context read from
  `GET /v1/customers/{customer_id}/context`.
- Every `/v1/*` request carries the `X-API-Key` header (`api/security.py`,
  opt-in via `API_KEY_REQUIRED`); the UI forwards `API_KEY` automatically.
- The gateway verifies `bank_serving.duckdb` and `transcripts.faiss` on boot and
  refuses to start when they are missing (`SKIP_SERVING_CHECK=1` bypasses it).

```text
streamlit_ui:8501 ──HTTP+X-API-Key──► api_gateway:8000 ──► OrchestratorEngine
                                                           └─► DuckDB + FAISS
```

### Mode B — In-Process Engine Fallback (single instance)

- Used on Streamlit Community Cloud, where no separate gateway runs.
- `API_BASE_URL` is left empty, so the UI falls back to the in-process engine.
- `apps/demo_ui/app.py::get_engine` is wrapped in `@st.cache_resource`, so the
  `OrchestratorEngine` (and the FAISS index it holds) is constructed once per
  process and reused across reruns and sessions.
- On boot, `ensure_serving_artifacts` downloads any missing serving artifacts from
  the configured release URLs before the engine is built.

| Aspect | Mode A (Gateway) | Mode B (In-process) |
| --- | --- | --- |
| Entry point | `api/main.py` | `apps/demo_ui/app.py` |
| Transport | HTTP `POST /v1/chat` | Direct method call |
| Auth | `X-API-Key` on `/v1/*` | N/A (same process) |
| Engine lifecycle | App singleton in gateway | `@st.cache_resource` |
| Typical target | Docker Compose | Streamlit Community Cloud |

---

## 4. Modularity Guardrails

The four structural boundaries below are **enforced by `tests/test_guardrails.py`**;
a violation fails the build.

### Guardrail 1 — Front-end isolation (`apps/**` ↛ `src/`)

`tests/test_guardrails.py::test_apps_never_import_src`. Every `apps/**` module imports
only the shared `contracts/` package and reaches the backend over the network
(`POST {API_BASE_URL}/v1/chat`, `timeout=30`). The single sanctioned exception is
`apps/demo_ui/app.py`, which *is* the Mode B fallback host and may import `src/`
(see `APPS_SRC_IMPORT_ALLOWLIST`). No other `apps/**` file may import `src/`.

### Guardrail 2 — Backend is UI-free (`src/**`, `api/**` ↛ `streamlit`)

`tests/test_guardrails.py::test_backend_never_imports_streamlit`. The backend is
transport-agnostic and reusable from the CLI, tests, evals, and the gateway.

### Guardrail 3 — Contract purity (`contracts/` = stdlib + `pydantic`)

`tests/test_guardrails.py::test_contracts_package_is_pure`. Every boundary payload (chat
request/response, evidence bundle, handoff, health) is a Pydantic model in
`contracts/schemas.py`, imported by `api/`, `src/`, and `evals/` alike; `contracts/`
never imports `src/`.

### Guardrail 4 — No schema re-export shim

`tests/test_guardrails.py::test_legacy_schemas_shim_is_not_reintroduced`. The legacy
`src/tools/schemas.py` shim was deleted, so every consumer imports `contracts` directly.

### Behavioral safety rules (conventions, not structural tests)

- **Read-only serving.** `data/serving/bank_serving.duckdb` and
  `data/serving/transcripts.faiss` are opened read-only and produced offline by
  `python -m src.data.ingest`; nothing at request time writes to them.
  `src/tools/context_tools.py` runs strictly: a missing database/view raises
  `ServiceUnavailableError` (HTTP 503) and an unknown customer raises
  `CustomerNotFoundError` (`status=not_found`), with no silent fixture fallback.
- **Deterministic policy overrides generation.** `src/policy/rules.py` owns the
  decision: fraud-score spikes (`>= 0.80`), open high-severity cases, SLA breaches, and
  repeat complaints force `ESCALATE`; missing context forces `CLARIFY`; otherwise the turn
  is `RESPOND`. PII redaction (`redact_pii`) runs on the final text, and when the decision
  is not `RESPOND` the LLM text is never surfaced — the engine emits the deterministic
  template or the structured human handoff.

## 5. Request Lifecycle

```text
1. api/ (Mode A) or app.py (Mode B) ──► validates the ChatRequest contract
2. src/orchestrator/                 ──► UNDERSTAND: classify intent
3. src/tools/ + src/retrieval/       ──► GATHER: DuckDB context + FAISS transcripts
4. src/policy/                       ──► DECIDE: fraud/SLA risk, PII redaction
        ┌──────────────────────────┴──────────────────────────┐
        ▼                                                      ▼
   RESPOND / CLARIFY                                   ESCALATE
   grounded template or LLM text                       structured Handoff
        └──────────────────────────┬──────────────────────────┘
                                   ▼
5. contracts.ChatResponse            ──► decision, intent, reply, evidence,
                                           optional handoff, trace_id, latency_ms
```

- **UNDERSTAND** — `classify_intent` matches a priority keyword table
  (`src/orchestrator/prompts.py`); unmatched messages are `UNKNOWN`.
- **GATHER** — `context_tools.get_context` reads the six read-only DuckDB views; the
  engine then overrides `similar_transcripts` with live FAISS matches.
- **DECIDE** — `assess_risk` returns the `Decision`, which the engine can only ever
  downgrade to a deterministic reply, never override upward.
- **RESPOND** — LLM text is used only for `RESPOND` turns; escalations and
  clarifications always use the deterministic templates. The final text is redacted.

---

## 6. Data Serving & Retrieval

- **Relational:** six DuckDB views (`customer_360_view`, `recent_transactions`,
  `journey_summary`, `interaction_history`, `similar_transcripts`, `open_cases`)
  built offline into `data/serving/bank_serving.duckdb`.
- **Vector:** a 256-dimensional, L2-normalized FAISS `IndexFlatIP` over call
  transcripts, stored at `data/serving/transcripts.faiss` with a
  `transcripts.faiss.meta.json` sidecar.
- **Build:** `python -m src.data.ingest` (see
  [DATASET_BACKED_TOOLS.md](./DATASET_BACKED_TOOLS.md) for flags and internals).
- **Runtime:** the UI never fabricates data. A missing customer surfaces as
  `not_found`; an unavailable serving layer surfaces as `offline`/HTTP 503.

---

## 7. Observability & Safety

- **Structured logs:** `src/telemetry/logger.py` emits one JSON object per record via
  the `ai_banking` logger; `extra` fields (for example `trace_id`, `session_id`)
  are flattened to the top level.
- **Trace buffer:** an in-memory ring buffer keyed by `trace_id`, served by
  `GET /v1/trace/{request_id}`. OpenTelemetry export remains a planned extension.
- **Latency:** `LatencyTimer` measures end-to-end `latency_ms`; the UI benchmarks it
  against the P95 target of **< 8000 ms** per reply.
- **Safety:** the model may never move money, execute transfers, or approve
  credit/eligibility; deterministic policy always has the final say.

## See Also

- [DATASET_BACKED_TOOLS.md](./DATASET_BACKED_TOOLS.md) — serving views, FAISS
  internals, and the offline build.
- [EDA_RUNBOOK.md](./EDA_RUNBOOK.md) — analytics runbook and notebook workflow.
- [../README.md](../README.md) — quickstart, benchmark scorecard, and the docs index.
