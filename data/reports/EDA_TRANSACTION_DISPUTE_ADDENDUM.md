# Transaction Investigation & Dispute — EDA Addendum

## Scope, provenance and denominators

Executed: 2026-10-01T23:44:03.623637-05:00. Primary population: **full observed extract**, not a training cohort.
Inherited feature cutoff: **2026-06-17 inclusive**, from the completed general EDA.
This addendum does not rebuild customer features. Labels and current case status have no documented
availability timestamp: event date before cutoff does **not** make them point-in-time safe.
See [cutoff audit](../artifacts/eda_transaction_dispute/population_cutoff_audit.csv) and
[outcome cutoff audit](../artifacts/eda_transaction_dispute/complaint_outcome_cutoff_audit.csv).
The execution date is not the observation horizon. General EDA observed event dates 2023-06-17 through
2026-06-18, surveys through June 19; process partitions end June 17. Later outcome dates are not
new observation of customer activity. last_updated is not used as a cutoff.

Read-only reuse of existing DuckDB projections; only complaint_id/resolution is additionally read
from raw because the general EDA cache excluded free text. Fallback ingests only the three relevant
domains if the cache is absent. No sampling, no giant pandas frames, no data correction or matching.
The [context](../artifacts/eda_transaction_dispute/analysis_context.json) records hashes and source mode;
[integrity](../artifacts/eda_transaction_dispute/integrity.json) records post-execution checks.

Coverage denominator = all rows of the indicated table/group, including nulls.
Fraud rate = recorded True / valid boolean labels; CSV fraud_rate is a **fraction**, *_pct a percentage.
Numeric quantiles exclude null/unparseable/nonfinite values, whose counts remain explicit.
CSV empty cells mean NULL (not zero); response codes remain strings, including leading zeros.
Basic valid_count tests type/range/nonblank presence, not business truth. No imputation.

## 1. Observed fraud label

**4316 / 4425008 transactions (0.097537%)** carry True.
Valid labels: 4425008; null: 0;
invalid: 0; False: 4420692.
The rare positive class requires future held-out design and provenance review, not model training now.

| dimension | lowest_group | lowest_rate_pct | lowest_records | highest_group | highest_rate_pct | highest_records |
|---|---|---|---|---|---|---|
| transaction_status | Reversed | 0.08045 | 44750 | Approved | 0.09792 | 4070681 |
| transaction_type | Transfer | 0.08902 | 896438 | Adjustment | 0.10899 | 132118 |
| transaction_category | Transport | 0.09335 | 260316 | Health | 0.10683 | 173173 |
| channel | POS | 0.09476 | 1548161 | Branch | 0.10793 | 132495 |
| transaction_country | Colombia | 0.0929 | 1289503 | Mexico | 0.12341 | 40515 |
| currency | COP | 0.09335 | 1194444 | ARS | 0.0993 | 792585 |
| merchant_category | Services | 0.09555 | 205124 | Health | 0.10787 | 102903 |

These min/max rates summarize the requested seven segmentations; exact class counts and group
denominators are in fraud_by_*.csv. Differences are associations, not causal effects; small groups
may have unstable rates. No significance or predictive performance is claimed.

## 2. fraud_score versus recorded label

| label_state | records | valid_score_count | null_pct | mean | median | p75 | p90 | p95 | p99 | minimum | maximum |
|---|---|---|---|---|---|---|---|---|---|---|---|
| False | 4420692 | 3536426 | 20.002886425926075 | 14.997817706350737 | 15.0 | 22.5 | 27.0 | 28.5 | 29.7 | 0.0 | 30.0 |
| True | 4316 | 3425 | 20.644114921223355 | 49.46448467153282 | 48.93 | 74.91 | 89.94 | 95.22599999999998 | 99.18759999999999 | 0.01 | 99.99 |

