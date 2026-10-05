# Phase 2 — Identity & AI Intake

Implementation and mocked tests exist; live learned evaluation is NOT MEASURED.
Provider, pinned model, credentials and budget remain required. Do not claim improvement.
See reports/IDENTITY_AI_INTAKE_DELIVERY.md for the complete acceptance status.

## Architecture

Bearer → DemoJWTIdentity → existing Principal → existing CaseService.
Authorized case/get → original intake utterance → extractor → unconfirmed structured clues.
Customer-confirmed Search → unchanged CaseService → explicit Selection → evidence → handoff.

CaseService, guards, store, tools and frozen baseline are unchanged. Case.extracted_clues
still contains original regex suggestions. Learned output is consultative, not written
over those clues or case state. Network calls happen outside SQLite transactions.

## Identity setup

Python 3.12+: install requirements.txt, requirements-dataset-tools.txt and
requirements-identity-intake.txt. Configure private server environment:

| Variable | Value |
|---|---|
| DISPUTE_IDENTITY_BACKEND | jwt |
| DISPUTE_JWT_SECRET | cryptographically random secret, at least 32 bytes; never commit |
| DISPUTE_JWT_ISSUER | exact issuer, e.g. banking-dispute-demo |
| DISPUTE_JWT_AUDIENCE | exact audience, e.g. banking-dispute-api |
| ENABLE_LEGACY_API | false |
| INTAKE_EXTRACTOR | baseline initially |

Keep explicit fixture/dataset backend settings from existing setup docs. JWT fixture
mode requires its anchor, but no opaque A/B tokens. JWT dataset mode requires serving
path/time policy/demo opt-in, but no A/B identity mapping: identity is issuer-signed.
The default local identity backend preserves old regression tests, not production IAM.

Operator-only provisioning (not a public endpoint or browser self-registration):

~~~sh
python scripts/issue_demo_token.py --subject demo-subject \
  --customer AUTHORIZED_REFERENCE --output .tmp/identity/demo.jwt
uvicorn api.main:app --host 127.0.0.1 --port 8000
~~~

Replace AUTHORIZED_REFERENCE with an operator-approved reference. The token is written
to a new 0600 file under ignored .tmp, never printed. Use it privately in Authorization:
Bearer. Do not paste tokens into chat/logs/screenshots. TTL defaults to 900s, maximum 3600s.

Verifier pins HS256 independently of header. Required claims: sub, customer_id, iss,
aud, iat, exp, scopes. Exact issuer/audience, integer timestamps, nonfuture iat, future
exp, maximum one-hour lifetime; scopes are dispute:read/write. CaseService enforces
operation-specific scope again. Failure is AUTH_DENIED/401 without token details;
foreign resources remain indistinguishable from missing (404). Verified issuer maps
to Principal.provider. Never trust identity from utterance/body/model.

Shared-secret demo only: the issuer/key holder can sign identities. Protect the key;
rotation invalidates tokens. No refresh, per-token revocation, onboarding or production
key management is implemented.

## Extraction API

After POST /v1/disputes, call POST /v1/disputes/{case_id}/intake-extraction with Bearer.
No body is needed. Only original case utterance enters the model. Authorization is
checked before and after inference, including session expiry. The response contains
status, intake (eight frozen fields or null), deterministic flags and metadata.

Provider/schema errors return HTTP 502/model_error with no intake. Unsupported clues
return unsupported_output with null intake and clarification. No automatic fallback,
query, confirmation, handoff or mutation occurs. Retry can incur another provider call:
this is a read-only suggestion endpoint, not a second command/idempotency implementation.
Existing mutating routes retain expected_version and Idempotency-Key.

Client confirmation precedes the existing search command; candidate confirmation is
still separately mandatory. Relative hints stay symbolic. Arbitrary banking IDs can
still be submitted to deterministic Search, while frozen extractor grammar only admits
pseudonymized TX IDs. Multi-turn clarification and summaries are not implemented.

