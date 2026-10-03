# Dispute Case Workflow Findings

## 1. Executive conclusion

**GO WITH CONSTRAINTS** for a stateful dispute-intake / candidate-retrieval / evidence / human-handoff
system. **NO-GO for autonomous adjudication or financial action.** The dataset supplies grounded
transaction records but does not supply complaint-to-transaction truth, authentication, policy,
decision authority or an operational case transition log.

Executed: 2026-10-02T22:51:49.519170-05:00. Inherited cutoff: 2026-06-17 inclusive.
Transactions/complaints/service/digital after this cutoff are audited and excluded from this stage.
No general EDA or profiling is rerun. See population_cutoff_audit.csv for exact exclusions.
All computations are exhaustive over the stated populations; no sampling or demo-customer selection.

Classification convention throughout:
OBSERVED FACT = supplied field; DERIVED FEATURE = documented aggregate;
HEURISTIC = retrieval rule/cohort/archetype; INFERRED RELATIONSHIP = same-customer temporal association;
HYPOTHESIS = possible later interpretation; FUTURE DESIGN = unimplemented architecture.
No unique candidate becomes a verified dispute link.

## 2. Dispute cohort recommendation

| cohort | records | customers | date_min | date_max | claimed_amount_present | claimed_amount_pct | currency_present | currency_pct | amount_currency_present | resolution_present | resolution_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 11571 | 11137 | 2023-06-17 15:37:40 | 2026-06-17 23:34:11 | 4500 | 38.8903292714545 | 4487 | 38.777979431336966 | 4302 | 2721 | 23.515685766139487 |
| B | 10477 | 10121 | 2023-06-17 15:37:40 | 2026-06-17 23:34:11 | 4090 | 39.03789252648659 | 4076 | 38.904266488498614 | 3907 | 2459 | 23.47045910088766 |
| C | 10373 | 10022 | 2023-06-17 13:19:54 | 2026-06-17 23:10:30 | 4033 | 38.87978405475754 | 4049 | 39.0340306565121 | 3822 | 2319 | 22.35611684180083 |

| cohort | sql_predicate | semantic_strength | semantic_weakness | linkage_limitation | potential_role | relationship_class |
|---|---|---|---|---|---|---|
| A | case_type IN ('Complaint','Claim') AND category='Transactions' | Explicit transaction category in Claim/Complaint | Includes unspecified subcategory | Customer only; no verified transaction or origin-interaction link | Broad sensitivity population | HEURISTIC cohort, not ground truth |
| B | case_type IN ('Complaint','Claim') AND category='Transactions' AND subcategory='Cargo no reconocido' | Explicit recorded Cargo no reconocido | Allegation not adjudication; B is subset of A | Customer only; no verified transaction or origin-interaction link | Primary discovery scope, subject to evidence and human review | HEURISTIC cohort, not ground truth |
| C | case_type IN ('Complaint','Claim') AND category='Fees' AND subcategory='Cobro indebido' | Explicit recorded Cobro indebido | Fees may not correspond to an individual transaction | Customer only; no verified transaction or origin-interaction link | Separate optional intake lane, not pooled with B | HEURISTIC cohort, not ground truth |

Recommend **B** as the primary discovery/development intake scope because its recorded allegation
is specific, not because of its size. Use **A** as a broader sensitivity population (B is a subset,
so counts must not be added). Keep **C** as a separate optional fees lane: the fee may not map to
a transaction amount. None is a gold-truth dispute population.
Status, priority, reception channel and repeat-complainer distributions are in
candidate_cohort_distributions.csv. These are snapshot descriptions, not proven creation-time values.
Resolution coverage is retrospective observability only; no resolution information enters bundles.

## 3. Transaction candidate retrieval

Trusted linkage is complaint.customer_id only. Neither affected_product_id nor origin_interaction_id
is used. The former has inherited ownership mismatches; the latter is entirely null.
Search uses exact timestamps in symmetric ±24*n-hour windows; boundaries are inclusive.
Historical same-customer baseline means transactions before each customer's last in-scope complaint,
deduplicated by transaction ID. It is a descriptive comparison, not a per-complaint as-of feature.

