# Phase 2 — Identity & AI Intake

## 1. Current repository assessment

Foundation: FastAPI, CaseService, SQLite, versioning/idempotency/audit, fixture/dataset
tools, explicit confirmation and durable HANDOFF_RECORDED. Initial suite 115 PASS.
No discovery reopened. Frozen intake has eight fields; should_clarify is derived.

## 2. Architecture implemented

Bearer → identity adapter → existing Principal/CaseService. Authorized immutable case
utterance → extractor → schema/support gates → unconfirmed suggestions. Existing Search
still requires confirmed clues. Extraction does not mutate case/state, select candidates,
execute tools or handoff, or overwrite Case.extracted_clues. CaseService unchanged.

## 3. Trusted Identity implementation

PyJWT fixed HS256, required sub/customer_id/iss/aud/iat/exp/scopes, exact issuer/audience,
integer timestamps and maximum one-hour lifetime. Runtime retains operation scopes.
Generic authentication denial; foreign resources indistinguishable from absent resources.
Private operator issuance writes new 0600 token files; no token logs. User text cannot
override identity. Demo IAM only, not production revocation/refresh infrastructure.

## 4. Learned Intake implementation

StructuredIntakeExtractor protocol, frozen regex wrapper, OpenAI-compatible SDK adapter.
POST /v1/disputes/{case_id}/intake-extraction authorizes before and after inference.
Only utterance sent, no principal/token/labels. Frozen eight-field Pydantic schema,
extra-field rejection, calendar/amount checks and conservative lexical support gates.
Provider/schema failure → HTTP 502/model_error; unsupported output → null intake and
clarification. No silent fallback. No model authority or SQLite lock during inference.
Selected gpt-5.6-luna, temperature 0, reasoning none, timeout 20s, max output 400,
no retries/tools, store=false. Metadata only; no chain-of-thought or raw PII logging.
OpenAI Docs guided structured output/refusal handling. Configuration and pricing source:
reports/evaluation/intake/openai_luna_v1_config.json.

## 5. Files created

- src/identity/{__init__,demo_jwt}.py; src/intake/{__init__,schema,extractor,evaluation}.py and prompt_v1.txt.
- api/routes/intake_extraction.py; requirements-identity-intake.txt.
- scripts/{issue_demo_token,evaluate_intake,report_intake_results}.py.
- tests/test_identity_intake.py, test_structured_intake.py, test_intake_harness.py.
- docs/IDENTITY_AI_INTAKE.md; this report; reports/evaluation/intake/ reports and immutable run outputs.

## 6. Files modified

api/dispute_configuration.py, api/dispute_fixture.py, api/main.py (composition only),
README.md, docs/IMPLEMENTATION_PLAN.md, .github/workflows/lint-test.yml.
No runtime core, transaction tools, frozen baseline/labels/contracts or notebook changes.

## 7. Tests added

63 tests cover JWT signature/algorithm/claims/time/issuer/audience/scopes; resource
isolation and identity override; ES/PT mocked extraction, nulls, authority fields,
malformed/schema-invalid outputs, unsupported fields, injection patterns, provider
failure/timeout/refusal/truncation, telemetry privacy, post-inference expiry, integration
through explicit search/confirm/evidence/handoff, raw hallucination metrics and one-use TEST.

## 8. Test results

Full suite: 178 PASS (115 existing + 63 new). Provider unit/integration tests are mocked;
live calls below evaluate extraction, not a complete live-LLM HTTP journey.
Earlier fixture HTTP smoke passed restart, 18 cross-customer denials, three cases,
three handoffs, 11 commands and 11 audit events after replay. Frozen verifier: 232
protected outputs, 384 identical baseline predictions, 132 identical retrieval fixtures.
7,671 raw file sizes checked, not content-rehashed. Historical analytics import-manifest
discrepancies remain preexisting; remote CI is not claimed verified.

## 9. Baseline metrics

TEST n=192: full-schema 144/192 (75%); schema validity 192/192; clarification 180/192
(93.75%); missing-required-clues 156/192 (81.25%); hallucinated fields 0/1,056 unknown
slots. Per-field exact/precision/recall/F1/null correctness exported without label changes.

## 10. Learned metrics

Run openai-luna-v1: DEV 192 cases, full-schema 165/192 (85.94%), six unsupported outputs.
Configuration frozen 2026-10-04T23:01:03Z, then TEST scored once, no subsequent tuning.
TEST full-schema 167/192 (86.98%); model schema 192/192; delivered schema 190/192
(two whole outputs rejected, not malformed JSON); clarification 192/192;
missing-required-clues 167/192. No provider failures/retries/fallback.
Raw hallucinations 2/1,056 unknown slots (0.1894%); delivered 0/1,056.

