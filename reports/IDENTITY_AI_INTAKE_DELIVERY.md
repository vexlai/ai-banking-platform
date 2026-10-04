# Phase 2 — Identity & AI Intake

## 1. Current repository assessment

Foundation is implemented: FastAPI, CaseService, SQLite/version/idempotency/audit,
explicit confirmation, read-only dataset/fixture tools and durable handoff. Initial
suite: 115 PASS. Plan numbering was consolidated by the project before this task;
this delivery follows its current Phase 2, not the earlier dataset-tools phase label.
Frozen schema contains eight fields; should_clarify is deterministic derived metadata.
No configured live provider/model/credentials were available. No discovery/EDA reopened.

## 2. Architecture implemented

Bearer → signed identity adapter → existing Principal/CaseService.
Authorized immutable case intake → text-only extractor → schema + support validation
→ unconfirmed suggestions → customer-confirmed Search through existing runtime.
Extraction is consultative POST /v1/disputes/{case_id}/intake-extraction, outside SQLite
transactions. It does not overwrite Case.extracted_clues (original regex suggestions),
select candidates, mutate states or execute handoff. CaseService remains unchanged.

## 3. Trusted Identity implementation

PyJWT verifier, fixed HS256, exact issuer/audience, required sub/customer_id/iat/exp/scopes,
integer timestamps and maximum one-hour lifetime. Principal.provider stores issuer.
Operation-specific scopes remain runtime authority. Generic 401; foreign cases/audit/
handoff/extraction return indistinguishable 404. Text cannot override identity.
Private operator token issuance creates new 0600 files under ignored .tmp, no token logs.
No production IAM, refresh or per-token revocation. Server secret holder is trusted issuer.

## 4. Learned Intake implementation

