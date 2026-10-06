# MVP Use Case Definition

## Executive Decision

**Transaction Dispute Intake & Investigation Copilot**

Decision: **GO WITH CONSTRAINTS**. Recommended workflow: **Option C, incorporating Option B
after explicit transaction selection**. This is not an autonomous dispute resolver, fraud
adjudicator or reimbursement system. This notebook freezes the selected use case, not a new search.

## Problem Evidence

| cohort | records | customers | date_min | date_max | claimed_amount_present | claimed_amount_pct | currency_present | currency_pct | amount_currency_present | resolution_present | resolution_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 11571 | 11137 | 2023-06-17 15:37:40 | 2026-06-17 23:34:11 | 4500 | 38.8903292714545 | 4487 | 38.777979431336966 | 4302 | 2721 | 23.515685766139487 |
| B | 10477 | 10121 | 2023-06-17 15:37:40 | 2026-06-17 23:34:11 | 4090 | 39.03789252648659 | 4076 | 38.904266488498614 | 3907 | 2459 | 23.47045910088766 |
| C | 10373 | 10022 | 2023-06-17 13:19:54 | 2026-06-17 23:10:30 | 4033 | 38.87978405475754 | 4049 | 39.0340306565121 | 3822 | 2319 | 22.35611684180083 |

B is primary because Claims/Complaints explicitly record Transactions / Cargo no reconocido;
A is sensitivity (B subset of A), C is a separate optional fees lane, not pooled.
Prior 30d in B: **5,253 no / 3,015 unique / 2,209 multiple**, denominator **10,477**.
Percentages are 50.14%, 28.78%, 21.08% respectively (rounded).
Among 3,907 with amount+currency there is no exact candidate linkage; tolerances are heuristics.
No complaint→transaction ground truth; affected-product ownership is invalid for attribution,
origin_interaction_id is entirely null. A unique candidate is never a verified disputed transaction.


Digital context (denominator: candidate transactions):

| time_window | candidate_transactions | fully_observed_window_transactions | transactions_with_digital_context | transaction_coverage_pct | transaction_event_pairs | distinct_identified_events | pairs_with_recorded_product_id | product_id_pct_pairs |
|---|---|---|---|---|---|---|---|---|
| before_30m | 35583 | 35582 | 11 | 0.0309136385352556 | 70 | 70 | 3 | 4.285714285714286 |
| before_2h | 35583 | 35578 | 36 | 0.10117190793356379 | 275 | 275 | 27 | 9.818181818181818 |
| before_24h | 35583 | 35570 | 338 | 0.9498918022651266 | 2665 | 2630 | 240 | 9.00562851782364 |
| after_24h | 35583 | 35562 | 304 | 0.8543405558834275 | 2494 | 2431 | 226 | 9.061748195669606 |

Transcripts (denominator: nearby unique interactions):

| relevant_unique_interactions | interactions_with_transcript | transcript_available_rate_pct |
|---|---|---|
| 1624 | 410 | 25.246305418719214 |

ML fraud/ranking is not justified as an MVP dependency: severe imbalance, weak descriptive
non-score differences, unresolved label construction/availability and no matching labels.
Structured language extraction is a different, independently evaluable learned component.
Classification remains OBSERVED FACT / DERIVED FEATURE / HEURISTIC / INFERRED RELATIONSHIP /
HYPOTHESIS / FUTURE DESIGN. Source outputs are reused, not recomputed.

## User Problem

An authenticated customer reports an unrecognized transaction.
Help identify candidate transactions, clarify missing clues, collect verifiable evidence,
preserve uncertainty and prepare a useful human handoff. Do not claim fraud determination
or dispute resolution. User-provided IDs and amounts are clues, not trusted account authority.

## Business Problem

**PROJECTED / HYPOTHESIS:** reduce manual intake repetition,
standardize handoffs, reduce evidence omissions, improve traceability and reduce ungrounded decisions.
No measured production time/cost savings, ROI or dispute-resolution uplift is claimed.

## Scope

### In Scope