| score_bucket | transaction_count | valid_labels | fraud_count | nonfraud_count | fraud_rate |
|---|---|---|---|---|---|
| 01 [0,10) | 1179452 | 1179452 | 337 | 1179115 | 0.00028572591339028633 |
| 02 [10,20) | 1179243 | 1179243 | 359 | 1178884 | 0.00030443258938149303 |
| 03 [20,30) | 1178174 | 1178174 | 356 | 1177818 | 0.0003021624989178169 |
| 04 [30,50) | 1312 | 1312 | 703 | 609 | 0.5358231707317073 |
| 05 [50,75) | 817 | 817 | 817 | 0 | 1.0 |
| 06 [75,100] | 853 | 853 | 853 | 0 | 1.0 |
| 07 NULL | 885157 | 885157 | 891 | 884266 | 0.0010066010888463855 |
| 08 INVALID_NONFINITE | 0 | 0 | 0 | 0 | NULL |
| 09 BELOW_0 | 0 | 0 | 0 | 0 | NULL |
| 10 ABOVE_100 | 0 | 0 | 0 | 0 | NULL |

Observed score ranges overlap: True minimum 0.01, False maximum 30.0.
The positive group also extends to 99.99. This separation in the upper tail is
**a signal and a possible label-construction/leakage concern**, not proof of predictive utility.
No calibrated probabilities, threshold optimization or score-based fraud rule is approved.
Score-by-status/channel/type exports retain counts and missingness.

## 3. Complaint taxonomy — observed, not a final cohort

| category | subcategory | records | pct_of_complaints | claimed_amount_present_count | claimed_amount_present_pct |
|---|---|---|---|---|---|
| Fees | Cobro indebido | 12194 | 18.174230568596766 | 4035 | 33.09004428407413 |
| Fees | NULL | 1359 | 2.0254862508383633 | 422 | 31.05224429727741 |
| Transactions | Cargo no reconocido | 12297 | 18.327744243237202 | 4090 | 33.26014475075222 |
| Transactions | NULL | 1283 | 1.9122140248900812 | 410 | 31.95635229929852 |

Transactions / Cargo no reconocido and Fees / Cobro indebido are descriptively relevant.
Null subcategories and all case types remain included in the tables.
There are no dedicated observed payment-, transfer- or ATM-dispute categories; generic Transactions
cannot establish those subtypes. Full two- and three-way tables include the other real categories:
Branch, Service and Technical. Annotations are hypotheses about relevance, not a new taxonomy.

## 4. Claimed amount usability

Overall finite amount coverage: **32.418%**;
currency coverage: **32.455%**.
Joint finite amount + known currency: **20711/67095
(30.868%)**. All observed non-null amounts are finite;
the joint calculation removes only the explicitly counted unknown-currency cases from this metric.

| group_value | records | valid_count | null_count | coverage_pct |
|---|---|---|---|---|
| Claim | 16598 | 6351 | 10247 | 38.263646222436435 |
| Complaint | 40452 | 15400 | 25052 | 38.06981113418372 |
| Request | 6761 | 0 | 6761 | 0.0 |
| Suggestion | 3284 | 0 | 3284 | 0.0 |

| group_value | records | null_amount | invalid_amount | zero_amount | negative_amount | amount_without_currency | currency_without_amount |
|---|---|---|---|---|---|---|---|
| ALL | 67095 | 45344 | 0 | 0 | 0 | 1040 | 1065 |

| currency | records | valid_amounts | mean | median | p75 | p90 | p95 | p99 | minimum | maximum |
|---|---|---|---|---|---|---|---|---|---|---|
| ARS | 5402 | 5132 | 2529.4708067030406 | 2521.17 | 3745.425 | 4500.366000000002 | 4735.2565 | 4931.3587 | 52.31 | 4997.59 |
| COP | 5456 | 5192 | 2505.3268990755014 | 2467.195 | 3753.3475000000003 | 4513.941 | 4769.1630000000005 | 4959.6854 | 50.27 | 4999.93 |
| MXN | 5487 | 5215 | 2536.1001073825532 | 2551.21 | 3753.63 | 4510.838 | 4764.84 | 4941.4144 | 50.31 | 4999.9 |
| USD | 5431 | 5172 | 2566.227376256768 | 2563.865 | 3818.745 | 4549.457 | 4780.365 | 4957.4446 | 50.61 | 4999.46 |

