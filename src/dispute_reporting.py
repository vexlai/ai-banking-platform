"""Evidence-bound interpretation of the scoped EDA; no operational rules."""
import csv
import json

from src.config import ROOT
from src.dispute_eda import ART, REPORT, save, log


def read(name):
    with (ART / name).open() as f:
        return list(csv.DictReader(f))


def table(records, columns=None):
    if not records:
        return "_No records._"
    columns = columns or list(records[0])
    def cell(value):
        return str(value if value not in (None, "") else "NULL").replace("|", "/").replace("\n", " ")
    return "\n".join(["| " + " | ".join(columns) + " |",
                      "|" + "|".join("---" for _ in columns) + "|"]
                     + ["| " + " | ".join(cell(r.get(c)) for c in columns) + " |" for r in records])


def assessments():
    coverage = {r["label"]: r for r in read("potential_label_coverage.csv")}
    meanings = {
        "transactions.is_fraud": (
            "Recorded boolean fraud flag; confirmation process, source and availability time undocumented",
            "fraud_score may encode the label or shared synthetic generation; post-event flag; severe imbalance",
            "Unique transaction; ownership validated, but no complaint-transaction link",
            "Candidate transaction-level fraud label only after provenance, timing and held-out validation",
            "requires_validation"),
        "complaints.status": (
            "Recorded case lifecycle state; Resolved does not mean customer was right",
            "Snapshot can reflect future resolution relative to creation and cutoff",
            "No transaction_id; affected product ownership is inconsistent; origin interaction absent",
            "Possible case lifecycle endpoint after defining time horizon and censoring",
            "requires_validation"),
        "complaints.compensation_granted": (
            "Recorded numeric compensation; zero/positive is not a fraud verdict",
            "Post-resolution action and policy selection; missingness depends on lifecycle",
            "No verified complaint-transaction linkage; currencies cannot be pooled",
            "Observable monetary outcome by currency; unsuitable as ground truth of fraud or dispute validity",
            "unsuitable"),
        "complaints.resolution_satisfaction": (
            "Recorded resolution satisfaction; scale anchors and collection timing undocumented",
            "Observed after resolution; response/selection bias; cannot stand for all complaints",
            "Complaint-level only; no safe transaction linkage",
            "Possible respondent satisfaction endpoint after scale and sampling validation",
            "requires_validation"),
        "call_center_interactions.was_resolved": (
            "Recorded interaction resolution flag, not transaction dispute adjudication",
            "Post-contact flag; availability time and resolution criteria unknown",
            "Customer linkage exists, but no explicit transaction linkage or complaint-origin link",
            "Possible interaction-level service outcome after semantic validation",
            "requires_validation"),
        "call_center_interactions.was_escalated": (
            "Recorded escalation flag; not a normative ground-truth decision to escalate",
            "Historical human/policy selection; post-contact flag and timing unknown",
            "Interaction-level only; cannot transfer to arbitrary customer transactions",
            "Possible historical escalation endpoint after policy and timestamp validation",
            "requires_validation"),
    }
    result = []
    for label, values in meanings.items():
        r = dict(coverage[label])
        r.update(zip(["semantic_meaning","known_leakage_risks","known_linkage_limitations",
                      "potential_use","recommendation"], values))
        r["class_distribution_artifact"] = "potential_label_distributions.csv"
        result.append(r)
    save("potential_labels_assessment.csv", result)
    return result