| capability | boundary |
|---|---|
| authenticated intake | Future MVP scope; not runtime implemented in 04/05 |
| structured clue extraction | Future MVP scope; not runtime implemented in 04/05 |
| clarification | Future MVP scope; not runtime implemented in 04/05 |
| deterministic transaction lookup | Future MVP scope; not runtime implemented in 04/05 |
| bounded candidate retrieval | Future MVP scope; not runtime implemented in 04/05 |
| explicit transaction confirmation | Future MVP scope; not runtime implemented in 04/05 |
| ownership verification | Future MVP scope; not runtime implemented in 04/05 |
| evidence retrieval | Future MVP scope; not runtime implemented in 04/05 |
| historical context retrieval | Future MVP scope; not runtime implemented in 04/05 |
| grounded summarization | Future MVP scope; not runtime implemented in 04/05 |
| unknown/missing evidence representation | Future MVP scope; not runtime implemented in 04/05 |
| state tracking | Future MVP scope; not runtime implemented in 04/05 |
| human handoff | Future MVP scope; not runtime implemented in 04/05 |
| audit/provenance | Future MVP scope; not runtime implemented in 04/05 |

### Out of Scope

| capability | status |
|---|---|
| autonomous dispute adjudication | Excluded |
| automatic reimbursement | Excluded |
| money movement | Excluded |
| fraud verdict | Excluded |
| automated rejection | Excluded |
| automatic complaint-to-transaction linking | Excluded |
| automatic closure | Excluded |
| invented banking policy | Excluded |
| unsupported customer identity inference | Excluded |

## AI / Deterministic / Human Responsibility Matrix

| owner | allowed | forbidden |
|---|---|---|
| AI / LLM | intent/clue extraction; clarification drafting; evidence-grounded summary; unresolved questions; handoff draft | auth/authz; ownership; resolving ambiguity as truth; policy invention; fraud verdict; approval/rejection; financial action; closure |
| DETERMINISTIC | external auth validation; authorization/account access; retrieval/filtering; temporal cutoff; currency/units; ownership; state guards; policy interface; audit; idempotency | inventing policy, treating heuristic candidate as true match, claiming dataset identity equals authentication |
| HUMAN | unresolved ambiguity; conflicts; authoritative policy interpretation; adjudication; financial decisions; final outcome; closure | bypassing authentication/authorization or leaving approvals unaudited |

## Workflow

AUTHENTICATED_REQUEST → INTAKE → CLUE_EXTRACTION → TRANSACTION_SEARCH
→ candidate branching → explicit confirmation → OWNERSHIP_VERIFICATION → EVIDENCE_COLLECTION
→ GROUNDED_SUMMARY → POLICY_GATE → HUMAN_HANDOFF.

- Normal: explicit ID or candidate, attributed customer/human confirmation, ownership, evidence, handoff.
- Ambiguous: multiple candidates → clarification; unresolved alternatives remain for human review.
- Unsupported/no candidate: preserve empty result/missing clues; clarify or handoff, never reject by inference.
- Human intervention: conflicts, missing required evidence/policy, financial decisions and adjudication.

Reuse the stage-03 transition specification unchanged. Authentication is an external dependency,
not implemented from dataset customer_id. No state machine engine is implemented here.
HANDOFF_RECORDED is the observable outcome; RESOLVED/CLOSED require external authorized outcome.

## Data Contracts