| cohort | days | eligible_complaints | zero_candidates | unique_candidate | multiple_candidates | candidate_count_mean | candidate_count_median | candidate_count_p90 | candidate_count_p95 | candidate_count_max | complete_window_complaints | boundary_censored_complaints |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 1 | 11571 | 10961 | 587 | 23 | 0.05479215279578256 | 0.0 | 0.0 | 1.0 | 3 | 11556 | 15 |
| A | 3 | 11571 | 9900 | 1497 | 174 | 0.16091954022988506 | 0.0 | 1.0 | 1.0 | 4 | 11516 | 55 |
| A | 7 | 11571 | 8194 | 2593 | 784 | 0.376371964393743 | 0.0 | 1.0 | 2.0 | 5 | 11423 | 148 |
| A | 14 | 11571 | 6042 | 3339 | 2190 | 0.764670296430732 | 0.0 | 2.0 | 3.0 | 8 | 11290 | 281 |
| A | 30 | 11571 | 3549 | 2958 | 5064 | 1.6450609281825253 | 1.0 | 4.0 | 5.0 | 15 | 10958 | 613 |
| B | 1 | 10477 | 9928 | 531 | 18 | 0.054213992555120744 | 0.0 | 0.0 | 1.0 | 3 | 10464 | 13 |
| B | 3 | 10477 | 8980 | 1345 | 152 | 0.15872864369571443 | 0.0 | 1.0 | 1.0 | 4 | 10427 | 50 |
| B | 7 | 10477 | 7440 | 2337 | 700 | 0.37243485730648085 | 0.0 | 1.0 | 2.0 | 5 | 10341 | 136 |
| B | 14 | 10477 | 5481 | 3018 | 1978 | 0.7611911806814928 | 0.0 | 2.0 | 3.0 | 8 | 10221 | 256 |
| B | 30 | 10477 | 3205 | 2687 | 4585 | 1.6411186408322993 | 1.0 | 4.0 | 5.0 | 15 | 9921 | 556 |
| C | 1 | 10373 | 9829 | 520 | 24 | 0.054757543622867055 | 0.0 | 0.0 | 1.0 | 2 | 10354 | 19 |
| C | 3 | 10373 | 8842 | 1374 | 157 | 0.1639834184903114 | 0.0 | 1.0 | 1.0 | 4 | 10323 | 50 |
| C | 7 | 10373 | 7251 | 2437 | 685 | 0.3816639352164273 | 0.0 | 1.0 | 2.0 | 5 | 10246 | 127 |
| C | 14 | 10373 | 5418 | 2966 | 1989 | 0.758893280632411 | 0.0 | 2.0 | 3.0 | 8 | 10126 | 247 |
| C | 30 | 10373 | 3264 | 2559 | 4550 | 1.6063819531475947 | 1.0 | 4.0 | 5.0 | 12 | 9802 | 571 |

For B, ±1 day gives zero/unique/multiple =
**9928/531/18**
out of **10477** complaints; ±30 days gives
**3205/2687/4585**
out of the same stated cohort. Full-window and boundary-censored denominators are explicit.
These are candidate-search outcomes, **not recall, accuracy or proof that a transaction was disputed**.
Restricting B to the **prior 30 days** gives no/unique/multiple =
**5253/3015/2209**
out of **10477** complaints. This removes future candidates, not uncertainty.

### Amount and currency

Exact comparison uses DECIMAL(24,6), validated against source precision; no binary-float equality.
Currency must be equal. Absolute tolerance is at most 1 unit **of that currency**.
Relative tolerances are abs(transaction amount - claim amount)/abs(claim amount) <=1% or <=5%;
zero claim amounts are ineligible for relative rules. No FX conversion, no silent preferred tolerance.
Missing clues remain in the ineligible count; they are not counted as failed matches.
All monetary rule tables are stratified by currency.

| currency | rule | eligible_complaints | ineligible_complaints | no_candidate | unique_candidate | multiple_candidates | candidate_rate_pct | ambiguity_pct_eligible |
|---|---|---|---|---|---|---|---|---|
| ARS | absolute_1 | 956 | 50 | 956 | 0 | 0 | 0.0 | 0.0 |
| ARS | exact | 956 | 50 | 956 | 0 | 0 | 0.0 | 0.0 |
| ARS | relative_1pct | 956 | 50 | 956 | 0 | 0 | 0.0 | 0.0 |
| ARS | relative_5pct | 956 | 50 | 956 | 0 | 0 | 0.0 | 0.0 |
| COP | absolute_1 | 977 | 35 | 977 | 0 | 0 | 0.0 | 0.0 |
| COP | exact | 977 | 35 | 977 | 0 | 0 | 0.0 | 0.0 |
| COP | relative_1pct | 977 | 35 | 977 | 0 | 0 | 0.0 | 0.0 |
| COP | relative_5pct | 977 | 35 | 977 | 0 | 0 | 0.0 | 0.0 |
| MXN | absolute_1 | 989 | 45 | 989 | 0 | 0 | 0.0 | 0.0 |
| MXN | exact | 989 | 45 | 989 | 0 | 0 | 0.0 | 0.0 |
| MXN | relative_1pct | 989 | 45 | 989 | 0 | 0 | 0.0 | 0.0 |
| MXN | relative_5pct | 989 | 45 | 989 | 0 | 0 | 0.0 | 0.0 |
| USD | absolute_1 | 985 | 39 | 984 | 1 | 0 | 0.10152284263959391 | 0.0 |
| USD | exact | 985 | 39 | 985 | 0 | 0 | 0.0 | 0.0 |
| USD | relative_1pct | 985 | 39 | 982 | 3 | 0 | 0.30456852791878175 | 0.0 |
| USD | relative_5pct | 985 | 39 | 963 | 21 | 1 | 2.233502538071066 | 0.10152284263959391 |
| NULL | absolute_1 | 0 | 6401 | 0 | 0 | 0 | NULL | NULL |
| NULL | exact | 0 | 6401 | 0 | 0 | 0 | NULL | NULL |
| NULL | relative_1pct | 0 | 6401 | 0 | 0 | 0 | NULL | NULL |
| NULL | relative_5pct | 0 | 6401 | 0 | 0 | 0 | NULL | NULL |