def validate_artifacts():
    """Check conservation of counts and explicit currency segregation."""
    fraud = read("fraud_label_summary.csv")[0]
    total = int(fraud["total_transactions"])
    positives = int(fraud["fraud_transactions"])
    checks = []
    def check(name, condition):
        assert condition, name
        checks.append(dict(check=name, passed=True))
    check("label_partition", int(fraud["valid_is_fraud"]) + int(fraud["null_is_fraud"])
          + int(fraud["invalid_is_fraud"]) == total)
    check("valid_labels_partition", positives + int(fraud["nonfraud_transactions"])
          == int(fraud["valid_is_fraud"]))
    buckets = read("fraud_score_buckets.csv")
    check("score_buckets_conserve_rows", sum(int(r["transaction_count"]) for r in buckets) == total)
    check("score_buckets_conserve_positive_labels", sum(int(r["fraud_count"]) for r in buckets) == positives)
    for path in sorted(ART.glob("fraud_by_*.csv")):
        grouped = read(path.name)
        check(path.name+"_row_sum", sum(int(r["records"]) for r in grouped) == total)
        check(path.name+"_fraud_sum", sum(int(r["fraud_records"]) for r in grouped) == positives)
    keys = read("transaction_identifier_check.csv")[0]
    check("transaction_ids_unique_nonnull", int(keys["records"]) == int(keys["nonnull_ids"])
          == int(keys["distinct_ids"]))
    for filename in ("transaction_evidence_coverage.csv","complaint_claimed_amount_coverage.csv",
                     "complaint_outcome_coverage.csv"):
        for r in read(filename):
            check(filename+"_"+r["scope"]+"_"+r["dimension"]+"_"+r["group_value"]+"_"+r["field"],
                  int(r["valid_count"])+int(r["null_count"])+int(r["invalid_nonnull_count"])
                  == int(r["records"]))
    for filename in ("claimed_amount_by_currency.csv","claimed_amount_upper_tail_by_currency.csv",
                     "compensation_by_currency_status.csv"):
        check(filename+"_known_currencies_only", all(r["currency"].strip() for r in read(filename)))
    for r in read("potential_label_coverage.csv"):
        distribution = [x for x in read("potential_label_distributions.csv") if x["label"] == r["label"]]
        check(r["label"]+"_class_sum", sum(int(x["records"]) for x in distribution) == int(r["records"]))
    (ART / "validation_checks.json").write_text(json.dumps(
        {"passed":len(checks), "failed":0, "checks":checks}, indent=2)+"\n")
    log(f"Validaciones de artefactos: {len(checks)} correctas")
    return len(checks)