| contract | required_fields | optional_fields | provenance | as_of_time_rule | trust_level | LLM_values_require_confirmation |
|---|---|---|---|---|---|---|
| AuthenticatedPrincipal | ['principal_ref', 'subject_ref', 'authorization_scope', 'verified_at', 'expires_at', 'auth_provider_ref'] | ['session_ref'] | External identity provider; never utterance/LLM | verified_at <= as_of_time < expires_at | trusted only after external deterministic validation | False |
| DisputeIntake | ['case_id', 'user_utterance', 'language', 'principal_ref', 'as_of_time', 'request_id'] | ['customer_confirmed_clues'] | Untrusted customer request; exact text retained with access controls | server-assigned case.as_of_time | untrusted input | True |
| TransactionSearchRequest | ['case_id', 'principal_ref', 'as_of_time', 'rule_version', 'lookback_days'] | ['transaction_id', 'amount', 'currency', 'date_hint', 'merchant', 'transaction_type_hint', 'channel_hint'] | Confirmed clues and trusted principal separately; no currency/date guessing | bounded event_time <= as_of_time; explicit start/end inclusivity | validated request, not fact | True |
| TransactionCandidate | ['candidate_transaction_id', 'owner_ref', 'product_ref', 'event_time', 'amount', 'currency', 'source_ref', 'retrieval_rule'] | ['merchant', 'recorded_status', 'channel', 'type'] | Deterministic query result; relation to complaint is HEURISTIC | event_time <= as_of_time; availability warning mandatory | observed transaction, unverified dispute link | False |
| TransactionSelection | ['case_id', 'candidate_transaction_id', 'confirmed_by', 'confirmed_at', 'confirmation_ref'] | ['clarification_history'] | Explicit customer/authorized-human confirmation; never count=1 alone | confirmation timestamp audited | attributed selection, not fraud verdict | True |
| EvidenceBundle | ['case_id', 'as_of_time', 'source_refs', 'core_facts', 'unknowns', 'guard_results', 'availability_limitations'] | ['optional_context', 'retrospective_context'] | Allowlisted source evidence, independently aggregated domains | admissible and retrospective evidence separate; snapshot attributes flagged | mixed trust with field provenance | False |
| GroundedSummary | ['case_id', 'facts_with_evidence_refs', 'unknowns', 'unresolved_questions', 'generator_version'] | ['draft_narrative'] | LLM-generated draft; deterministic references + human factual review | only intake-admissible evidence may be asserted as intake facts | untrusted generated content | True |
| HandoffPackage | ['case_id', 'user_request', 'authenticated_identity_reference', 'selected_transaction_or_candidates', 'verified_facts', 'evidence_references', 'actions_taken', 'missing_evidence', 'unresolved_questions', 'guard_results', 'state', 'as_of_time'] | ['draft_summary', 'handoff_receipt'] | Deterministic assembly; optional generated draft; authorized recipient | evidence snapshot/as_of plus handoff time distinct | auditable package, not adjudication | True |
| CaseState | ['case_id', 'state', 'version', 'updated_at', 'last_transition_id'] | ['failure_reason'] | Deterministic guarded state store; FUTURE DESIGN | versioned event/recorded timestamps | trusted only after guards; no engine implemented | False |
| AuditEvent | ['event_id', 'case_id', 'request_id', 'idempotency_key', 'actor_ref', 'source_state', 'target_state', 'event_time', 'recorded_at', 'evidence_refs', 'guard_results', 'rule_version'] | ['policy_version', 'model_version', 'approval_ref'] | Append-only future service audit; immutable evidence versions | event_time and recorded_at separately | system-generated; LLM cannot author authority | False |

All LLM-originated fields carry source spans and generator/prompt version and remain untrusted
until validated; customer-confirmed clues and trusted external principal are distinct.
Contracts are conceptual specifications, not Pydantic models or production services.

## Evidence Model

| level | contents | limit |
|---|---|---|
| CORE | transaction ID; customer ownership; product relationship; timestamp; amount+currency; type; channel; recorded status | Observed structure does not prove fraud or historical availability of status |
| OPTIONAL | merchant; geo; service; transcript; digital; historical behavior | Missingness explicit; service/digital proximity is not causal linkage |
| QUARANTINED / UNSAFE FOR AUTHORITY | fraud_score; is_fraud as verdict; inferred complaint link; temporal proximity as proof; anonymous digital events | Never decision authority; never stitch anonymous identities |

## Time Safety

Freeze case.as_of_time from trusted server context. Where applicable,
intake evidence must satisfy event_time <= case.as_of_time. Keep INTAKE-ADMISSIBLE EVIDENCE separate
from RETROSPECTIVE ANALYTICAL EVIDENCE; future candidates are never eligible at intake.
Historical features require history.event_time < candidate.event_time and explicit left-censor flags.
Availability-time safety is not fully certified: ingestion/revision timestamps are absent; snapshot
status, fraud flags and transcript availability require warnings. Resolution after intake is not
contemporaneous evidence. Relative language dates stay symbolic until resolved against trusted
as_of_time and a confirmed time zone; user_utterance alone must not invent a reference date.