B has 0 unique exact candidates and 21 unique <=5% candidates within ±30d,
among 3907 complaints eligible by both amount and currency.
These counts are across distinct currency strata, not pooled monetary distributions.
candidate_rules_common_eligibility.csv holds populations constant across rule comparisons.
candidate_rule_comparison.csv additionally compares before-or-at-complaint rules.
No arbitrary weighted rank or threshold is selected. Status is presented as evidence, not filtered
without a policy basis.

| cohort | currency | complaints | observed_claim_amounts | claim_minimum | claim_median | claim_maximum | transaction_records_same_currency | transaction_minimum | transaction_median | transaction_maximum | support |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B | ARS | 1006 | 956 | 62.530000 | 2502.505000 | 4985.840000 | 792338 | 1750.050000 | 163279.490000 | 3499939.110000 | overlapping_ranges_not_proof_of_linkage |
| B | COP | 1012 | 977 | 55.800000 | 2397.960000 | 4998.130000 | 1194084 | 20006.900000 | 1867144.000000 | 39999828.480000 | disjoint_observed_amount_ranges |
| B | MXN | 1034 | 989 | 55.060000 | 2678.790000 | 4999.900000 | 0 | NULL | NULL | NULL | no_transaction_currency |
| B | USD | 1024 | 985 | 76.190000 | 2552.700000 | 4987.340000 | 2437234 | 5.000000 | 467.070000 | 9999.980000 | overlapping_ranges_not_proof_of_linkage |
| B | NULL | 6401 | 183 | 82.700000 | 2731.380000 | 4961.640000 | 0 | NULL | NULL | NULL | missing_claim_currency |

**Observed currency/amount incompatibility limits narrowing:** MXN has no transactions in this
extract; COP claimed amounts and transaction amounts have disjoint observed ranges. ARS/USD
range overlap is not linkage evidence. These source discrepancies are preserved, not rescaled
or repaired. The almost empty exact-result sets are a limitation, not successful disambiguation.

### Direction and admissibility

temporal_candidate_distribution.csv separates calendar-day direction from elapsed-time bins:
[0,24h], (24,72h], (72,168h], (168,336h], (336,720h] before; exact equality separately;
after-complaint candidates are retrospective sensitivity only. Adjacent bins have no gaps.
An operational search at intake must reject future candidates even if their amount matches.
The data has no linked triggering event, so it cannot validate a causal or optimal retrieval horizon.
The union population has 17897 pairs before/at intake versus
17801 after, out of 35698 pairs:
roughly symmetric proximity does not establish the triggering transaction.

## 4. Evidence available per case

Pair-grain artifact: 35698 candidate pairs,
15131 complaints with a candidate and
35583 distinct candidate transactions.
17801 pairs are after intake and are **not intake-admissible**.
case_register.parquet separately retains zero-candidate complaints; case IDs are derived analytical IDs.

- **Core observed evidence:** transaction ID, customer/product ownership backbone, timestamp,
  amount+currency, type, channel and literal recorded status.
- **Optional/sparse:** merchant, response code, coordinates, historical context, nearby service and
  identified digital activity. Missing optional evidence is not itself suspicious.
- **Recorded-only, quarantined semantics:** is_fraud and fraud_score availability. They are not
  approved risk predictors, probability, legal fraud verdict or action authorization.
- **Unsafe:** complaint/product ownership, complaint/origin contact, true complaint/transaction link;
  anonymous digital identity; assigning a service contact to a transaction from proximity.

| time_window | candidate_transactions | fully_observed_window_transactions | transactions_with_interaction | transaction_coverage_pct | transaction_interaction_pairs | distinct_interactions | escalation_valid_pair_labels | escalated_pairs | escalation_pct_pairs | resolution_valid_pair_labels | resolved_pairs | resolution_pct_pairs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0_24h | 35583 | 35557 | 166 | 0.4665149088047663 | 166 | 163 | 166 | 20 | 12.048192771084338 | 166 | 126 | 75.90361445783132 |
| 1_3d | 35583 | 35521 | 313 | 0.8796335328668184 | 313 | 301 | 313 | 22 | 7.0287539936102235 | 313 | 234 | 74.76038338658147 |
| 3_7d | 35583 | 35453 | 578 | 1.6243711884888852 | 582 | 540 | 582 | 34 | 5.841924398625429 | 582 | 433 | 74.39862542955326 |
| 7_14d | 35583 | 35308 | 993 | 2.790658460500801 | 1017 | 879 | 1017 | 103 | 10.127826941986234 | 1017 | 779 | 76.59783677482793 |