StructuredIntakeExtractor protocol, frozen RegexBaselineExtractor wrapper and
LearnedStructuredExtractor via existing OpenAI-compatible SDK. Pinned model is required
from operator config, not selected implicitly. Prompt v1 and frozen schema are versioned.
Temperature defaults to zero, timeout 20s, no retries/tools, store=false. Eight fields,
extra-key rejection, calendar/amount/type checks and conservative lexical support gates.
Flags reuse frozen intake_flags. JSON/provider errors produce HTTP 502/model_error;
unsupported output returns null intake + clarification. No silent baseline fallback.
Auth is rechecked after inference. Model metadata is logged without tokens, utterance,
raw provider prose or chain-of-thought. Skill OpenAI Docs informed structured-output
and refusal handling; [official reference](https://developers.openai.com/api/docs/guides/structured-outputs).

## 5. Files created

- src/identity/__init__.py, demo_jwt.py.
- src/intake/__init__.py, schema.py, extractor.py, prompt_v1.txt, evaluation.py.
- api/routes/intake_extraction.py.
- scripts/issue_demo_token.py, scripts/evaluate_intake.py.
- requirements-identity-intake.txt.
- tests/test_identity_intake.py, test_structured_intake.py, test_intake_harness.py.
- docs/IDENTITY_AI_INTAKE.md and this delivery report.
- reports/evaluation/intake/{baseline_metrics,baseline_error_analysis,learned_metrics,
  comparison,language_breakdown,latency_cost}.json and error_analysis.md.

## 6. Files modified

api/dispute_configuration.py, api/dispute_fixture.py, api/main.py: composition only.
README.md, docs/IMPLEMENTATION_PLAN.md and .github/workflows/lint-test.yml: setup/status/CI.
No runtime core, tools, frozen contracts, baseline code, labels or notebook changes.

## 7. Tests added

63 tests: valid/expired/bad-signature/algorithm/issuer/audience/claims/scopes; JWT
configuration; cross-customer resources; identity override text; ES/PT mocked output;
nulls/ambiguity; all authority fields forbidden; invalid JSON/schema/calendar/enums;
hallucinations, known instruction injection, timeout/failure/refusal/truncation/tool
calls; telemetry privacy; post-inference expiry; explicit search/confirm/evidence/handoff;
raw hallucination metric preservation and DEV/freeze/one-use TEST ledger.

## 8. Test results

Full suite: 178 PASS (115 existing + 63 new). Targeted tests use mocked providers, no
external inference. A repeated run exposed a test using a future timestamp computed
at collection time; a slow suite exhausted that margin. Test timestamps now resolve
at execution time, without changing authentication or guards; the full suite was rerun.
HTTP fixture smoke passed with restart and 18 cross-customer denials;
3 cases, 3 handoffs, 11 commands, 11 audit events after replay. Ruff and diff checks pass.
Frozen verifier: 232 protected outputs, 384 baseline predictions and 132 retrieval fixture
results unchanged; 7,671 raw file sizes checked, not rehashed. No raw writes performed.
Historical import-manifest discrepancies remain preexisting; no claim of fully green
remote CI or repaired analytics manifest. CI workflow updated, not remotely executed.

## 9. Baseline metrics

Unchanged regex-intake-v1; reproduced all 384 saved predictions exactly. TEST n=192:
full-schema exact match 144/192 (75%); schema validity 192/192 (100%);
should_clarify correctness 180/192 (93.75%); missing-required-clues 156/192 (81.25%).
Hallucinated fields: zero against annotated unknown slots (denominators in JSON).
Per-field exact match/precision/recall/F1/null correctness are fully exported.

## 10. Learned metrics

**NOT MEASURED.** Adapter/unit tests are implemented, but no live model calls, DEV
scores, model configuration freeze or learned TEST scoring occurred. Placeholder files
say NOT_MEASURED explicitly. No fabricated cost/accuracy or mock-as-model results.

## 11. Baseline vs Learned comparison

**Cannot establish superiority or parity.** comparison.json records null for learned
outperformed baseline. Harness uses identical frozen workload and metrics, separates
DEV/TEST, hashes config/code/prompt/schema/data/runtime versions and requires matching
returned model version before freeze. A one-use TEST ledger is written before inference.
Further prompt optimization cannot be presented as independent testing on this holdout.
Raw allowlisted model fields are measured before rejection, so gates do not erase
hallucinations. Delivered-output scores and raw-model scores are separately labeled.

## 12. ES/PT breakdown

Each split: 96 ES and 96 PT authored cases. Baseline TEST in each language: 72/96 full
schema, 90/96 clarification, 78/96 missing-required clues, 96/96 schema valid. PT is
team-generated, not observed Portuguese banking behavior. Learned ES/PT: NOT MEASURED.

## 13. Latency and cost

Local baseline adapter TEST n=192: p50 0.0710ms, p95 0.1417ms; API model cost zero,
not a claim of zero compute cost. Breakdown in latency_cost.json. Learned latency,
token usage and cost per attempted case: NOT MEASURED. Runtime supports usage and
operator-supplied tariff estimates; unknown request cost remains null. Live harness
requires pricing reference and explicit positive budget; allowance is not a billing cap.

## 14. Error analysis

Per 192-case split baseline has 36 amount, 12 currency and 12 intent errors; 12 false
positive clarification signals. Categories overlap. Sanitized fixture references in
error_analysis.md / baseline_error_analysis.json. No learned error conclusions yet.
Source IDs are pseudonymized; arbitrary banking IDs remain available through explicit
Search rather than inventing new extraction grammar. Learned semantic gates are
conservative and may reject legitimate paraphrases: effect must be measured on DEV.

## 15. Known limitations

Live model evaluation is blocked by missing provider/model credentials and budget.
No winning configuration exists. Mocked injection tests prove isolation/control only,
not LLM robustness. No complete conversation, summary, ranking or financial authority.
JWT is demo IAM; protect issuer secret, rotate to revoke globally. No rate limiting or
extraction-result cache; repeated advisory calls can cost money. Privacy limits raw
output retention to allowlisted fields in synthetic eval; failure prose is hashed.
Inherited timezone/snapshot/availability limits of dataset serving remain unchanged.

## 16. Phase 2 Definition of Done status

| Criterion | Status | Evidence / remaining work |
|---|---|---|
| Trusted demo identity exists | PASS | Signed JWT adapter + private operator issuance |
| Identity independent of text | PASS | Override tests, no model authority path |
| Signature/issuer/audience/expiry/scope validated | PASS | Verifier + runtime scopes, negative tests |
| Cross-customer tests | PASS | Existing/new resource isolation |
| Learned Structured Extractor exists | PASS | SDK adapter/protocol implemented; live quality unmeasured |
| Output schema validated | PASS | Frozen eight-field structure and semantic validation |
| No authority fields from LLM | PASS | Extra fields rejected; no state/tool access |
| Prompt/model/schema versioned | PARTIAL | Prompt/schema/config machinery exists; selected live snapshot not frozen |
| Baseline remains frozen | PASS | 384 identical predictions; hashes preserved |
| Baseline vs learned evaluation runs reproducibly | PARTIAL | Harness tested, baseline run; no live comparison |
| ES metrics reported | PARTIAL | Baseline yes; learned pending |
| PT metrics reported | PARTIAL | Baseline yes, team-generated; learned pending |
| Hallucinated-field rate measured | PARTIAL | Baseline and metric tests; live learned pending |
| should_clarify accuracy measured | PARTIAL | Baseline only; model flags stay deterministic |
| p50/p95 latency measured | PARTIAL | Baseline only |
| Cost/case estimated | PARTIAL | Baseline API cost zero; learned unknown |
| Error analysis generated | PARTIAL | Baseline + mock boundary failures, not live learned errors |
| Existing safety guards unchanged | PASS | CaseService/state/tools unchanged |
| Existing suite remains green | PASS | Full suite 178 PASS |

Overall: **PARTIAL — not closed**, not a PASS for the phase as a whole.

## 17. Recommended next step

Configure a trusted provider and pinned model, inject INTAKE_API_KEY privately, provide
tariffs/reference and an evaluation budget. Run learned DEV, review without tuning on
TEST, freeze config, then one held-out TEST and comparison/error analysis. Only after
that decision should Phase 3 — Investigation Intelligence begin. It was not implemented.