No currencies are pooled or converted. Amounts with unknown currency remain in coverage/checks
but are excluded from monetary quantiles: their units cannot safely be combined.
Upper-tail counts above each currency's p99/p99.9 are
descriptive, not invalid-value tests, and all extremes are retained. See claimed_amount_upper_tail_by_currency.csv.
Case-type conditional absence should not be mislabeled as universal data corruption.
The potential_transaction_taxonomy_amount.csv export gives case/category/subcategory-specific amount
and currency coverage. A recorded amount could narrow future candidates, but cannot identify a
transaction. Joint amount-and-currency coverage is separately exported for each combination.
A recorded amount cannot identify a
transaction or justify matching by itself.

## 5. Transaction evidence retrievability

| field | records | valid_count | null_count | invalid_nonnull_count | coverage_pct |
|---|---|---|---|---|---|
| transaction_id | 4425008 | 4425008 | 0 | 0 | 100.0 |
| transaction_date | 4425008 | 4425008 | 0 | 0 | 100.0 |
| product_id | 4425008 | 4425008 | 0 | 0 | 100.0 |
| customer_id | 4425008 | 4425008 | 0 | 0 | 100.0 |
| transaction_type | 4425008 | 4425008 | 0 | 0 | 100.0 |
| transaction_category | 4425008 | 1731488 | 2693520 | 0 | 39.129601573601676 |
| amount | 4425008 | 4425008 | 0 | 0 | 100.0 |
| currency | 4425008 | 4425008 | 0 | 0 | 100.0 |
| amount_usd | 4425008 | 1887552 | 2537456 | 0 | 42.656465253848125 |
| channel | 4425008 | 4425008 | 0 | 0 | 100.0 |
| branch_id | 4425008 | 1387932 | 3037076 | 0 | 31.365638209015668 |
| merchant_name | 4425008 | 1029234 | 3395774 | 0 | 23.259483372685427 |
| merchant_category | 4425008 | 1028793 | 3396215 | 0 | 23.249517289008292 |
| transaction_country | 4425008 | 4425008 | 0 | 0 | 100.0 |
| transaction_city | 4425008 | 3982397 | 442611 | 0 | 89.99750960902217 |
| transaction_status | 4425008 | 4425008 | 0 | 0 | 100.0 |
| response_code | 4425008 | 4203975 | 221033 | 0 | 95.00491298546805 |
| is_fraud | 4425008 | 4425008 | 0 | 0 | 100.0 |
| fraud_score | 4425008 | 3539851 | 885157 | 0 | 79.99648814194234 |
| latitude | 4425008 | 857328 | 3567680 | 0 | 19.374609040254843 |
| longitude | 4425008 | 857293 | 3567715 | 0 | 19.373818081232848 |

Uniqueness is checked in transaction_identifier_check.csv. Coverage is also exported by channel,
transaction_type and transaction_status. Amount is interpreted only with its currency; amount_usd
is not silently filled from amount, including USD rows. Ownership consistency is inherited from
validated transactions → products → customers, not from coincident identifiers.

## 6. Geography viability

| records | country_count_pct | city_count_pct | latitude_present_pct | longitude_present_pct | lat_lon_pair_present_pct | lat_lon_pair_valid_pct | latitude_out_of_range | longitude_out_of_range | latitude_invalid_nonnull | longitude_invalid_nonnull |
|---|---|---|---|---|---|---|---|---|---|---|
| 4425008 | 100.0 | 89.99750960902217 | 19.374609040254843 | 19.373818081232848 | 18.404825482801385 | 18.404825482801385 | 0 | 0 | 0 | 0 |

Per-channel/type/country coverage is exported. Valid physical ranges do not establish that coordinates
agree with the recorded city or country. **Exclude geographic anomaly logic from the MVP**; show
optional raw geography only with missingness and provenance. No geocoding or location correction.

## 7. Status and response-code evidence