Service windows are disjoint [0,24h], (24,72h], (72,168h], (168,336h].
Rates of resolution/escalation use valid labels on transaction-interaction pairs (same interaction
may appear for multiple transactions). Distinct interaction counts are separately reported.
Coverage denominators include all candidate transactions; some boundary windows are partially
observed, so absence of an event in those windows is not proof of a complete negative history.
These outcomes are current recorded flags, not proven available at contact start.

| relevant_unique_interactions | interactions_with_transcript | transcript_available_rate_pct |
|---|---|---|
| 1624 | 410 | 25.246305418719214 |

| field | schema_status | relevant_interactions | relevant_transcripts | nonnull_transcripts | nonempty_transcripts | nonempty_pct_transcripts | nonempty_pct_interactions |
|---|---|---|---|---|---|---|---|
| detected_keywords | present_in_raw_not_in_original_curated_projection | 1624 | 410 | 392 | 392 | 95.60975609756098 | 24.137931034482758 |
| mentioned_entities | present_in_raw_not_in_original_curated_projection | 1624 | 410 | 358 | 358 | 87.3170731707317 | 22.04433497536946 |
| detected_intents | present_in_raw_not_in_original_curated_projection | 1624 | 410 | 386 | 386 | 94.14634146341463 | 23.76847290640394 |
| main_topics | present_in_raw_not_in_original_curated_projection | 1624 | 410 | 410 | 410 | 100.0 | 25.246305418719214 |

Metadata fields exist in raw, not in the original curated projection. Only nonnull/nonempty
indicators were recovered; no raw text or entity values are exposed. Empty lists/objects are not
counted as populated metadata. Existing metadata may itself be generated output, not verified NLP truth.
transcript_selection_comparison.csv compares available/unavailable groups by channel/type/reason;
partial coverage and temporal/customer selection prevent assuming representativeness.

| time_window | candidate_transactions | fully_observed_window_transactions | transactions_with_digital_context | transaction_coverage_pct | transaction_event_pairs | distinct_identified_events | pairs_with_recorded_product_id | product_id_pct_pairs |
|---|---|---|---|---|---|---|---|---|
| before_30m | 35583 | 35582 | 11 | 0.0309136385352556 | 70 | 70 | 3 | 4.285714285714286 |
| before_2h | 35583 | 35578 | 36 | 0.10117190793356379 | 275 | 275 | 27 | 9.818181818181818 |
| before_24h | 35583 | 35570 | 338 | 0.9498918022651266 | 2665 | 2630 | 240 | 9.00562851782364 |
| after_24h | 35583 | 35562 | 304 | 0.8543405558834275 | 2494 | 2431 | 226 | 9.061748195669606 |

Digital before windows are nested and must not be summed; after excludes neither zero timestamp nor
future elapsed time but is explicitly retrospective. Only identified events are used. Product ID
coverage is conditional evidence, not a transaction link. event_value units are undocumented.
**Exclude digital context from the core MVP**, retaining it as optional research context.

Bundles aggregate each domain independently, avoiding service×digital event multiplication.
Intake-time event counts require event_time <= complaint creation; retrospective counts are named
separately. Transcript existence in the extract does not establish transcript availability at intake.
Recorded status/fraud availability times are unknown and flagged explicitly.

## 5. Point-in-time safe behavioral context

| feature | candidate_transactions | computable_count | computable_pct | complete_history_window_count | computable_complete_window_count | recommendation |
|---|---|---|---|---|---|---|
| customer_transaction_count_prior_7d | 35583 | 35583 | 100.0 | 35438 | 35438 | recommended |
| customer_transaction_count_prior_30d | 35583 | 35583 | 100.0 | 34844 | 34844 | recommended |
| customer_transaction_count_prior_90d | 35583 | 35583 | 100.0 | 32885 | 32885 | recommended |
| median_amount_prior_30d | 35583 | 21876 | 61.47879605429559 | 34844 | 21578 | recommended |
| median_amount_prior_90d | 35583 | 31621 | 88.86546946575612 | 32885 | 29741 | recommended |
| same_channel_count_prior_90d | 35583 | 35583 | 100.0 | 32885 | 32885 | recommended |
| same_transaction_type_count_prior_90d | 35583 | 35583 | 100.0 | 32885 | 32885 | recommended |
| same_merchant_count_prior_90d | 35583 | 8375 | 23.53652024843324 | 32885 | 7759 | optional |
| prior_declined_count_30d | 35583 | 35583 | 100.0 | 34844 | 34844 | optional |
| prior_reversed_count_30d | 35583 | 35583 | 100.0 | 34844 | 34844 | optional |

