"""FUTURE DESIGN artifacts and evidence-bound report. No workflow engine is implemented."""

import csv
import json
from src.data.config import ROOT
from src.data.workflows.dispute_workflow_data import ART, save, query, log
from src.data.workflows.dispute_reporting import table


def read(name):
    with (ART / name).open() as f:
        return list(csv.DictReader(f))


def future_design():
    responsibilities = [
        (
            "authenticate customer",
            "external/system, absent from dataset",
            "DETERMINISTIC",
            "HIGH for required boundary",
            "Must use authenticated principal; customer_id in a request is not authentication",
            "External IAM integration; no dataset-based substitute",
        ),
        (
            "retrieve transaction",
            "strong structural IDs",
            "DETERMINISTIC",
            "HIGH",
            "Exact ID lookup and explicit missing result",
            "No automatic identification from proximity",
        ),
        (
            "verify ownership",
            "validated transaction/product/customer consistency",
            "DETERMINISTIC",
            "HIGH within dataset",
            "Compare authenticated principal to returned owner",
            "Authentication and current access policy remain external",
        ),
        (
            "identify candidate transaction",
            "partial; ambiguity quantified by rule tables",
            "DETERMINISTIC",
            "MEDIUM",
            "Transparent customer/time/currency/amount retrieval; no probability or arbitrary ranking weights",
            "No verified complaint-transaction labels",
        ),
        (
            "confirm transaction selection",
            "candidate evidence only",
            "HUMAN",
            "REQUIRED",
            "Customer confirmation or documented authorized human selection",
            "Unique candidate is not a true-dispute label",
        ),
        (
            "extract complaint clues",
            "recorded taxonomy; raw text exists but not analyzed here",
            "LLM",
            "UNVALIDATED",
            "Future structured extraction with evidence spans and schema validation",
            "No LLM evaluation or privacy-approved text pipeline yet",
        ),
        (
            "compute behavioral context",
            "strict prior-event aggregates with censoring flags",
            "DETERMINISTIC",
            "MEDIUM",
            "Counts and same-currency summaries reproducible",
            "No availability/revision timestamps; not certified production point-in-time",
        ),
        (
            "risk assessment",
            "recorded rare label; no demonstrated generalizable signal",
            "ML",
            "LOW / NOT APPROVED",
            "Only a future research option after provenance and held-out validation",
            "Exclude fraud_score; post-event/synthetic-label risk",
        ),
        (
            "summarize evidence",
            "structured evidence bundle available",
            "LLM",
            "UNVALIDATED",
            "Potential grounded narrative and explicit unknowns",
            "Outputs require source references and evaluation; no decision authority",
        ),
        (
            "apply policy",
            "policy unavailable",
            "EXTERNAL_POLICY_SERVICE",
            "REQUIRED",
            "Versioned authoritative policy; deterministic application",
            "Missing policy must block financial eligibility/decision",
        ),
        (
            "adjudicate dispute",
            "no linked verified verdict",
            "HUMAN",
            "REQUIRED",
            "Human authorized review with external policy",
            "Resolved/compensation/is_fraud are not legal adjudication truth",
        ),
        (
            "create handoff record",
            "structured bundle and uncertainty available",
            "DETERMINISTIC",
            "HIGH for structure",
            "Persist evidence IDs, rule version, unknowns, actor and timestamps",
            "Optional LLM narrative cannot change structured facts",
        ),
        (
            "financial action authorization",
            "not supplied",
            "HUMAN",
            "REQUIRED",
            "External approval, authorization and idempotent audited execution",
            "Not part of proposed hackathon autonomous path",
        ),
        (
            "audit trail and state persistence",
            "architectural requirement, not observed source log",
            "DETERMINISTIC",
            "REQUIRED",
            "Append-only transitions, versions, evidence snapshot, actor, request IDs",
            "Future implementation; dataset does not already contain these transitions",
        ),
        (
            "case closure",
            "requires recorded authorized outcome",
            "DETERMINISTIC",
            "REQUIRED",
            "Guard against unresolved handoff or missing outcome record",
            "No LLM-only or snapshot-status-only closure",
        ),
    ]
    save(
        "workflow_responsibility_matrix.csv",
        [
            dict(
                zip(
                    [
                        "workflow_step",
                        "data_support",
                        "proposed_owner",
                        "confidence",
                        "reason",
                        "main_limitation",
                    ],
                    r,
                ),
                classification="FUTURE DESIGN, not implemented",
            )
            for r in responsibilities
        ],
    )
    # Human_required means an authorized human/user action is required by the proposed transition.
    transitions = [
        (
            "CASE_CREATED",
            "AUTH_REQUIRED",
            "Intake received",
            "request_id; untrusted claimed identity",
            "Generate case/request ID and persist untrusted intake; no account evidence exposed",
            False,
            False,
            "AUTH_REQUIRED",
        ),
        (
            "AUTH_REQUIRED",
            "INTAKE_INCOMPLETE",
            "External identity verification succeeds",
            "signed current principal; authorization scope",
            "Verify issuer, expiry, scope and subject via external auth; never trust LLM identity",
            False,
            False,
            "AUTH_FAILED",
        ),
        (
            "AUTH_REQUIRED",
            "AUTH_FAILED",
            "Identity verification fails",
            "auth failure record",
            "Deny account reads; audit failure without leaking customer data",
            False,
            False,
            "AUTH_FAILED",
        ),
        (
            "AUTH_FAILED",
            "AUTH_REQUIRED",
            "Authorized retry",
            "new valid auth attempt",
            "Rate limits and external retry policy; no bypass through human narrative",
            False,
            True,
            "AUTH_FAILED",
        ),
        (
            "INTAKE_INCOMPLETE",
            "TRANSACTION_SEARCH",
            "Minimum clues supplied",
            "authenticated customer plus transaction_id OR explicit search date/window",
            "Validate types/units; preserve missing amount/currency; confirm extracted clues with user",
            True,
            True,
            "INTAKE_INCOMPLETE",
        ),
        (
            "TRANSACTION_SEARCH",
            "NO_CANDIDATE",
            "Empty eligible retrieval",
            "versioned query and count=0",
            "Only same authorized customer and nonfuture admissible transactions; expose empty result",
            False,
            False,
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "TRANSACTION_SEARCH",
            "MULTIPLE_CANDIDATES",
            "More than one eligible candidate",
            "candidate IDs and deterministic rule trace",
            "Retain alternatives; no weighted score promoted to truth",
            False,
            False,
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "TRANSACTION_SEARCH",
            "TRANSACTION_SELECTED",
            "One candidate explicitly confirmed",
            "candidate evidence + recorded customer/human confirmation",
            "Count=1 is insufficient alone; require attributed selection and authorization",
            False,
            True,
            "HUMAN_REVIEW",
        ),
        (
            "MULTIPLE_CANDIDATES",
            "TRANSACTION_SELECTED",
            "Explicit disambiguation",
            "recorded selection by customer/authorized human",
            "Selected ID must belong to admissible retrieved/explicit-ID result and current owner",
            False,
            True,
            "HUMAN_REVIEW",
        ),
        (
            "MULTIPLE_CANDIDATES",
            "HUMAN_REVIEW",
            "Ambiguity remains",
            "alternatives; missing clues; retrieval trace",
            "Do not infer a true match",
            True,
            True,
            "HUMAN_REVIEW",
        ),
        (
            "NO_CANDIDATE",
            "INTAKE_INCOMPLETE",
            "Customer can clarify clues",
            "new date/amount/currency/ID, with provenance",
            "Never manufacture amount or expand to other customers",
            True,
            True,
            "HUMAN_REVIEW",
        ),
        (
            "NO_CANDIDATE",
            "HUMAN_REVIEW",
            "No further safe clarification",
            "empty-result evidence and limits",
            "No automated denial or reimbursement from missing candidates",
            True,
            True,
            "HUMAN_REVIEW",
        ),
        (
            "TRANSACTION_SELECTED",
            "OWNERSHIP_VERIFIED",
            "Ownership check succeeds",
            "authenticated principal; transaction/product/customer records",
            "Exact subject equality plus validated structural relationship and current access policy",
            False,
            False,
            "HUMAN_REVIEW",
        ),
        (
            "TRANSACTION_SELECTED",
            "HUMAN_REVIEW",
            "Conflicting ownership/evidence",
            "access-safe conflict record",
            "Block selection and financial action; do not repair complaint affected_product_id",
            False,
            True,
            "HUMAN_REVIEW",
        ),
        (
            "OWNERSHIP_VERIFIED",
            "EVIDENCE_COLLECTION",
            "Authorized evidence reads",
            "transaction ID; sources; as-of time",
            "Read allowlisted fields; mark snapshot timing and inferred service/digital links",
            False,
            False,
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "EVIDENCE_COLLECTION",
            "INSUFFICIENT_EVIDENCE",
            "Required evidence missing",
            "explicit missingness + source errors",
            "Distinguish optional sparsity from required ownership/core evidence absence",
            False,
            False,
            "HUMAN_REVIEW",
        ),
        (
            "EVIDENCE_COLLECTION",
            "ASSESSMENT_READY",
            "Required bundle complete",
            "core facts, optional evidence flags, provenance",
            "Schema/ownership/as-of checks; no post-intake outcomes used as intake facts",
            False,
            False,
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "INSUFFICIENT_EVIDENCE",
            "HUMAN_REVIEW",
            "Evidence cannot safely be completed",
            "unknowns and conflicts",
            "No fabricated evidence or default fraud verdict",
            True,
            True,
            "HUMAN_REVIEW",
        ),
        (
            "ASSESSMENT_READY",
            "POLICY_REVIEW_REQUIRED",
            "Summary prepared",
            "grounded summary + structured bundle",
            "Validate references and factual consistency; LLM may draft but cannot authorize eligibility",
            True,
            False,
            "HUMAN_REVIEW",
        ),
        (
            "POLICY_REVIEW_REQUIRED",
            "HUMAN_REVIEW",
            "Policy missing, ambiguous or financial decision needed",
            "policy version OR explicit missing-policy flag",
            "Missing policy blocks autonomous decision; all current dataset cases require escalation",
            False,
            True,
            "HUMAN_REVIEW",
        ),
        (
            "HUMAN_REVIEW",
            "HANDOFF_RECORDED",
            "Authorized reviewer/queue accepts handoff",
            "handoff_id; recipient; evidence snapshot; unresolved questions",
            "Persist acceptance and audit receipt; this is NOT a resolved dispute",
            True,
            True,
            "HUMAN_REVIEW",
        ),
        (
            "HANDOFF_RECORDED",
            "HUMAN_REVIEW",
            "Authorized reviewer resumes",
            "assigned actor; preserved evidence; current policy",
            "Idempotent versioned transition with current authorization",
            False,
            True,
            "HUMAN_REVIEW",
        ),
        (
            "HUMAN_REVIEW",
            "RESOLVED",
            "External authorized outcome supplied",
            "signed human outcome; authoritative policy; financial-action approval if applicable",
            "NO dataset-only authority; require external approvals; unsupported until integrated",
            False,
            True,
            "HUMAN_REVIEW",
        ),
        (
            "RESOLVED",
            "CLOSED",
            "Authorized completion recorded",
            "outcome record; approval trail; notification receipt; no pending action",
            "Versioned deterministic closure checks; no LLM-only closure or inferred resolution",
            False,
            True,
            "HUMAN_REVIEW",
        ),
    ]
    records = [
        dict(
            zip(
                [
                    "source_state",
                    "target_state",
                    "trigger",
                    "required_evidence",
                    "deterministic_guard",
                    "AI_allowed",
                    "human_required",
                    "failure_state",
                ],
                r,
            ),
            classification="FUTURE DESIGN ONLY",
        )
        for r in transitions
    ]
    save("proposed_case_state_machine.csv", records)
    (ART / "proposed_case_state_machine.json").write_text(
        json.dumps(
            {
                "classification": "FUTURE DESIGN ONLY; no executable engine",
                "initial_state": "CASE_CREATED",
                "mvp_terminal_observation": "HANDOFF_RECORDED",
                "forbidden_llm_authorities": [
                    "authentication",
                    "authorization",
                    "ownership",
                    "financial_action",
                    "policy_eligibility",
                    "case_closure",
                ],
                "transition_audit_fields": [
                    "case_id",
                    "transition_id",
                    "idempotency_key",
                    "previous_version",
                    "new_version",
                    "source_state",
                    "target_state",
                    "actor_id",
                    "actor_role",
                    "event_time",
                    "recorded_at",
                    "evidence_ids",
                    "evidence_hashes",
                    "rule_version",
                    "policy_version",
                    "model_version_if_used",
                    "guard_results",
                    "human_approval_reference",
                    "failure_reason",
                ],
                "transitions": records,
            },
            indent=2,
        )
        + "\n"
    )
    options = [
        (
            "A",
            "Transaction inquiry only",
            "HIGH",
            "LOW",
            "HIGH for lookup/ownership invariants",
            "LOW with external auth",
            "MEDIUM",
            "Does not demonstrate stateful dispute handling",
            "Fallback",
        ),
        (
            "B",
            "Transaction investigation + structured evidence summary",
            "HIGH with optional gaps",
            "MEDIUM",
            "HIGH for evidence fidelity; LLM fidelity needs held-out review",
            "MEDIUM",
            "HIGH",
            "No verified dispute verdict or policy; optional context weak",
            "Investigation subworkflow",
        ),
        (
            "C",
            "Dispute intake + candidate retrieval + human handoff",
            "MEDIUM with explicit ambiguity",
            "MEDIUM",
            "HIGH for guards/provenance; unknown linkage prevents true-match accuracy",
            "CONTROLLED with mandatory human boundary",
            "HIGH",
            "No reliable complaint-transaction labels; needs future auth/policy/queue integration",
            "RECOMMENDED, with B when a transaction is explicitly confirmed",
        ),
        (
            "D",
            "Autonomous dispute adjudication",
            "UNSUPPORTED",
            "HIGH",
            "UNSUPPORTED for correctness",
            "UNACCEPTABLE on present evidence",
            "Misleading without policy/ground truth",
            "No verified outcome linkage, policy, auth or financial-action authority",
            "NO-GO",
        ),
    ]
    save(
        "mvp_scope_assessment.csv",
        [
            dict(
                zip(
                    [
                        "option",
                        "scope",
                        "data_feasibility",
                        "engineering_complexity",
                        "evaluation_feasibility",
                        "risk",
                        "hackathon_value",
                        "main_blocker",
                        "recommendation",
                    ],
                    r,
                ),
                classification="FUTURE DESIGN",
            )
            for r in options
        ],
    )
    log(
        "14–16. Responsabilidades, máquina de estados propuesta y opciones MVP; sin implementación"
    )