| response_code | code_records | observed_status_count | dominant_status | dominant_status_records | dominant_status_pct | exclusive_in_this_extract |
|---|---|---|---|---|---|---|
| 00 | 3867312 | 1 | Approved | 3867312 | 100.0 | True |
| NULL | 221033 | 4 | Approved | 203369 | 92.00843312989463 | False |
| 14 | 84472 | 3 | Declined | 52711 | 62.40055876503457 | False |
| 51 | 84179 | 3 | Declined | 52788 | 62.70922676677081 | False |
| 05 | 84141 | 3 | Declined | 52246 | 62.09339085582534 | False |
| 54 | 83871 | 3 | Declined | 52527 | 62.62832206602997 | False |

Observed code exclusivity is limited to this extract. Codes are not translated into undocumented
decline causes. Status-by-code/type/channel tables provide both P(dimension|status) and
P(status|dimension); missing codes are a separate group. Status-by-fraud and score-by-status
reuse sections 1–2. Approved does not itself prove settlement, and Reversed does not establish
that a complaint was upheld.

## 8. Complaint outcome observability

| field | records | valid_count | null_count | coverage_pct |
|---|---|---|---|---|
| status | 67095 | 67095 | 0 | 100.0 |
| resolution | 67095 | 15310 | 51785 | 22.81839183247634 |
| resolution_date | 67095 | 15349 | 51746 | 22.876518369476116 |
| closing_date | 67095 | 2481 | 64614 | 3.6977420076011627 |
| compensation_granted | 67095 | 4641 | 62454 | 6.917057902973396 |
| resolution_satisfaction | 67095 | 2484 | 64611 | 3.7022132796780682 |
| sla_breached | 67095 | 67095 | 0 | 100.0 |
| resolution_days | 67095 | 15363 | 51732 | 22.89738430583501 |
| priority | 67095 | 67095 | 0 | 100.0 |

complaint_outcome_coverage.csv conditions coverage on status/case_type/category/subcategory for all complaints
and separately the exploratory Transactions-or-Fees subset (not a finalized cohort).
Resolution/closing nulls may reflect lifecycle, not a missing-data error.
resolution_satisfaction has respondent/closure selection; compensation is a post-case monetary
observation, **not fraud truth**. Resolved does not mean the customer was right.
Resolution text is measured for presence without exposing raw customer text.
Outcome dates after cutoff are reported, not included as available historical features.
No existing field establishes a verified dispute verdict linked to a specific transaction.

## 9. Potential labels — NOT YET APPROVED FOR MODELING

| label | coverage_pct | semantic_meaning | known_leakage_risks | known_linkage_limitations | potential_use | recommendation |
|---|---|---|---|---|---|---|
| transactions.is_fraud | 100.0 | Recorded boolean fraud flag; confirmation process, source and availability time undocumented | fraud_score may encode the label or shared synthetic generation; post-event flag; severe imbalance | Unique transaction; ownership validated, but no complaint-transaction link | Candidate transaction-level fraud label only after provenance, timing and held-out validation | requires_validation |
| complaints.status | 100.0 | Recorded case lifecycle state; Resolved does not mean customer was right | Snapshot can reflect future resolution relative to creation and cutoff | No transaction_id; affected product ownership is inconsistent; origin interaction absent | Possible case lifecycle endpoint after defining time horizon and censoring | requires_validation |
| complaints.compensation_granted | 6.917057902973396 | Recorded numeric compensation; zero/positive is not a fraud verdict | Post-resolution action and policy selection; missingness depends on lifecycle | No verified complaint-transaction linkage; currencies cannot be pooled | Observable monetary outcome by currency; unsuitable as ground truth of fraud or dispute validity | unsuitable |
| complaints.resolution_satisfaction | 3.7022132796780682 | Recorded resolution satisfaction; scale anchors and collection timing undocumented | Observed after resolution; response/selection bias; cannot stand for all complaints | Complaint-level only; no safe transaction linkage | Possible respondent satisfaction endpoint after scale and sampling validation | requires_validation |
| call_center_interactions.was_resolved | 100.0 | Recorded interaction resolution flag, not transaction dispute adjudication | Post-contact flag; availability time and resolution criteria unknown | Customer linkage exists, but no explicit transaction linkage or complaint-origin link | Possible interaction-level service outcome after semantic validation | requires_validation |
| call_center_interactions.was_escalated | 100.0 | Recorded escalation flag; not a normative ground-truth decision to escalate | Historical human/policy selection; post-contact flag and timing unknown | Interaction-level only; cannot transfer to arbitrary customer transactions | Possible historical escalation endpoint after policy and timestamp validation | requires_validation |