## Success Criteria

| criterion | measurement | target_or_status |
|---|---|---|
| extraction correctness | per-field EM/P/R/F1 and full-schema EM, dev/test and es/pt separately | Report baseline; future improvement on frozen test without degrading safety |
| schema validity | valid schemas / outputs | 100% proposed acceptance gate |
| hallucination | unsupported nonnull fields / expected-unknown slots and / predicted slots | 0 desired; observed baseline failures retained |
| clarification and missing clues | should_clarify accuracy; exact missing required clue set | Baseline first; human-reviewed annotations needed |
| retrieval invariants | exact candidate set; missing/extra; future/ownership/auth exposure | 100% fixture correctness; zero safety violations |
| abstention | correct deny/clarify/abstain/handoff on contract fixtures | No autonomous decision; safety scenarios mandatory |
| handoff quality | completeness; unsupported structured claims; valid evidence refs | All required sections; no unsupported facts |
| state/audit validity | valid guarded transitions and audit fields | Future runtime only; NOT MEASURED here |
| unsafe actions / authorization violations | forbidden actions or access violations / attempted requests | Zero required; fixture checks are not production certification |
| latency/cost | per-case parser latency; future end-to-end/model cost | Report measured parser only; no invented production savings |

Targets are proposed acceptance gates, not measured achievements. Dispute-resolution accuracy
and observed complaint→transaction recall are excluded because the required truth does not exist.
Future learned extraction uses the identical schema, frozen fixtures and deterministic retrieval:
improvement must come from extraction/clarification, not changed access or candidate rules.

## Demo Scenarios

| scenario | es | expected |
|---|---|---|
| 1 Normal / explicit confirmation | No reconozco la transacción [ID]; quiero revisar sus detalles. | Exact lookup, explicit confirmation, ownership, evidence, handoff |
| 2 Ambiguous | No reconozco un cargo por ese importe; aparecen varias operaciones. | Clarify; preserve candidates; never auto-select truth |
| 3 No candidate / unsupported | No encuentro el cargo que quiero reclamar. | Document missing evidence and retrieval limits; human handoff |

Portuguese evaluation is required, but the source transcript language field has only es
(171,321 records; checked from the existing curated table). No observed Portuguese textual
coverage is claimed. Portuguese utterances in 05 are synthetic/team-generated, human linguistic
review pending. These are scenario definitions, not selected individual demo customers.

## Frozen MVP Contract

**Version: mvp-contract-v1 — GO WITH CONSTRAINTS**

**What we build:** Transaction Dispute Intake & Investigation Copilot; authenticated intake,
structured clues, deterministic bounded retrieval, explicit selection, ownership check, evidence,
optional grounded summary and auditable human handoff. Primary analogue cohort B; no gold dispute linkage.

**What we do not build:** autonomous adjudication, fraud verdict, rejection, reimbursement,
money movement, automatic linkage/closure, invented policy or inferred identity.

**Required future services:** external IAM/authz, transaction/evidence queries, guarded case/audit
store with idempotency, authoritative policy interface and human queue. No production service
or state engine is implemented in these notebooks.

**LLM:** draft extraction, clarification, questions, grounded summary and handoff; outputs are untrusted.
It never owns auth, authorization, ownership, policy eligibility, financial decisions or closure.

**Deterministic:** validate identity/scope and clues, retrieve and filter, enforce time/currency/
ownership, schema/provenance/guard checks, policy interface, audit and idempotency.

**Human:** unresolved ambiguity/conflicts, policy interpretation, adjudication, financial decisions,
authorized final outcome and closure. Missing policy blocks automated decisions.

**Learned component:** Structured Dispute Intake Extraction; no fraud/ranking model dependency.
Evaluate against a regex baseline on frozen grouped dev/test cases. Generated ground truth is
explicitly synthetic, never inherited from complaint linkage.

**Final observable MVP outcome: HANDOFF_RECORDED — NOT DISPUTE_RESOLVED.**
Changing scope, schema, annotation or test cases requires a new version and documented review.
