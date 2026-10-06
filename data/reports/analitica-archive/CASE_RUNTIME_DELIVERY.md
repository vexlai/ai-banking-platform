# Delivery 1 — persistent deterministic core

Local validation: 2026-10-03. Result: PASS for the defined offline scope.
Not a certification of production security or banking adjudication.

## Implemented flow

Verified external principal -> intake -> untrusted regex clues -> confirmed search
-> branching across zero/one/multiple candidates -> explicit selection
-> transaction/product/customer ownership -> evidence and historical context
-> automatic policy blocked -> HANDOFF_RECORDED.

No-candidate, ambiguous or insufficient-evidence paths can also record a handoff,
without fabricating a transaction or verified facts.
Customer selection does not constitute complaint->transaction ground truth.

SQLite persists case, audit, idempotent response and handoff in a single
transaction. Mutations require the expected version. Repeating an identical command
does not duplicate effects; another load with the same key is rejected. Schema
initialization is also rolled back if the existing version is incompatible.
A new database is created with 0600 permissions; existing databases are not re-permissioned.

## Verification evidence

| Check | Result |
|---|---|
| Core tests with network connections blocked | 37 passed |
| Existing API/guardrails/orchestrator/policy regressions, LLM disabled | 19 passed |
| Final run total | 56 passed |
| Lint and format of new code | passed |
| Explicit/ambiguous/no-candidate demo | 3 HANDOFF_RECORDED |
| Demo re-run and SQLite recovery | same IDs; no duplicates |
| Audit of the three demo cases | 5 / 3 / 3 events, no replay growth |
| Imported analytical files | 279 SHA256 identical to source |
| Frozen baseline predictions | 384 identical |
| Frozen retrieval fixtures | identical metrics across 132 fixtures |

Tests cover expiration/scope/invalid credential, cross-customer isolation,
time and currency limits, explicit confirmation, revalidated ownership, record
changes, strictly prior context, explicit truncation, tool errors,
concurrency, restart, rollback, idempotency, audited rejections and incompatible schema.
Prompt-injection text has no authority over identity or actions.
This does NOT evaluate an LLM's resistance to injection: there is no model in this flow.

The 3 scaffold golden cases also passed as smoke tests; their marker-based grounding
metrics are not factual validation of the new system.
Remote CI was not run in this session; it was updated to include the core.

## Limits of this delivery

- Transaction backend and authentication: explicit synthetic fixtures.
- Issuer/signature/revocation verification: responsibility of the host IAM not yet integrated.
- Legacy API/UI: not connected to the new core; keeps its known restrictions.
- Handoff: LOCAL_PENDING_HUMAN_REVIEW, not external-queue acceptance or resolution.
- Policy: EXTERNAL_POLICY_REQUIRED; no financial decision, reimbursement, fraud or closure.
- Real data: not connected to tools; profiling/EDA/discovery were not re-run.
- Historical ingestion/revision: not certified; this limitation is preserved in the evidence.
- Audit is append-only in the application, not WORM storage in the face of an administrator.
- Synthetic tests do not demonstrate matching accuracy or production benefits.

No raw data or frozen artifacts were modified. The final raw verification was
by sizes (7,671 files), not a new full content hash.

## Reproduction

From the ai-banking-platform root:

    .venv/bin/python -m pytest tests/test_case_runtime.py -q
    .venv/bin/python scripts/demo_dispute_cases.py

The demo keeps its database in .tmp/disputes/demo.sqlite3, ignored by Git.
To start another demo use --db with a new file, without deleting the previous one.
Minimum dependencies are pinned in requirements-case-runtime.txt.
Full contracts, states and limits: docs/DETERMINISTIC_CASE_RUNTIME.md.

The next increment is a secure application adapter with IAM and read-only serving,
keeping these guards. LLM extraction/summary integration must be evaluated later
against the frozen benchmark.