## Learned configuration

INTAKE_EXTRACTOR=learned requires INTAKE_API_KEY and INTAKE_MODEL_CONFIG (path to private
operator-authored JSON). ModelConfig in src/intake/extractor.py defines exact fields:

- Required model and model_version; use a pinned snapshot/version.
- provider=openai-compatible, base_url=https://api.openai.com/v1 by default; HTTPS required.
- temperature=0, timeout_seconds=20, max_completion_tokens=400; no retries, tools or storage.
- Temperature may be explicitly null only if required by the selected model.
- input_usd_per_million, output_usd_per_million, pricing_reference required for live eval.

No model is silently selected. Legacy USE_LLM does not select this extractor.
Explicitly switch INTAKE_EXTRACTOR=baseline to operate without a provider. Failure
never silently becomes a baseline result. Pydantic validates exact frozen keys/types,
enums/calendar dates. Unknowns remain null. Conservative lexical support checks and a
small instruction-pattern guard reject unsupported output, not repair it. These are
not proof of semantic truth or general prompt-injection resistance.

Metadata logs request/case IDs, language, model/version, prompt/schema, latency,
validation, usage, cost when known and error code. No utterance, principal, credentials,
raw model prose or chain-of-thought. Invalid output is hashed. Privacy deliberately
limits the conceptual future contract's raw-output preservation: only allowlisted
structured fields from synthetic eval are retained for measuring rejected hallucinations,
and those internal fields are excluded from HTTP serialization and telemetry.

## Evaluation

Never regenerate frozen analytics/baseline. Commands from repo root:

~~~sh
python scripts/evaluate_intake.py baseline
python scripts/evaluate_intake.py dev --config PRIVATE_CONFIG.json --run-id v1 --max-cost-usd BUDGET
python scripts/evaluate_intake.py freeze --config PRIVATE_CONFIG.json --run-id v1
python scripts/evaluate_intake.py test --run-id v1 --max-cost-usd BUDGET
~~~

Baseline was already reproduced; files are create-only and refuse overwrites.
Baseline reproduction without rewriting outputs uses the baseline-check command. Live
outputs use reports/evaluation/intake/runs/v1/{development,test}. Those run-scoped
metrics/comparison are immutable run records. scripts/report_intake_results.py explicitly
publishes derived root report views, superseding the initial NOT_MEASURED placeholders.
Each split: 192 cases, 96 ES/96 PT; disjoint groups. All utterances are team-generated;
PT is not observed banking text. No labels/split/principal enter the extractor.

Freeze requires successful DEV, returned provider version matching declared snapshot,
matching configuration, prompt/schema/code/data hashes and Python/SDK/Pydantic versions.
A create-only held_out_consumption.json is written before first TEST call. Interrupted
runs also consume TEST. Never delete that ledger to retry. Further independent testing
requires a fresh held-out workload and explicit review, not a new name for the same test.

Operator supplies pricing references and positive budget; a conservative UTF-8 byte/token
allowance bounds planned calls but is not a provider billing cap. Unknown cost from failed
requests remains null, not zero. Baseline zero cost means external API cost, not free CPU.
Metrics separate delivered intake from raw allowlisted model fields before semantic
rejection, so filtering cannot hide hallucinations. Per-field metrics and denominators,
full schema, unknown correctness, missing clues, clarification, ES/PT and latency/cost
are emitted. Rejected/failed attempts remain in denominators. Error examples reference
synthetic case IDs, without copying raw personal text.

## Validation and references

~~~sh
USE_LLM=false USE_MOCKS=true pytest tests -q
python scripts/verify_dispute_adapter_regressions.py
USE_LLM=false python scripts/smoke_dispute_http.py
~~~

OpenAI Docs skill informed schema/refusal handling, not workflow authority:
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
Fixed JWT algorithm allowlist follows [PyJWT API](https://pyjwt.readthedocs.io/en/stable/api.html).