## 11. Baseline vs Learned comparison

Full-schema +11.98 percentage points; clarification +6.25 points. Not universal
superiority: regex is faster and has no raw hallucinations. Both unsupported model
transaction_type_hint values were blocked. Retain gates, confirmation and baseline option.
Raw and delivered metrics remain separate. Immutable run artifacts and config/code/data
hashes support traceability; the one-use TEST ledger prevents presenting retuning as
independent testing. Root report views explicitly supersede NOT_MEASURED placeholders.

## 12. ES/PT breakdown

Each split has 96 ES and 96 PT cases. TEST baseline full-schema 72/96 per language.
Learned ES 86/96 (89.58%); PT 81/96 (84.38%); clarification 96/96 each.
Raw hallucinations ES 2/528 unknown slots, PT 0/528. PT is team-generated, not observed
Portuguese banking behavior. These are authored evaluation utterances, not resolution truth.

## 13. Latency and cost

Baseline TEST p50 0.0710ms/p95 0.1417ms, external model cost zero (not zero CPU cost).
Learned TEST p50 1,211.79ms/p95 1,508.16ms; estimated USD 0.000167933 per attempt.
DEV USD 0.032236 + TEST USD 0.0322432 + one DEV compatibility probe USD 0.0001748
= USD 0.064654, 385 calls total, against USD 2 authorization. All costs have usage
metadata. Tariff estimates, not invoice or production benchmark. No further calls needed.

## 14. Error analysis

Raw TEST categories overlap: amount 16, currency 9, transaction type 2, hallucination 2.
Delivered amount errors 18 because two entire outputs were rejected. No clarification
errors on this workload. Baseline per split: amount 36, currency 12, intent 12,
clarification false positives 12. Sanitized synthetic case references and denominators
are in reports/evaluation/intake/error_analysis.md; no raw customer transcript exposure.

## 15. Known limitations

No blocking evaluation dependency remains. Model/config/returned identifier are pinned,
but gpt-5.6-luna is not a dated immutable-weights snapshot; future provider drift is possible.
TEST is consumed; future tuning requires a new independent holdout. Mocked adversarial
tests certify boundary behavior, not general live-model prompt-injection robustness.
No full conversation, summary, production IAM, rate limiting or extraction cache.
Repeated advisory requests can cost money. Historical serving/timezone/snapshot limits
remain. No measured production benefit or financial authority is claimed.

## 16. Phase 2 Definition of Done status

| Criterion | Status | Evidence |
|---|---|---|
| Trusted demo identity exists | PASS | Signed JWT adapter |
| Identity independent of text | PASS | Override tests, no model authority path |
| Signature/issuer/audience/expiry/scope validated | PASS | Verifier and runtime negative tests |
| Cross-customer tests | PASS | Existing and new resource isolation |
| Learned Structured Extractor exists | PASS | SDK adapter plus live evaluation |
| Output schema validated | PASS | Frozen schema and semantic gates |
| No authority fields from LLM | PASS | Extra keys rejected, no state/tool access |
| Prompt/model/schema versioned | PASS | Config lock/hashes/returned ID; alias drift limitation above |
| Baseline vs learned evaluation reproducible | PASS | Frozen workload and runner; stochastic/provider limits apply |
| ES metrics reported | PASS | 96 TEST cases |
| PT metrics reported | PASS | 96 team-generated TEST cases |
| Hallucinated-field rate measured | PASS | Raw and delivered separately |
| should_clarify measured | PASS | Frozen deterministic flags, 192 TEST cases |
| p50/p95 measured | PASS | Per attempt and language |
| Cost/case estimated | PASS | Usage/tariffs, not invoice |
| Error analysis generated | PASS | Categories and sanitized references |
| Baseline remains frozen | PASS | Hashes and 384 predictions |
| Existing safety guards unchanged | PASS | Runtime core unchanged |
| Existing suite remains green | PASS | 178 tests |

Overall: PASS for the bounded offline phase, not production certification.

## 17. Recommended next step

Phase 3 — Investigation Intelligence: controlled clarification and grounded narrative
with independent evaluation and unchanged deterministic authority. Not implemented here.
Regenerate report views without inference: python scripts/report_intake_results.py.
Do not rerun TEST or modify this frozen prompt based on held-out errors.