def validate(con):
    checks = []

    def check(name, condition):
        assert condition, name
        checks.append(dict(check=name, passed=True))

    check(
        "B_subset_A",
        con.execute("""SELECT count(*) FROM membership b ANTI JOIN membership a
      ON b.complaint_id=a.complaint_id AND a.cohort='A' WHERE b.cohort='B'""").fetchone()[
            0
        ]
        == 0,
    )
    check(
        "no_foreign_customer_candidates",
        con.execute("""SELECT count(*) FROM candidate_pairs p
      JOIN cases c USING(complaint_id) JOIN candidates t USING(transaction_id)
      WHERE c.customer_id IS DISTINCT FROM t.customer_id""").fetchone()[0]
        == 0,
    )
    check(
        "bounded_30_day_pairs",
        con.execute(
            "SELECT count(*) FROM candidate_pairs WHERE abs(delta_hours)>720"
        ).fetchone()[0]
        == 0,
    )
    check(
        "no_cross_currency_amount_comparison",
        con.execute("""SELECT count(*) FROM candidate_pairs
      WHERE amount_difference IS NOT NULL AND same_currency IS NOT TRUE""").fetchone()[
            0
        ]
        == 0,
    )
    check(
        "strict_prior_features",
        con.execute(
            "SELECT count(*) FROM prior_pairs WHERE age_days<=0 OR age_days>90"
        ).fetchone()[0]
        == 0,
    )
    check(
        "features_one_per_candidate",
        con.execute(
            "SELECT count(*)=count(DISTINCT transaction_id) FROM behavior_features"
        ).fetchone()[0],
    )
    for r in read("complaint_transaction_window_summary.csv"):
        check(
            "window_count_partition_" + r["cohort"] + "_" + r["days"],
            sum(
                int(r[k])
                for k in ("zero_candidates", "unique_candidate", "multiple_candidates")
            )
            == int(r["eligible_complaints"]),
        )
    for i, r in enumerate(read("candidate_rule_comparison.csv")):
        check(
            f"rule_partition_{i}",
            sum(
                int(r[k])
                for k in ("no_candidate", "unique_candidate", "multiple_candidates")
            )
            == int(r["eligible_complaints"]),
        )
    check(
        "rule_monotonicity",
        con.execute("""SELECT count(*) FROM complaint_counts
      WHERE exact_count>absolute_1_count OR exact_count>relative_1pct_count
      OR relative_1pct_count>relative_5pct_count OR relative_5pct_count>currency_count
      OR currency_count>temporal_count OR prior_exact_count>exact_count
      OR prior_count>temporal_count""").fetchone()[0]
        == 0,
    )
    check(
        "no_future_service_in_intake_view",
        con.execute("""SELECT count(*) FROM evidence_bundles
       WHERE NOT candidate_exists_by_intake AND interaction_count_observed_by_intake<>0""").fetchone()[
            0
        ]
        == 0,
    )
    columns = {r[0] for r in con.execute("DESCRIBE evidence_bundles").fetchall()}
    check(
        "no_ground_truth_field",
        not columns.intersection(
            {"matched_transaction", "true_disputed_transaction", "ground_truth_match"}
        ),
    )
    check(
        "full_case_register",
        con.execute("SELECT count(*) FROM cases").fetchone()[0]
        == con.execute(
            f"SELECT count(*) FROM read_parquet('{ART / 'case_register.parquet'}')"
        ).fetchone()[0],
    )
    (ART / "validation_checks.json").write_text(
        json.dumps({"passed": len(checks), "failed": 0, "checks": checks}, indent=2)
        + "\n"
    )
    log(f"{len(checks)} controles de consistencia correctos")


