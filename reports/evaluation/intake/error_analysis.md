# Intake error analysis

Completed run: openai-luna-v1. TEST was scored once after configuration freeze; no post-test tuning.

## Raw model errors (192 TEST cases; overlapping categories)

- amount_extraction: 16
- currency_extraction: 9
- transaction_type_hint_extraction: 2
- hallucination: 2

Two unsupported transaction_type_hint values occurred in ES; both complete outputs were rejected. Raw hallucination: 2/1,056 unknown slots; delivered: 0/1,056. Delivered amount errors include the two rejected outputs (18 versus 16 raw).

Baseline per split: 36 amount, 12 currency, 12 intent errors and 12 clarification false positives (overlapping). Learned clarification: 192/192 correct. ES full-schema 86/96; PT 81/96. PT is team-generated, not observed banking behavior.

## Sanitized references

- group-001d624f0208b967-es-01 (es): amount_extraction
- group-001d624f0208b967-es-12 (es): amount_extraction
- group-001d624f0208b967-pt-07 (pt): currency_extraction
- group-001d624f0208b967-pt-12 (pt): amount_extraction
- group-00220e2ed3b7e926-es-07 (es): currency_extraction
- group-00220e2ed3b7e926-es-08 (es): currency_extraction, transaction_type_hint_extraction, hallucination
- group-00220e2ed3b7e926-es-12 (es): amount_extraction
- group-00220e2ed3b7e926-pt-07 (pt): currency_extraction

These references point to synthetic fixtures, not customer transcripts. Conservative gates can reject legitimate paraphrases. This sample does not certify prompt-injection robustness or production performance.
