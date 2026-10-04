# Error analysis — baseline reproduced; learned NOT MEASURED

Baseline version regex-intake-v1; unchanged 384 authored ES/PT utterances.
Each split has 192 cases (96 ES, 96 PT). Counts below overlap by error category.

| Error | Development / 192 | Test / 192 |
|---|---:|---:|
| Amount extraction | 36 | 36 |
| Currency extraction | 12 | 12 |
| Intent extraction | 12 | 12 |
| Clarification false positive | 12 | 12 |
| Expected-null field populated | 0 | 0 |

Representative sanitized references from DEV (not raw customer text):

- group-0009c22232890f00-es-01: amount differs from annotation.
- group-0009c22232890f00-es-08: amount and currency differ.
- group-0009c22232890f00-pt-13: intent differs and unnecessary clarification is signaled.

These are synthetic evaluation case identifiers, not selected banking customers.
Full per-field counts/denominators and all unknown-slot rates are in baseline_metrics.json.
No annotation was changed. The already-frozen baseline TEST is reproduced, not used to
claim an independently optimized learned model. No live learned DEV or TEST call occurred.

Learned error categories, hallucination, false-negative clarification and ES/PT language
effects remain NOT MEASURED. Mocked provider tests prove validation/control behavior,
not actual language-model robustness or accuracy. The live harness exports per-run
errors.json with the same categories and sanitized references; rejected hallucinations
remain counted using raw allowlisted fields before semantic gating.

No winning model, prompt, threshold or improvement claim is justified yet.