def report(context):
    cohorts = read("candidate_dispute_cohorts.csv")
    windows = read("complaint_transaction_window_summary.csv")
    amounts = read("amount_currency_candidate_matching.csv")
    behavior = read("behavioral_feature_feasibility.csv")
    service = read("service_interaction_proximity.csv")
    transcripts = read("transcript_feasibility.csv")
    digital = read("digital_context_feasibility.csv")
    bundles = read("evidence_bundle_summary.csv")[0]
    dimensions = read("fraud_signal_without_score.csv")
    fractions = [
        r
        for r in dimensions
        if r["population"] == "all_cutoff_transactions"
        and r["field"] == "transaction_type"
    ]
    fraud_n = sum(int(r["fraud_recorded_count"]) for r in fractions)
    total_n = sum(int(r["valid_recorded_labels"]) for r in fractions)
    b30 = next(r for r in windows if r["cohort"] == "B" and r["days"] == "30")
    b1 = next(r for r in windows if r["cohort"] == "B" and r["days"] == "1")
    exact_b = [
        r
        for r in amounts
        if r["cohort"] == "B" and r["days"] == "30" and r["rule"] == "exact"
    ]
    rel_b = [
        r
        for r in amounts
        if r["cohort"] == "B" and r["days"] == "30" and r["rule"] == "relative_5pct"
    ]
    exact_unique = sum(int(r["unique_candidate"]) for r in exact_b)
    relative_unique = sum(int(r["unique_candidate"]) for r in rel_b)
    exact_eligible = sum(int(r["eligible_complaints"]) for r in exact_b)
    candidate_fraud = sum(
        int(r["records"])
        for r in read("fraud_amount_without_score_by_currency.csv")
        if r["population"] == "unique_candidates_plus_minus_30d"
        and r["is_fraud"] == "True"
    )
    prior_b = [
        r
        for r in read("candidate_rule_comparison.csv")
        if r["cohort"] == "B" and r["days"] == "30" and r["rule"] == "prior_temporal"
    ]
    prior_totals = {
        k: sum(int(r[k]) for r in prior_b)
        for k in (
            "eligible_complaints",
            "no_candidate",
            "unique_candidate",
            "multiple_candidates",
        )
    }
    learned_range = [
        dict(
            dimension=f,
            minimum_rate_pct=min(
                float(r["recorded_fraud_pct"])
                for r in dimensions
                if r["population"] == "all_cutoff_transactions" and r["field"] == f
            ),
            maximum_rate_pct=max(
                float(r["recorded_fraud_pct"])
                for r in dimensions
                if r["population"] == "all_cutoff_transactions" and r["field"] == f
            ),
        )
        for f in [
            "transaction_type",
            "channel",
            "transaction_category",
            "transaction_status",
            "merchant_category",
            "transaction_country",
        ]
    ]
    save("non_score_fraud_rate_ranges.csv", learned_range)
    text = f"""# Dispute Case Workflow Findings

## 1. Executive conclusion

**GO WITH CONSTRAINTS** for a stateful dispute-intake / candidate-retrieval / evidence / human-handoff
system. **NO-GO for autonomous adjudication or financial action.** The dataset supplies grounded
transaction records but does not supply complaint-to-transaction truth, authentication, policy,
decision authority or an operational case transition log.

Executed: {context["execution_timestamp"]}. Inherited cutoff: {
        context["feature_cutoff_inclusive"]
    } inclusive.
Transactions/complaints/service/digital after this cutoff are audited and excluded from this stage.
No general EDA or profiling is rerun. See population_cutoff_audit.csv for exact exclusions.
All computations are exhaustive over the stated populations; no sampling or demo-customer selection.

Classification convention throughout:
OBSERVED FACT = supplied field; DERIVED FEATURE = documented aggregate;
HEURISTIC = retrieval rule/cohort/archetype; INFERRED RELATIONSHIP = same-customer temporal association;
HYPOTHESIS = possible later interpretation; FUTURE DESIGN = unimplemented architecture.
No unique candidate becomes a verified dispute link.

## 2. Dispute cohort recommendation

{table(cohorts)}

{table(read("candidate_cohort_definitions.csv"))}

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

{table(windows)}

For B, ±1 day gives zero/unique/multiple =
**{b1["zero_candidates"]}/{b1["unique_candidate"]}/{b1["multiple_candidates"]}**
out of **{b1["eligible_complaints"]}** complaints; ±30 days gives
**{b30["zero_candidates"]}/{b30["unique_candidate"]}/{b30["multiple_candidates"]}**
out of the same stated cohort. Full-window and boundary-censored denominators are explicit.
These are candidate-search outcomes, **not recall, accuracy or proof that a transaction was disputed**.
Restricting B to the **prior 30 days** gives no/unique/multiple =
**{prior_totals["no_candidate"]}/{prior_totals["unique_candidate"]}/{
        prior_totals["multiple_candidates"]
    }**
out of **{
        prior_totals["eligible_complaints"]
    }** complaints. This removes future candidates, not uncertainty.

### Amount and currency

Exact comparison uses DECIMAL(24,6), validated against source precision; no binary-float equality.
Currency must be equal. Absolute tolerance is at most 1 unit **of that currency**.
Relative tolerances are abs(transaction amount - claim amount)/abs(claim amount) <=1% or <=5%;
zero claim amounts are ineligible for relative rules. No FX conversion, no silent preferred tolerance.
Missing clues remain in the ineligible count; they are not counted as failed matches.
All monetary rule tables are stratified by currency.

{
        table(
            [r for r in amounts if r["cohort"] == "B" and r["days"] == "30"],
            [
                "currency",
                "rule",
                "eligible_complaints",
                "ineligible_complaints",
                "no_candidate",
                "unique_candidate",
                "multiple_candidates",
                "candidate_rate_pct",
                "ambiguity_pct_eligible",
            ],
        )
    }

B has {exact_unique} unique exact candidates and {
        relative_unique
    } unique <=5% candidates within ±30d,
among {exact_eligible} complaints eligible by both amount and currency.
These counts are across distinct currency strata, not pooled monetary distributions.
candidate_rules_common_eligibility.csv holds populations constant across rule comparisons.
candidate_rule_comparison.csv additionally compares before-or-at-complaint rules.
No arbitrary weighted rank or threshold is selected. Status is presented as evidence, not filtered
without a policy basis.

{table([r for r in read("candidate_currency_support.csv") if r["cohort"] == "B"])}

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
The union population has {
        bundles["pairs_not_after_intake"]
    } pairs before/at intake versus
{bundles["future_pairs_retrospective_only"]} after, out of {
        bundles["complaint_candidate_pairs"]
    } pairs:
roughly symmetric proximity does not establish the triggering transaction.

## 4. Evidence available per case

Pair-grain artifact: {bundles["complaint_candidate_pairs"]} candidate pairs,
{bundles["complaints_with_candidate"]} complaints with a candidate and
{bundles["unique_candidate_transactions"]} distinct candidate transactions.
{
        bundles["future_pairs_retrospective_only"]
    } pairs are after intake and are **not intake-admissible**.
case_register.parquet separately retains zero-candidate complaints; case IDs are derived analytical IDs.

- **Core observed evidence:** transaction ID, customer/product ownership backbone, timestamp,
  amount+currency, type, channel and literal recorded status.
- **Optional/sparse:** merchant, response code, coordinates, historical context, nearby service and
  identified digital activity. Missing optional evidence is not itself suspicious.
- **Recorded-only, quarantined semantics:** is_fraud and fraud_score availability. They are not
  approved risk predictors, probability, legal fraud verdict or action authorization.
- **Unsafe:** complaint/product ownership, complaint/origin contact, true complaint/transaction link;
  anonymous digital identity; assigning a service contact to a transaction from proximity.

{table(service)}

Service windows are disjoint [0,24h], (24,72h], (72,168h], (168,336h].
Rates of resolution/escalation use valid labels on transaction-interaction pairs (same interaction
may appear for multiple transactions). Distinct interaction counts are separately reported.
Coverage denominators include all candidate transactions; some boundary windows are partially
observed, so absence of an event in those windows is not proof of a complete negative history.
These outcomes are current recorded flags, not proven available at contact start.

{table(transcripts)}

{table(read("transcript_metadata_feasibility.csv"))}

Metadata fields exist in raw, not in the original curated projection. Only nonnull/nonempty
indicators were recovered; no raw text or entity values are exposed. Empty lists/objects are not
counted as populated metadata. Existing metadata may itself be generated output, not verified NLP truth.
transcript_selection_comparison.csv compares available/unavailable groups by channel/type/reason;
partial coverage and temporal/customer selection prevent assuming representativeness.

{table(digital)}

Digital before windows are nested and must not be summed; after excludes neither zero timestamp nor
future elapsed time but is explicitly retrospective. Only identified events are used. Product ID
coverage is conditional evidence, not a transaction link. event_value units are undocumented.
**Exclude digital context from the core MVP**, retaining it as optional research context.

Bundles aggregate each domain independently, avoiding service×digital event multiplication.
Intake-time event counts require event_time <= complaint creation; retrospective counts are named
separately. Transcript existence in the extract does not establish transcript availability at intake.
Recorded status/fraud availability times are unknown and flagged explicitly.

## 5. Point-in-time safe behavioral context

{
        table(
            behavior,
            [
                "feature",
                "candidate_transactions",
                "computable_count",
                "computable_pct",
                "complete_history_window_count",
                "computable_complete_window_count",
                "recommendation",
            ],
        )
    }

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

Recorded positive class: **{fraud_n}/{total_n} ({
        100 * fraud_n / total_n:.6f}%)** within this stage's cutoff.
Extreme imbalance must be preserved in evaluation. No classifier, predictive threshold or learned
ranker was trained.

{table(learned_range)}

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
non-score separation is demonstrated here. Only {
        candidate_fraud
    } recorded positives occur among
{
        bundles["unique_candidate_transactions"]
    } unique candidates, leaving little support for interpreting
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

{
        table(
            read("case_archetypes.csv"),
            [
                "cohort",
                "archetype",
                "population_size",
                "cohort_complaints",
                "pct_cohort",
                "representative_evidence_pattern",
                "recommended_handling",
            ],
        )
    }

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

{
        table(
            read("proposed_case_state_machine.csv"),
            [
                "source_state",
                "target_state",
                "trigger",
                "required_evidence",
                "deterministic_guard",
                "AI_allowed",
                "human_required",
                "failure_state",
            ],
        )
    }

The JSON specification also defines future audit fields: actor, transition/state version, evidence
references/hashes, event/recorded time, rule/policy/model versions, guard results, human approval and
idempotency key. Dataset complaints.status does not constitute such a transition log.

## 10. Recommended MVP

{table(read("mvp_scope_assessment.csv"))}

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
"""
    (ROOT / "reports/DISPUTE_CASE_WORKFLOW_FINDINGS.md").write_text(
        text, encoding="utf-8"
    )
    (ART / "README.md").write_text(
        "# Dispute case workflow discovery\n\nAll links are candidates/inferred, never true dispute matches. "
        "Percentages name their denominators; null CSV cells are unknown, not zero. "
        "Currencies remain separate; source response codes are strings. "
        "Cohort B is nested in A. Pair-grain bundles can include retrospective future candidates: "
        "filter candidate_exists_by_intake and require explicit selection for any future intake use. "
        "Event-time ordering does not prove ingestion-time availability.\n\n"
        + "\n".join(
            "- " + p.name
            for p in sorted(ART.iterdir())
            if p.suffix in {".csv", ".json", ".parquet"}
        )
        + "\n",
        encoding="utf-8",
    )
    return text