Historical events must satisfy history.timestamp < candidate.timestamp, including exclusion of
same-timestamp events. Lookbacks are 7/30/90 elapsed days. Amount medians compare **only the candidate's
currency**. Merchant counts require an observed merchant; missing merchant yields NULL, not zero.
Counts of zero are exact observed absence within the extract, not imputation.
Early history windows are left-censored and must not be interpreted as full lifetime history.

These features are **event-time safe by construction, not certified availability-time safe**:
process_date has ambiguous semantics and no ingestion/revision timestamp is supplied.
Past transaction status may be revised later; prior_declined/reversed counts remain optional
descriptive evidence until status history is available. Production/model use requires event availability
and revisions to be versioned. No later complaint resolution fields are used as contemporaneous inputs.

## 6. ML feasibility

Recorded positive class: **4315/4423656 (0.097544%)** within this stage's cutoff.
Extreme imbalance must be preserved in evaluation. No classifier, predictive threshold or learned
ranker was trained.

| dimension | minimum_rate_pct | maximum_rate_pct |
|---|---|---|
| transaction_type | 0.08893808815471879 | 0.10902813531603016 |
| channel | 0.09478446387658765 | 0.10795630411970315 |
| transaction_category | 0.09337211670361846 | 0.1068573540963911 |
| transaction_status | 0.08048109811987213 | 0.09792480505346056 |
| merchant_category | 0.09558224706060207 | 0.10789269051321929 |
| transaction_country | 0.09285389590744708 | 0.1234445980643887 |

These group-rate ranges are descriptive, not significance tests; denominators are in
fraud_signal_without_score.csv. Monetary distributions by recorded label remain separated by
currency in fraud_amount_without_score_by_currency.csv. Prior-feature comparisons also show
class counts and history-window completeness in fraud_prior_behavior_without_score.csv.
Candidate-transaction selection is not a representative training population.

**A learned component is not yet justified as an MVP dependency.** Descriptive associations do not
establish incremental/generalizable signal. is_fraud is only a possible future label after provenance,
label-availability and synthetic-construction review. fraud_score is excluded from this feasibility
analysis and from proposed predictors; current transaction status also requires availability review.
Observed categorical rates are narrow and monetary distributions overlap substantially; no clear
non-score separation is demonstrated here. Only 32 recorded positives occur among
35583 unique candidates, leaving little support for interpreting
conditional prior-feature differences. This is descriptive evidence of limited support, not a
statistical proof that no learned signal exists.
The baseline should first be deterministic lookup, transparent retrieval sets, explicit abstention
and handoff. Any later ML baseline must be compared against class prevalence/no-skill behavior on
customer/time-separated held-out data with adequate positive support and no post-event fields.
No linkage labels exist to train/evaluate true transaction matching now.

## 7. AI/LLM feasibility

Potential LLM value is limited to future extraction of user-provided clues, grounded summarization,
explicit unknowns and a draft human handoff. Structured output must be schema-validated and
traceable to evidence IDs; extracted amounts/currencies/IDs require customer confirmation.
Transcripts are partial optional context and require separate privacy/quality evaluation.
No LLM or NLP model ran in this task.

An LLM must never be sole authority for authentication, authorization, ownership, policy eligibility,
financial action or closure. It must not invent code meanings, select a true transaction from an
ambiguous set, infer policy or turn a fraud flag into a verdict. These are future design boundaries,
not demonstrated model capabilities.

## 8. Human escalation boundary

Escalate unresolved no-candidate and multiple-candidate cases, ownership/evidence conflicts,
insufficient required evidence, missing policy, any high-risk financial action and all unsupported
adjudication. Missing optional merchant/geo alone does not mandate a fraud conclusion.
Auth failure blocks data access, rather than granting a human/LLM a bypass.
Even a unique exact candidate requires attributed customer/authorized-human confirmation.

