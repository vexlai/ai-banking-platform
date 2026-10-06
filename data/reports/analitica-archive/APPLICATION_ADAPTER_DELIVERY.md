# Phase 1 — Secure Application Adapter

## Architecture and result

FastAPI -> typed adapter -> **CaseService** -> FixtureTools / SQLite.
The full workflow is exposed over HTTP without the legacy LLM or orchestrator.
Terminal result preserved: **HANDOFF_RECORDED**, local package pending review.
No adjudication, reimbursement, confirmed fraud, closure or external queue.

src/cases/, contracts/disputes.py, the frozen parser and its fixtures were not modified.
All state, selection, ownership, idempotency, version and handoff decisions stay in the core.

## Files in this delivery

- api/main.py: injectable factory, wiring, option to not mount legacy, scoped CORS.
- api/routes/disputes.py: transport, opaque credential, delegation and safe errors.
- api/dispute_fixture.py: explicit local composition from existing development fixtures.
- contracts/dispute_http.py: command/version DTOs, case projection and audit.
- tests/test_dispute_api.py: HTTP acceptance with the existing rig and network blocking.
- scripts/smoke_dispute_http.py: real Uvicorn, restart and SQLite verification.
- scripts/verify_dispute_adapter_regressions.py: hashes and read-only frozen parity.
- README, docs/SECURE_APPLICATION_ADAPTER.md, docs/DETERMINISTIC_CASE_RUNTIME.md,
  docs/IMPLEMENTATION_PLAN.md and CI: real status, execution and tests.

AGENTS.md and the new plan had user changes before this task; they were not reverted.

## Surface and security

POST /v1/disputes; POST /{case_id}/search, /confirm, /evidence and /handoff;
GET /{case_id}, /{case_id}/audit and /{case_id}/handoff under the same prefix.
The eight endpoints delegate exclusively to public CaseService methods.

Bearer is required, resolved by the injected verifier; principal/scope/as_of do not come
from the body. The scaffold's shared API key does not authenticate customers. Ephemeral
local/server-configured credentials are **MOCKED**, not external IAM. CaseService checks
expiration and scopes on GET and replays too. As_of uses the server's real UTC clock.

Expected_version and Idempotency-Key are transported with no extra idempotency layer.
The same payload/key/version preserves the historical response; GET serves current state.
Create responds 201 on replay; no effect is added. Explicit selection remains required
even with a single candidate. Ownership is re-read from tools on confirm and collect.

Development fixtures A/C are reused without modifying the source file. The time offset
is fixed by a server anchor that must survive restarts. Product/ownership and additional
type/channel/status are labeled synthetic, not new banking observations. Evidence keeps
source_ref with the anchor.

## Domain → HTTP

| Situation | HTTP |
|---|---:|
| AUTH_DENIED: missing/invalid/expired/scope | 401 |
| CASE_NOT_ACCESSIBLE: foreign or nonexistent indistinguishable | 404 |
| STALE_VERSION / IDEMPOTENCY_KEY_REUSED / INVALID_TRANSITION / TERMINAL_CASE | 409 |
| Invalid input, clues or selection | 422 |
| CLOCK_BEFORE_CASE / SQLite failure / dependency unavailable | 503 |
| Unexpected exception / invalid internal contract | 500 |

Allowlisted codes only; no echo of inputs, secrets, foreign IDs or stacktraces.
Tool failures captured by the core keep HTTP 200 with explicit INSUFFICIENT_EVIDENCE
state and issue: success of persisting the failure, **not investigative success**.

Authorized audit projects actor/provider, action, states, version and recorded_at.
Internal hashes and the global rejection table are not exposed. Evidence/guard results are
in the bundle/evidence; the correlation-id is transient HTTP correlation and v1 does not
admit it in durable audit. Cache-Control: no-store is returned. No duplicate HTTP auditing was added.

## Local validations

| Check | Result |
|---|---|
| Full prior suite, unchanged | 73 passed |
| New API tests | 30 passed |
| Full suite after integration | 103 passed |
| Ruff lint / format of affected files | PASS |
| Real HTTP on loopback with Uvicorn | explicit / multiple / none -> HANDOFF_RECORDED |
| Uvicorn restart + replay of the whole sequence | same cases/handoffs |
| SQLite after replay | 3 cases, 3 handoffs, 11 commands, 11 audit |
| Audit per case | 5 / 3 / 3, no duplicates |
| Cross access to GET case/audit/handoff, two runs | 18/18 rejected |
| SQLite integrity_check / foreign_key_check | ok / no violations |
| Analytical artifacts/frozen manifest contracts | 232 identical hashes |
| Baseline predictions | 384 identical |
| Retrieval fixtures | identical metrics across 132 fixtures |
| Raw | 7,671 file sizes unchanged; no content rehash |

Tests include unauthorized command calls, invalid/expired/scope, future, wrong
currency, false confirmation, foreign candidate, changed ownership, concurrency,
stale version, replay after restart, double handoff, tool and persistence failures,
malformed input and missing configuration. Network is blocked in in-process tests.
The separate smoke does use local HTTP; its credentials are not printed and its temporary
DB is deleted after verification. No LLM calls, raw access from the API or financial decisions.

### Environment and inherited discrepancy

The first run with only the runtime environment could not collect three analytical modules:
DuckDB was missing. It was repeated before changing code with the analytical dependencies
already installed: 73 passed. The final full run used the same dependency combination.
In a new environment install requirements.txt and requirements-analytics.txt.

The historical verifier scripts/verify_analytics_integration.py already failed before editing:
its old references to 03_customer_journey_discovery.ipynb, 04_use_case_definition.ipynb and
05_baseline.ipynb are missing. scripts/build_eda.py, scripts/build_mvp_and_eval.py, AGENTS.md
and docs/ANALYTICS_ORIGINAL_README.md also differ from its historical manifest.
That manifest was not corrected or overwritten. This delivery's verifier reports the
discrepancies and separately checks the frozen scope. **It is not claimed that the full
historical verifier or remote CI is green.** Adapter CI was added, not run remotely.

## Limits and next task

IMPLEMENTED: HTTP, DTOs, delegation, safe errors and transient correlation.
TESTED: fixture workflow, core/HTTP safety, persistence and local replay.
MOCKED/SYNTHETIC: credentials/serving, aliases and demo context.
NOT IMPLEMENTED: real data, production IAM, external queue/policy, LLM, UI, deployment.
NOT MEASURED: production benefit, LLM adversarial robustness and load performance.

No functional blocker for the fixtures adapter. The historical-manifest discrepancy
is documented pre-existing debt, not a baseline regression nor authorization to change it.
Local SQLite/locks and demo secrets are not a production architecture. Legacy stays
available for compatibility if not disabled: use ENABLE_LEGACY_API=false for the MVP.

Next task: **Phase 2 — Dataset-backed Banking Tools**. Not implemented in this delivery.
Full reproduction: [SECURE_APPLICATION_ADAPTER.md](../docs/SECURE_APPLICATION_ADAPTER.md).