Class distributions, including NULL and descriptive compensation sign bins, are in
[potential_label_distributions.csv](../artifacts/eda_transaction_dispute/potential_label_distributions.csv).
Compensation bins are not newly approved labels. None of these candidates is approved for training.
The recommendation unsuitable refers specifically to compensation as fraud/dispute-validity ground truth.
Future held-out evaluation requires provenance, outcome timing, censoring, a task definition and
customer/time-aware split design; no models or split optimization are performed here.

## 10. Decision matrix

Availability ratings: HIGH = broadly recoverable core evidence; MEDIUM = usable partial fields;
LOW = sparse/selected for the intended use; UNUSABLE = absent or invalid required linkage.
Reliability rates the narrow use described, not source truth certification. HIGH structural transaction
reliability does not authorize payments or legal conclusions; LOW label reliability reflects absent
provenance, not evidence that recorded values are false.

| evidence_source | availability | reliability | quantitative_basis | potential_agent_use | main_limitation |
|---|---|---|---|---|---|
| transaction details | HIGH | HIGH | 4425008 unique IDs; date/owner/amount/currency coverage 100.000%/100.000%/100.000%/100.000% | Deterministic lookup, owner consistency and literal amount/status evidence | Structural reliability within extract, not authorization or settlement proof; amount_usd partial |
| is_fraud | HIGH | LOW | 4425008 valid; 4316 positive | Visible recorded flag; conditional future label candidate | Undocumented provenance/availability; not confirmed fraud or decision authority |
| fraud_score | MEDIUM | LOW | 79.996% finite coverage | Supporting numeric evidence only | Label association and provenance/timing uncertainty; no operational threshold justified |
| merchant | LOW | MEDIUM | name 23.259%; category 23.250% | Display observed merchant evidence when present | Incomplete; no independent verification or merchant identity reference |
| geography | MEDIUM | LOW | country 100.000%; city 89.998%; valid coordinate pair 18.405% | Optional raw location context, not required MVP decision logic | Physical ranges do not validate real location or country-coordinate coherence |
| complaint taxonomy | HIGH | MEDIUM | 67095 cases; actual categories Transactions and Fees | Exploratory intake language and scope discovery | Coarse recorded categories; no final cohort; no transfer/ATM-specific taxonomy |
| claimed amount | LOW | MEDIUM | 32.418% overall coverage | Possible future candidate-matching evidence when amount AND currency exist | Not a verified transaction amount; no matching performed; missingness by case type |
| complaint outcome | LOW | LOW | resolution 22.818%; date 22.877%; compensation 6.917%; satisfaction 3.702% | Descriptive case outcomes; conditional future offline evaluation | Not dispute-validity ground truth; lifecycle/selection/timing and linkage limitations |
| call interactions | HIGH | MEDIUM | 686296 interactions; resolution/escalation coverage in labels CSV | Customer-level service evidence; interaction endpoints requiring semantic validation | UNUSABLE as direct transaction linkage without additional evidence |
| transcripts | LOW | MEDIUM | 171321/686296 interactions (24.963%) | Future NLP candidate with privacy controls and evidence attribution | Partial, selected coverage; transcript-interaction consistency is not a transaction link |

## Preserved general EDA findings

| validation | total | eligible | linked | orphan | inconsistent | consistent | consistent_pct |
|---|---|---|---|---|---|---|---|
| transaction_product_customer | 4425008 | 4425008 | 4425008 | 0 | 0 | 4425008 | 100.0 |
| transcript_customer | 171321 | 171321 | 171321 | 0 | 0 | 171321 | 100.0 |
| transcript_agent | 171321 | 171321 | 171321 | 0 | 0 | 171321 | 100.0 |
| survey_customer | 212759 | 212759 | 212759 | 0 | 0 | 212759 | 100.0 |
| survey_agent | 212759 | 212759 | 212759 | 0 | 0 | 212759 | 100.0 |
| complaint_product_customer | 67095 | 44570 | 44570 | 0 | 44570 | 0 | 0.0 |