| cohort | archetype | population_size | cohort_complaints | pct_cohort | representative_evidence_pattern | recommended_handling |
|---|---|---|---|---|---|---|
| A | unique_prior_temporal_candidate | 3301 | 11571 | 28.528217094460288 | One same-customer transaction in prior 30d; amount may be absent or inconsistent with heuristic | Customer/authorized-human confirmation; preserve uncertainty |
| B | unique_prior_temporal_candidate | 3015 | 10477 | 28.777321752410042 | One same-customer transaction in prior 30d; amount may be absent or inconsistent with heuristic | Customer/authorized-human confirmation; preserve uncertainty |
| C | unique_prior_temporal_candidate | 2992 | 10373 | 28.8441145281018 | One same-customer transaction in prior 30d; amount may be absent or inconsistent with heuristic | Customer/authorized-human confirmation; preserve uncertainty |
| A | no_candidate_under_monetary_tolerance | 2126 | 11571 | 18.373520006913836 | Prior candidates exist but none meet exploratory same-currency <=5% rule | Clarify amount/currency or human review; never automatic rejection |
| B | no_candidate_under_monetary_tolerance | 1932 | 10477 | 18.440393242340363 | Prior candidates exist but none meet exploratory same-currency <=5% rule | Clarify amount/currency or human review; never automatic rejection |
| C | no_candidate_under_monetary_tolerance | 1878 | 10373 | 18.104694880940905 | Prior candidates exist but none meet exploratory same-currency <=5% rule | Clarify amount/currency or human review; never automatic rejection |
| A | multiple_prior_candidates | 2460 | 11571 | 21.260046668395127 | Multiple same-customer prior transactions in 30d | Clarify intake or human investigation |
| B | multiple_prior_candidates | 2209 | 10477 | 21.084279851102416 | Multiple same-customer prior transactions in 30d | Clarify intake or human investigation |
| C | multiple_prior_candidates | 2104 | 10373 | 20.283428130723994 | Multiple same-customer prior transactions in 30d | Clarify intake or human investigation |
| A | no_prior_candidate | 5810 | 11571 | 50.211736237144585 | No same-customer transaction in prior 30d | Clarify; human if unresolved |
| B | no_prior_candidate | 5253 | 10477 | 50.138398396487545 | No same-customer transaction in prior 30d | Clarify; human if unresolved |
| C | no_prior_candidate | 5277 | 10373 | 50.872457341174204 | No same-customer transaction in prior 30d | Clarify; human if unresolved |
| A | claimed_amount_missing | 7071 | 11571 | 61.1096707285455 | Missing claim amount | Intake incomplete path |
| B | claimed_amount_missing | 6387 | 10477 | 60.96210747351341 | Missing claim amount | Intake incomplete path |
| C | claimed_amount_missing | 6340 | 10373 | 61.12021594524246 | Missing claim amount | Intake incomplete path |
| A | sparse_optional_evidence | 1276 | 11571 | 11.027568922305765 | At least one prior candidate without merchant/score/nearby pre-intake service | Human review if required evidence absent |
| B | sparse_optional_evidence | 1149 | 10477 | 10.966879832012982 | At least one prior candidate without merchant/score/nearby pre-intake service | Human review if required evidence absent |
| C | sparse_optional_evidence | 1073 | 10373 | 10.34416273016485 | At least one prior candidate without merchant/score/nearby pre-intake service | Human review if required evidence absent |
| A | recorded_fraud_flag_present | 9 | 11571 | 0.077780658542909 | Recorded True on a prior candidate | Human risk review, no automatic verdict |
| B | recorded_fraud_flag_present | 8 | 10477 | 0.0763577359931278 | Recorded True on a prior candidate | Human risk review, no automatic verdict |
| C | recorded_fraud_flag_present | 10 | 10373 | 0.09640412609659693 | Recorded True on a prior candidate | Human risk review, no automatic verdict |
| A | service_after_transaction_before_intake | 340 | 11571 | 2.938380433843229 | Same-customer contact temporally after candidate and by intake | Label temporal association in handoff |
| B | service_after_transaction_before_intake | 311 | 10477 | 2.9684069867328433 | Same-customer contact temporally after candidate and by intake | Label temporal association in handoff |
| C | service_after_transaction_before_intake | 294 | 10373 | 2.8342813072399498 | Same-customer contact temporally after candidate and by intake | Label temporal association in handoff |

Archetypes overlap and are reported only when observed. No individual customers were selected.
“Unique candidate” is deliberately not called “high-confidence true match.”

## 9. Proposed case state machine

FUTURE DESIGN ONLY. Main path:

CASE_CREATED → AUTH_REQUIRED → INTAKE_INCOMPLETE → TRANSACTION_SEARCH
→ [NO_CANDIDATE / MULTIPLE_CANDIDATES / explicitly confirmed TRANSACTION_SELECTED]
→ OWNERSHIP_VERIFIED → EVIDENCE_COLLECTION → ASSESSMENT_READY
→ POLICY_REVIEW_REQUIRED → HUMAN_REVIEW → HANDOFF_RECORDED.

Auth failure denies access. Missing core evidence goes through INSUFFICIENT_EVIDENCE.
RESOLVED/CLOSED require external authorized outcome, authoritative policy and audited deterministic
guards; the present dataset cannot supply that authority. HANDOFF_RECORDED is the MVP observable
outcome, **not a fabricated dispute resolution**.

