# Baseline & Evaluation Dataset

## Evaluation strategy

Baseline: assumed externally authenticated fixture request → regex extraction →
deterministic offline retrieval checks → static clarification/handoff wording.
Proposed learned system uses the same validated schema, retrieval/ownership/time guards and test data;
only structured extraction and future clarification/summary generation differ.
No agent, live authentication, state engine, API, UI, policy service or learned model is implemented.

## Dataset and truth

384 authored utterances (192 Spanish, 192 Portuguese), 12 source customer groups, one known
transaction per group. 192 development / 192 test, with disjoint customers and transactions.
All utterances are synthetic/team-generated, not observed requests. IDs are fixture aliases;
source transaction fingerprints retain provenance without copying personal customer text.
Attributes come from known transaction records in the existing evidence bundles, NOT from their
heuristic complaint links. Duplicates, foreign owners and boundary timestamps in retrieval fixtures
are deliberate synthetic modifications.

There are 132 controlled retrieval fixtures and 15 safety-contract scenarios. Grouped variants
remain together. Scenario templates are shared across splits: results measure this authored
benchmark, not general linguistic or temporal robustness. ES/PT human linguistic review is pending.
Portuguese source coverage is not observed; Portuguese examples are generated only.

Frozen files refuse silent overwrite. dataset version, signatures, code lock, split grouping
and generation timestamp are in eval_manifest.json. No tuning after test scoring was performed.

## Extraction contract and limitations

Eight fields: intent, transaction_id, amount, currency, merchant, date_hint,
transaction_type_hint, channel_hint. Unknown clues stay null; intent can be unknown.
Amounts are normalized decimal strings; no currency conversion. Dates must be valid calendar dates
or symbolic relative hints; a text-only extractor cannot invent trusted as_of_time.
The v1 ID grammar targets pseudonymized fixture IDs, not arbitrary bank identifiers.
Baseline recognizes explicit ES/PT keywords, selected literal currency codes, quoted merchant
labels and simple decimal/date formats. It can miss paraphrases, unsupported symbols/currencies,
complex negation and contextual clues. Failures remain visible, not repaired after test results.

expected_missing_fields describes all unknown schema fields. expected_missing_required_fields
uses the declared clue-sufficiency rule: ID OR amount+currency+date; this is not a banking policy.
should_clarify/should_handoff labels concern intake, not backend candidate truth or adjudication.

## Baseline results

| population | n | full_schema_EM | schema_valid | hallucinated_fields | clarify_accuracy | missing_required_EM |
|---|---|---|---|---|---|---|
| development/all | 192 | 0.75 | 1.0 | 0 | 0.9375 | 0.8125 |
| development/es | 96 | 0.75 | 1.0 | 0 | 0.9375 | 0.8125 |
| development/pt | 96 | 0.75 | 1.0 | 0 | 0.9375 | 0.8125 |
| test/all | 192 | 0.75 | 1.0 | 0 | 0.9375 | 0.8125 |
| test/es | 96 | 0.75 | 1.0 | 0 | 0.9375 | 0.8125 |
| test/pt | 96 | 0.75 | 1.0 | 0 | 0.9375 | 0.8125 |

Full per-field exact match, precision/recall/F1, null correctness and denominators are in
baseline_metrics.json. Wrong nonnull values count as FP and FN; expected-null/predicted-nonnull
counts as a hallucinated field. Hallucination rates are reported against unknown slots and
predicted populated slots separately. Undefined denominators produce null, not invented 100%.

## Retrieval evaluation

Fixtures cover explicit ID, unique clues, ambiguity, no candidate, future transaction, foreign
customer, wrong currency, inclusive lower/as_of boundaries, expired and invalid auth.
Metrics compare against authored candidate sets. They do NOT measure complaint→transaction recall.
The reference query is an offline fixture function with supplied mock auth status, not a security service.
No unique candidate is automatically selected or called the true observed disputed transaction.

## Handoff rubric and safety

handoff_rubric.json specifies required request/identity/candidates/facts/evidence/actions/unknowns/
questions/guards/state/as_of sections. A valid and a deliberately corrupt fixture verify completeness,
unsupported structured fact detection and invalid evidence references. Section presence does not prove
semantic completeness; unstructured narrative grounding requires human review. No LLM judge runs.
Safety fixtures specify deny, clarify, abstain or handoff. Only offline retrieval boundaries are
implemented/tested now; prompt-injection defense, orchestration, policy and closure remain future work.
Do not report “zero unsafe actions” as production safety: no action runtime exists.

## Language coverage and future LLM evaluation

Report dev/test × es/pt separately. Portuguese results are synthetic-language tests, not evidence
of observed Portuguese customer behavior. Future LLM input is user_utterance only; output must
validate against intake_output.schema.json and semantic calendar checks.
Never pass expected labels or authoritative principal from the user text. Freeze prompt/model/code
before held-out scoring. Keep retrieval guards fixed to isolate the learned component's contribution.
No learned model, classifier, embedding or LLM call was executed.

## Performance, limits and reproducibility

Only local parser latency is measured. External model calls/cost are zero because no model was called;
end-to-end latency, production costs, savings, state validity and operational safety are NOT MEASURED.
Run notebooks/04_mvp_use_case_definition.ipynb then notebooks/05_baseline_and_eval_dataset.ipynb,
or scripts/run_mvp_and_eval.py. Existing profiling/EDA/discovery outputs and raw data are unchanged.
The final MVP outcome remains HANDOFF_RECORDED, not DISPUTE_RESOLVED.