def build_report(context):
    label_assessment = assessments()
    fraud = read("fraud_label_summary.csv")[0]
    scores = read("fraud_score_by_label_state.csv")
    evidence = {r["field"]: r for r in read("transaction_evidence_coverage.csv")
                if r["dimension"] == "overall"}
    geo = next(r for r in read("transaction_geography_coverage.csv") if r["dimension"] == "overall")
    claim = {r["field"]: r for r in read("complaint_claimed_amount_coverage.csv")
             if r["dimension"] == "overall"}
    outcome = {r["field"]: r for r in read("complaint_outcome_coverage.csv")
               if r["scope"] == "all" and r["dimension"] == "overall"}
    ncomplaints = int(claim["claimed_amount"]["records"])
    amount_checks = read("claimed_amount_checks_overall.csv")[0]
    amount_with_currency = int(claim["claimed_amount"]["valid_count"]) - int(amount_checks["amount_without_currency"])
    def pct(value):
        return f"{float(value):.3f}%"
    def ev(field):
        return pct(evidence[field]["coverage_pct"])
    def ov(field):
        return pct(outcome[field]["coverage_pct"])
    with (ROOT / "reports/eda/transcript_coverage.csv").open() as f:
        transcripts = next(csv.DictReader(f))
    with (ROOT / "reports/eda/semantic_validation.csv").open() as f:
        semantic = list(csv.DictReader(f))
    with (ROOT / "reports/eda/digital_coverage.csv").open() as f:
        digital = next(csv.DictReader(f))
    matrix_rows = [
        ("transaction details","HIGH","HIGH",
         f"{fraud['total_transactions']} unique IDs; date/owner/amount/currency coverage "
         + "/".join(ev(c) for c in ["transaction_date","customer_id","amount","currency"]),
         "Deterministic lookup, owner consistency and literal amount/status evidence",
         "Structural reliability within extract, not authorization or settlement proof; amount_usd partial"),
        ("is_fraud","HIGH","LOW",f"{fraud['valid_is_fraud']} valid; {fraud['fraud_transactions']} positive",
         "Visible recorded flag; conditional future label candidate",
         "Undocumented provenance/availability; not confirmed fraud or decision authority"),
        ("fraud_score","MEDIUM","LOW",ev("fraud_score")+" finite coverage",
         "Supporting numeric evidence only",
         "Label association and provenance/timing uncertainty; no operational threshold justified"),
        ("merchant","LOW","MEDIUM",f"name {ev('merchant_name')}; category {ev('merchant_category')}",
         "Display observed merchant evidence when present",
         "Incomplete; no independent verification or merchant identity reference"),
        ("geography","MEDIUM","LOW",f"country {ev('transaction_country')}; city {ev('transaction_city')}; "
         f"valid coordinate pair {pct(geo['lat_lon_pair_valid_pct'])}",
         "Optional raw location context, not required MVP decision logic",
         "Physical ranges do not validate real location or country-coordinate coherence"),
        ("complaint taxonomy","HIGH","MEDIUM",f"{ncomplaints} cases; actual categories Transactions and Fees",
         "Exploratory intake language and scope discovery",
         "Coarse recorded categories; no final cohort; no transfer/ATM-specific taxonomy"),
        ("claimed amount","LOW","MEDIUM",pct(claim["claimed_amount"]["coverage_pct"])+" overall coverage",
         "Possible future candidate-matching evidence when amount AND currency exist",
         "Not a verified transaction amount; no matching performed; missingness by case type"),
        ("complaint outcome","LOW","LOW",f"resolution {ov('resolution')}; date {ov('resolution_date')}; "
         f"compensation {ov('compensation_granted')}; satisfaction {ov('resolution_satisfaction')}",
         "Descriptive case outcomes; conditional future offline evaluation",
         "Not dispute-validity ground truth; lifecycle/selection/timing and linkage limitations"),
        ("call interactions","HIGH","MEDIUM",f"{transcripts['n_interactions']} interactions; resolution/escalation coverage in labels CSV",
         "Customer-level service evidence; interaction endpoints requiring semantic validation",
         "UNUSABLE as direct transaction linkage without additional evidence"),
        ("transcripts","LOW","MEDIUM",
         f"{transcripts['n_interactions_with_transcript']}/{transcripts['n_interactions']} interactions "
         f"({pct(transcripts['interaction_coverage_pct'])})",
         "Future NLP candidate with privacy controls and evidence attribution",
         "Partial, selected coverage; transcript-interaction consistency is not a transaction link"),
    ]
    matrix = [dict(zip(["evidence_source","availability","reliability","quantitative_basis",
                        "potential_agent_use","main_limitation"], r)) for r in matrix_rows]
    save("transaction_dispute_evidence_matrix.csv", matrix)
    # Ratings express fitness for the narrow stated use, not certification of truth.
    rate = 100*float(fraud["fraud_rate"])
    segment_lines = []
    for dim in ["transaction_status","transaction_type","transaction_category","channel",
                "transaction_country","currency","merchant_category"]:
        groups = read("fraud_by_"+dim+".csv")
        valid = [r for r in groups if r["fraud_rate"]]
        low, high = min(valid,key=lambda r:float(r["fraud_rate"])),max(valid,key=lambda r:float(r["fraud_rate"]))
        segment_lines.append(dict(dimension=dim,
            lowest_group=low[dim] or "NULL",lowest_rate_pct=round(100*float(low["fraud_rate"]),5),
            lowest_records=low["records"],highest_group=high[dim] or "NULL",
            highest_rate_pct=round(100*float(high["fraud_rate"]),5),highest_records=high["records"]))
    save("fraud_segment_rate_ranges.csv", segment_lines)
    taxonomy = read("complaint_category_subcategory.csv")
    potential = [r for r in taxonomy if r["category"] in {"Transactions","Fees"}]
    cat_amount = [r for r in read("complaint_claimed_amount_coverage.csv")
                  if r["dimension"] == "case_type" and r["field"] == "claimed_amount"]
    positive = next(r for r in scores if r["label_state"] == "True")
    negative = next(r for r in scores if r["label_state"] == "False")
    report = f"""# Transaction Investigation & Dispute — EDA Addendum

## Scope, provenance and denominators

Executed: {context['execution_started']}. Primary population: **full observed extract**, not a training cohort.
Inherited feature cutoff: **{context['feature_cutoff_inclusive']} inclusive**, from the completed general EDA.
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

**{fraud['fraud_transactions']} / {fraud['total_transactions']} transactions ({rate:.6f}%)** carry True.
Valid labels: {fraud['valid_is_fraud']}; null: {fraud['null_is_fraud']};
invalid: {fraud['invalid_is_fraud']}; False: {fraud['nonfraud_transactions']}.
The rare positive class requires future held-out design and provenance review, not model training now.

{table(segment_lines)}

These min/max rates summarize the requested seven segmentations; exact class counts and group
denominators are in fraud_by_*.csv. Differences are associations, not causal effects; small groups
may have unstable rates. No significance or predictive performance is claimed.

## 2. fraud_score versus recorded label

{table(scores, ['label_state','records','valid_score_count','null_pct','mean','median','p75','p90','p95','p99','minimum','maximum'])}

{table(read('fraud_score_buckets.csv'))}

Observed score ranges overlap: True minimum {positive['minimum']}, False maximum {negative['maximum']}.
The positive group also extends to {positive['maximum']}. This separation in the upper tail is
**a signal and a possible label-construction/leakage concern**, not proof of predictive utility.
No calibrated probabilities, threshold optimization or score-based fraud rule is approved.
Score-by-status/channel/type exports retain counts and missingness.

## 3. Complaint taxonomy — observed, not a final cohort

{table(potential)}

Transactions / Cargo no reconocido and Fees / Cobro indebido are descriptively relevant.
Null subcategories and all case types remain included in the tables.
There are no dedicated observed payment-, transfer- or ATM-dispute categories; generic Transactions
cannot establish those subtypes. Full two- and three-way tables include the other real categories:
Branch, Service and Technical. Annotations are hypotheses about relevance, not a new taxonomy.

## 4. Claimed amount usability

Overall finite amount coverage: **{pct(claim['claimed_amount']['coverage_pct'])}**;
currency coverage: **{pct(claim['currency']['coverage_pct'])}**.
Joint finite amount + known currency: **{amount_with_currency}/{ncomplaints}
({100*amount_with_currency/ncomplaints:.3f}%)**. All observed non-null amounts are finite;
the joint calculation removes only the explicitly counted unknown-currency cases from this metric.

{table(cat_amount, ['group_value','records','valid_count','null_count','coverage_pct'])}

{table(read('claimed_amount_checks_overall.csv'))}

{table(read('claimed_amount_by_currency.csv'))}

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

{table(list(evidence.values()), ['field','records','valid_count','null_count','invalid_nonnull_count','coverage_pct'])}

Uniqueness is checked in transaction_identifier_check.csv. Coverage is also exported by channel,
transaction_type and transaction_status. Amount is interpreted only with its currency; amount_usd
is not silently filled from amount, including USD rows. Ownership consistency is inherited from
validated transactions → products → customers, not from coincident identifiers.

## 6. Geography viability

{table([geo], ['records','country_count_pct','city_count_pct','latitude_present_pct','longitude_present_pct','lat_lon_pair_present_pct','lat_lon_pair_valid_pct','latitude_out_of_range','longitude_out_of_range','latitude_invalid_nonnull','longitude_invalid_nonnull'])}

Per-channel/type/country coverage is exported. Valid physical ranges do not establish that coordinates
agree with the recorded city or country. **Exclude geographic anomaly logic from the MVP**; show
optional raw geography only with missingness and provenance. No geocoding or location correction.

## 7. Status and response-code evidence

{table(read('response_code_associations.csv'))}

Observed code exclusivity is limited to this extract. Codes are not translated into undocumented
decline causes. Status-by-code/type/channel tables provide both P(dimension|status) and
P(status|dimension); missing codes are a separate group. Status-by-fraud and score-by-status
reuse sections 1–2. Approved does not itself prove settlement, and Reversed does not establish
that a complaint was upheld.

## 8. Complaint outcome observability

{table(list(outcome.values()), ['field','records','valid_count','null_count','coverage_pct'])}

complaint_outcome_coverage.csv conditions coverage on status/case_type/category/subcategory for all complaints
and separately the exploratory Transactions-or-Fees subset (not a finalized cohort).
Resolution/closing nulls may reflect lifecycle, not a missing-data error.
resolution_satisfaction has respondent/closure selection; compensation is a post-case monetary
observation, **not fraud truth**. Resolved does not mean the customer was right.
Resolution text is measured for presence without exposing raw customer text.
Outcome dates after cutoff are reported, not included as available historical features.
No existing field establishes a verified dispute verdict linked to a specific transaction.

## 9. Potential labels — NOT YET APPROVED FOR MODELING

{table(label_assessment, ['label','coverage_pct','semantic_meaning','known_leakage_risks','known_linkage_limitations','potential_use','recommendation'])}

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

{table(matrix)}

## Preserved general EDA findings

{table(semantic)}

All 44,570 non-null complaint affected-product references point to existing products **owned by
different customers**. No repair or owner reassignment is allowed. complaint.origin_interaction_id
is entirely null. Customer and agent branch joins remain unreliable.
Digital anonymous share: {pct(digital['anonymous_pct'])}; do not attach those events to customers.
Transcript coverage: {pct(transcripts['interaction_coverage_pct'])} of all interactions and
{pct(transcripts['call_coverage_pct'])} of calls. Verified transcript → interaction identity does
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

**Yes, with constraints:** {fraud['total_transactions']} individually identified transactions,
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
"""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    files = sorted(p.name for p in ART.glob("*.csv"))
    (ART / "README.md").write_text(
        "# Transaction dispute EDA artifacts\n\n"
        "Generated by notebooks/02b_transaction_dispute_eda_addendum.ipynb. "
        "Full extract unless population explicitly states otherwise. "
        "Fraud rates are fractions of valid labels; *_pct values are percentages. "
        "NULL CSV cells are missing, not zero. Preserve response_code as string. "
        "No monetary distributions pool currencies. See reports/EDA_TRANSACTION_DISPUTE_ADDENDUM.md.\n\n"
        + "\n".join("- " + f for f in files) + "\n", encoding="utf-8")
    log("10. Matriz y reporte generados: GO WITH CONSTRAINTS para discovery, no adjudicación")
    return report