| source_state | target_state | trigger | required_evidence | deterministic_guard | AI_allowed | human_required | failure_state |
|---|---|---|---|---|---|---|---|
| CASE_CREATED | AUTH_REQUIRED | Intake received | request_id; untrusted claimed identity | Generate case/request ID and persist untrusted intake; no account evidence exposed | False | False | AUTH_REQUIRED |
| AUTH_REQUIRED | INTAKE_INCOMPLETE | External identity verification succeeds | signed current principal; authorization scope | Verify issuer, expiry, scope and subject via external auth; never trust LLM identity | False | False | AUTH_FAILED |
| AUTH_REQUIRED | AUTH_FAILED | Identity verification fails | auth failure record | Deny account reads; audit failure without leaking customer data | False | False | AUTH_FAILED |
| AUTH_FAILED | AUTH_REQUIRED | Authorized retry | new valid auth attempt | Rate limits and external retry policy; no bypass through human narrative | False | True | AUTH_FAILED |
| INTAKE_INCOMPLETE | TRANSACTION_SEARCH | Minimum clues supplied | authenticated customer plus transaction_id OR explicit search date/window | Validate types/units; preserve missing amount/currency; confirm extracted clues with user | True | True | INTAKE_INCOMPLETE |
| TRANSACTION_SEARCH | NO_CANDIDATE | Empty eligible retrieval | versioned query and count=0 | Only same authorized customer and nonfuture admissible transactions; expose empty result | False | False | INSUFFICIENT_EVIDENCE |
| TRANSACTION_SEARCH | MULTIPLE_CANDIDATES | More than one eligible candidate | candidate IDs and deterministic rule trace | Retain alternatives; no weighted score promoted to truth | False | False | INSUFFICIENT_EVIDENCE |
| TRANSACTION_SEARCH | TRANSACTION_SELECTED | One candidate explicitly confirmed | candidate evidence + recorded customer/human confirmation | Count=1 is insufficient alone; require attributed selection and authorization | False | True | HUMAN_REVIEW |
| MULTIPLE_CANDIDATES | TRANSACTION_SELECTED | Explicit disambiguation | recorded selection by customer/authorized human | Selected ID must belong to admissible retrieved/explicit-ID result and current owner | False | True | HUMAN_REVIEW |
| MULTIPLE_CANDIDATES | HUMAN_REVIEW | Ambiguity remains | alternatives; missing clues; retrieval trace | Do not infer a true match | True | True | HUMAN_REVIEW |
| NO_CANDIDATE | INTAKE_INCOMPLETE | Customer can clarify clues | new date/amount/currency/ID, with provenance | Never manufacture amount or expand to other customers | True | True | HUMAN_REVIEW |
| NO_CANDIDATE | HUMAN_REVIEW | No further safe clarification | empty-result evidence and limits | No automated denial or reimbursement from missing candidates | True | True | HUMAN_REVIEW |
| TRANSACTION_SELECTED | OWNERSHIP_VERIFIED | Ownership check succeeds | authenticated principal; transaction/product/customer records | Exact subject equality plus validated structural relationship and current access policy | False | False | HUMAN_REVIEW |
| TRANSACTION_SELECTED | HUMAN_REVIEW | Conflicting ownership/evidence | access-safe conflict record | Block selection and financial action; do not repair complaint affected_product_id | False | True | HUMAN_REVIEW |
| OWNERSHIP_VERIFIED | EVIDENCE_COLLECTION | Authorized evidence reads | transaction ID; sources; as-of time | Read allowlisted fields; mark snapshot timing and inferred service/digital links | False | False | INSUFFICIENT_EVIDENCE |
| EVIDENCE_COLLECTION | INSUFFICIENT_EVIDENCE | Required evidence missing | explicit missingness + source errors | Distinguish optional sparsity from required ownership/core evidence absence | False | False | HUMAN_REVIEW |
| EVIDENCE_COLLECTION | ASSESSMENT_READY | Required bundle complete | core facts, optional evidence flags, provenance | Schema/ownership/as-of checks; no post-intake outcomes used as intake facts | False | False | INSUFFICIENT_EVIDENCE |
| INSUFFICIENT_EVIDENCE | HUMAN_REVIEW | Evidence cannot safely be completed | unknowns and conflicts | No fabricated evidence or default fraud verdict | True | True | HUMAN_REVIEW |
| ASSESSMENT_READY | POLICY_REVIEW_REQUIRED | Summary prepared | grounded summary + structured bundle | Validate references and factual consistency; LLM may draft but cannot authorize eligibility | True | False | HUMAN_REVIEW |
| POLICY_REVIEW_REQUIRED | HUMAN_REVIEW | Policy missing, ambiguous or financial decision needed | policy version OR explicit missing-policy flag | Missing policy blocks autonomous decision; all current dataset cases require escalation | False | True | HUMAN_REVIEW |
| HUMAN_REVIEW | HANDOFF_RECORDED | Authorized reviewer/queue accepts handoff | handoff_id; recipient; evidence snapshot; unresolved questions | Persist acceptance and audit receipt; this is NOT a resolved dispute | True | True | HUMAN_REVIEW |
| HANDOFF_RECORDED | HUMAN_REVIEW | Authorized reviewer resumes | assigned actor; preserved evidence; current policy | Idempotent versioned transition with current authorization | False | True | HUMAN_REVIEW |
| HUMAN_REVIEW | RESOLVED | External authorized outcome supplied | signed human outcome; authoritative policy; financial-action approval if applicable | NO dataset-only authority; require external approvals; unsupported until integrated | False | True | HUMAN_REVIEW |
| RESOLVED | CLOSED | Authorized completion recorded | outcome record; approval trail; notification receipt; no pending action | Versioned deterministic closure checks; no LLM-only closure or inferred resolution | False | True | HUMAN_REVIEW |