All 44,570 non-null complaint affected-product references point to existing products **owned by
different customers**. No repair or owner reassignment is allowed. complaint.origin_interaction_id
is entirely null. Customer and agent branch joins remain unreliable.
Digital anonymous share: 23.977%; do not attach those events to customers.
Transcript coverage: 24.963% of all interactions and
24.960% of calls. Verified transcript → interaction identity does
not imply a transcript → transaction or complaint link.
Source: [unchanged General EDA findings](eda/EDA_FINDINGS.md).

## Hypotheses and pending validation — not findings

1. fraud_score and is_fraud may share label generation or post-event information; inspect provenance.
2. Transactions / Cargo no reconocido and Fees / Cobro indebido may support different dispute-intake
   patterns; no final cohort or transaction matching is defined.
3. Claimed amount plus currency may help candidate retrieval where present, but temporal, ownership
   and linkage constraints must be independently established.
4. Complaint outcomes and call flags might support separate service-quality endpoints, not fraud
   correctness. Any future evaluation must separate service completion from adjudication.

## Required conclusions

### 1. Does the dataset support a Transaction Investigation workflow?

**Yes, with constraints:** 4425008 individually identified transactions,
validated transaction/product/customer ownership, literal amounts/currencies/dates/statuses and
partially available merchant/score evidence support scoped lookup and evidence collection.
This establishes data feasibility, not a production system, independent truth verification or an
automatic financial decision.

### 2. Does the dataset support a Transaction Dispute workflow?

- **Dispute intake:** conditionally supported by observed case taxonomy and amount/currency fields.
  Missing fields must remain unknown; no complete intake policy is documented.
- **Transaction investigation:** supported as evidence retrieval and structural validation.
- **Dispute matching:** **not validated**. No direct complaint-transaction key and broken affected-product
  ownership; future discovery must investigate feasibility, not assume a match.
- **Dispute decision/resolution:** **not supported for autonomous adjudication or gold-label evaluation**.
  No verified linked verdict, policy basis, label provenance or point-in-time outcome availability.

### 3. Which signals are reliable enough for deterministic logic?

Within this immutable extract: unique transaction_id lookup, transaction/customer/product ownership
consistency, observed date, amount paired with currency, and literal transaction_status.
Response codes and is_fraud can be returned **as recorded evidence only**, not interpreted as causes,
confirmed fraud or permission to reimburse. Missing evidence and inconsistent ownership require
explicit unknown/error states; no silent repair. Dataset ownership is not authentication/authorization.

### 4. Which signals are appropriate as AI/ML inputs?

- **Raw evidence:** transaction fields with coverage/provenance, optional merchant/location,
  customer-level service context only where linkage is explicit.
- **Derived feature candidates:** existing cutoff-aware independent aggregates, missingness indicators,
  documented summaries; do not add post-event labels/snapshot outcomes as contemporaneous predictors.
- **Label candidates:** is_fraud and service/case outcomes require validation listed above;
  compensation is not fraud ground truth. No approved label or model is delivered.
- **LLM/NLP candidates:** limited transcripts tied to interactions and complaint text might support
  future evidence extraction with privacy/grounding controls. Neither NLP nor LLM analysis was run,
  and these texts are not linked to transactions by this addendum.

### 5. Which relationships remain unsafe to assume?

Complaint → affected product ownership; complaint → origin interaction; complaint → transaction;
anonymous digital event → customer; same-customer call/transcript → specific transaction;
customer/agent branch links; score/flag → verified fraud; compensation or Resolved → justified dispute;
response code → undocumented decline cause; event date → label availability.

### 6. Can we proceed to transaction_dispute_discovery?

**GO WITH CONSTRAINTS.** Proceed only to scoped discovery of transaction evidence retrieval and
dispute-intake feasibility, preserving known broken links and unknown semantics. Before matching,
automation or ML, require verified linkage, label provenance/timing, policy documentation and
an auditable evaluation target. Autonomous dispute decisions remain NO-GO on present evidence.
No stage-03 notebook, journeys, matching, demo customer selection, models or agent architecture
were implemented in this task.