The JSON specification also defines future audit fields: actor, transition/state version, evidence
references/hashes, event/recorded time, rule/policy/model versions, guard results, human approval and
idempotency key. Dataset complaints.status does not constitute such a transition log.

## 10. Recommended MVP

| option | scope | data_feasibility | engineering_complexity | evaluation_feasibility | risk | hackathon_value | main_blocker | recommendation | classification |
|---|---|---|---|---|---|---|---|---|---|
| A | Transaction inquiry only | HIGH | LOW | HIGH for lookup/ownership invariants | LOW with external auth | MEDIUM | Does not demonstrate stateful dispute handling | Fallback | FUTURE DESIGN |
| B | Transaction investigation + structured evidence summary | HIGH with optional gaps | MEDIUM | HIGH for evidence fidelity; LLM fidelity needs held-out review | MEDIUM | HIGH | No verified dispute verdict or policy; optional context weak | Investigation subworkflow | FUTURE DESIGN |
| C | Dispute intake + candidate retrieval + human handoff | MEDIUM with explicit ambiguity | MEDIUM | HIGH for guards/provenance; unknown linkage prevents true-match accuracy | CONTROLLED with mandatory human boundary | HIGH | No reliable complaint-transaction labels; needs future auth/policy/queue integration | RECOMMENDED, with B when a transaction is explicitly confirmed | FUTURE DESIGN |
| D | Autonomous dispute adjudication | UNSUPPORTED | HIGH | UNSUPPORTED for correctness | UNACCEPTABLE on present evidence | Misleading without policy/ground truth | No verified outcome linkage, policy, auth or financial-action authority | NO-GO | FUTURE DESIGN |

Recommend **Option C**, incorporating Option B only once a transaction has been explicitly selected:

- **Entry point:** authenticated request with transaction ID or customer-confirmed transaction clues;
  B is the primary recorded complaint analogue; A sensitivity and C fees remain separate.
- **Stages:** persisted intake → explicit missing clues → deterministic candidate search →
  confirmation/ownership checks → independently aggregated evidence → optional grounded narrative →
  policy-required human review → auditable handoff receipt.
- **Future tools:** exact transaction lookup, bounded customer/time/currency retrieval, ownership
  check, prior-event context queries, evidence retrieval, case-state/audit store, external IAM,
  authoritative policy interface and human queue. None is implemented here as an agent/API.
- **Deterministic gates:** authentication/authorization, ownership, explicit selection, no future
  evidence, currency/units, schema/provenance validation, version/idempotency checks, missing policy
  blocks action, human approval required for adjudication and closure.
- **Possible ML:** optional later research only; no required fraud/ranking component in the MVP.
- **LLM responsibility:** optional clue extraction and evidence-grounded summary with unknowns;
  never state/financial authority.
- **Human handoff:** unresolved candidate ambiguity, no candidate, conflict, missing required
  evidence/policy or a dispute decision. The dataset cannot safely bypass this boundary.
- **Final observable outcome:** accepted, versioned handoff with evidence IDs, candidate alternatives,
  unknowns and guard results; not automatic reimbursement or claimed correct dispute resolution.

Future evaluation should hold out requests and assess evidence fidelity, ownership/access denial,
temporal/currency invariants, correct handling of empty/ambiguous candidate sets, transition guards,
audit completeness and handoff acceptance. True-match accuracy, retrieval recall and adjudication
correctness need independent verified annotations/policy not supplied here. Human-reviewed or explicitly
labeled synthetic scenarios may test system behavior later, but must not be represented as observed
complaint-to-transaction truth. No demo customers, agents, UI, policy engine or models were built.

### Reproducibility and artifacts

Execute notebooks/03_dispute_case_workflow_discovery.ipynb from top to bottom, or run
python scripts/run_dispute_workflow.py from the repository's Python 3.12+ environment.
All analysis outputs are in [artifacts/dispute_case_workflow](../artifacts/dispute_case_workflow/README.md).
analysis_context.json records cutoff, source signatures and prior artifacts; integrity.json verifies
source/cache/prior-result preservation; validation_checks.json records count and temporal invariants.
No raw data or previous EDA conclusions were changed.
