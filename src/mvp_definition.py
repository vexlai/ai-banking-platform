"""Formal MVP contract from existing discovery artifacts; no new discovery queries."""
import csv
import json
from src.config import ROOT
from src.dispute_eda import digest
from src.dispute_reporting import table

OUT=ROOT/"artifacts/mvp_definition"
DISCOVERY=ROOT/"artifacts/dispute_case_workflow"


def read(name):
    with (DISCOVERY/name).open() as f:
        return list(csv.DictReader(f))


def define():
    OUT.mkdir(parents=True,exist_ok=True)
    contracts=[
        ("AuthenticatedPrincipal",["principal_ref","subject_ref","authorization_scope","verified_at","expires_at","auth_provider_ref"],
         ["session_ref"],"External identity provider; never utterance/LLM","verified_at <= as_of_time < expires_at","trusted only after external deterministic validation",False),
        ("DisputeIntake",["case_id","user_utterance","language","principal_ref","as_of_time","request_id"],
         ["customer_confirmed_clues"],"Untrusted customer request; exact text retained with access controls","server-assigned case.as_of_time","untrusted input",True),
        ("TransactionSearchRequest",["case_id","principal_ref","as_of_time","rule_version","lookback_days"],
         ["transaction_id","amount","currency","date_hint","merchant","transaction_type_hint","channel_hint"],
         "Confirmed clues and trusted principal separately; no currency/date guessing","bounded event_time <= as_of_time; explicit start/end inclusivity","validated request, not fact",True),
        ("TransactionCandidate",["candidate_transaction_id","owner_ref","product_ref","event_time","amount","currency","source_ref","retrieval_rule"],
         ["merchant","recorded_status","channel","type"],"Deterministic query result; relation to complaint is HEURISTIC",
         "event_time <= as_of_time; availability warning mandatory","observed transaction, unverified dispute link",False),
        ("TransactionSelection",["case_id","candidate_transaction_id","confirmed_by","confirmed_at","confirmation_ref"],
         ["clarification_history"],"Explicit customer/authorized-human confirmation; never count=1 alone",
         "confirmation timestamp audited","attributed selection, not fraud verdict",True),
        ("EvidenceBundle",["case_id","as_of_time","source_refs","core_facts","unknowns","guard_results","availability_limitations"],
         ["optional_context","retrospective_context"],"Allowlisted source evidence, independently aggregated domains",
         "admissible and retrospective evidence separate; snapshot attributes flagged","mixed trust with field provenance",False),
        ("GroundedSummary",["case_id","facts_with_evidence_refs","unknowns","unresolved_questions","generator_version"],
         ["draft_narrative"],"LLM-generated draft; deterministic references + human factual review",
         "only intake-admissible evidence may be asserted as intake facts","untrusted generated content",True),
        ("HandoffPackage",["case_id","user_request","authenticated_identity_reference","selected_transaction_or_candidates",
          "verified_facts","evidence_references","actions_taken","missing_evidence","unresolved_questions",
          "guard_results","state","as_of_time"],["draft_summary","handoff_receipt"],
         "Deterministic assembly; optional generated draft; authorized recipient","evidence snapshot/as_of plus handoff time distinct",
         "auditable package, not adjudication",True),
        ("CaseState",["case_id","state","version","updated_at","last_transition_id"],
         ["failure_reason"],"Deterministic guarded state store; FUTURE DESIGN","versioned event/recorded timestamps",
         "trusted only after guards; no engine implemented",False),
        ("AuditEvent",["event_id","case_id","request_id","idempotency_key","actor_ref","source_state","target_state",
          "event_time","recorded_at","evidence_refs","guard_results","rule_version"],["policy_version","model_version","approval_ref"],
         "Append-only future service audit; immutable evidence versions","event_time and recorded_at separately",
         "system-generated; LLM cannot author authority",False),
    ]
    contract_rows=[dict(zip(["contract","required_fields","optional_fields","provenance","as_of_time_rule",
                            "trust_level","LLM_values_require_confirmation"],r)) for r in contracts]
    inscope=["authenticated intake","structured clue extraction","clarification","deterministic transaction lookup",
        "bounded candidate retrieval","explicit transaction confirmation","ownership verification","evidence retrieval",
        "historical context retrieval","grounded summarization","unknown/missing evidence representation",
        "state tracking","human handoff","audit/provenance"]
    outside=["autonomous dispute adjudication","automatic reimbursement","money movement","fraud verdict",
        "automated rejection","automatic complaint-to-transaction linking","automatic closure",
        "invented banking policy","unsupported customer identity inference"]
    responsibilities=[
        {"owner":"AI / LLM","allowed":"intent/clue extraction; clarification drafting; evidence-grounded summary; unresolved questions; handoff draft",
         "forbidden":"auth/authz; ownership; resolving ambiguity as truth; policy invention; fraud verdict; approval/rejection; financial action; closure"},
        {"owner":"DETERMINISTIC","allowed":"external auth validation; authorization/account access; retrieval/filtering; temporal cutoff; currency/units; ownership; state guards; policy interface; audit; idempotency",
         "forbidden":"inventing policy, treating heuristic candidate as true match, claiming dataset identity equals authentication"},
        {"owner":"HUMAN","allowed":"unresolved ambiguity; conflicts; authoritative policy interpretation; adjudication; financial decisions; final outcome; closure",
         "forbidden":"bypassing authentication/authorization or leaving approvals unaudited"},
    ]
    metrics=[
        ("extraction correctness","per-field EM/P/R/F1 and full-schema EM, dev/test and es/pt separately","Report baseline; future improvement on frozen test without degrading safety"),
        ("schema validity","valid schemas / outputs","100% proposed acceptance gate"),
        ("hallucination","unsupported nonnull fields / expected-unknown slots and / predicted slots","0 desired; observed baseline failures retained"),
        ("clarification and missing clues","should_clarify accuracy; exact missing required clue set","Baseline first; human-reviewed annotations needed"),
        ("retrieval invariants","exact candidate set; missing/extra; future/ownership/auth exposure","100% fixture correctness; zero safety violations"),
        ("abstention","correct deny/clarify/abstain/handoff on contract fixtures","No autonomous decision; safety scenarios mandatory"),
        ("handoff quality","completeness; unsupported structured claims; valid evidence refs","All required sections; no unsupported facts"),
        ("state/audit validity","valid guarded transitions and audit fields","Future runtime only; NOT MEASURED here"),
        ("unsafe actions / authorization violations","forbidden actions or access violations / attempted requests","Zero required; fixture checks are not production certification"),
        ("latency/cost","per-case parser latency; future end-to-end/model cost","Report measured parser only; no invented production savings"),
    ]
    sections={}
    sections["Executive Decision"]="""**Transaction Dispute Intake & Investigation Copilot**

Decision: **GO WITH CONSTRAINTS**. Recommended workflow: **Option C, incorporating Option B
after explicit transaction selection**. This is not an autonomous dispute resolver, fraud
adjudicator or reimbursement system. This notebook freezes the selected use case, not a new search."""
    sections["Problem Evidence"]=table(read("candidate_dispute_cohorts.csv"))+"""

B is primary because Claims/Complaints explicitly record Transactions / Cargo no reconocido;
A is sensitivity (B subset of A), C is a separate optional fees lane, not pooled.
Prior 30d in B: **5,253 no / 3,015 unique / 2,209 multiple**, denominator **10,477**.
Percentages are 50.14%, 28.78%, 21.08% respectively (rounded).
Among 3,907 with amount+currency there is no exact candidate linkage; tolerances are heuristics.
No complaint→transaction ground truth; affected-product ownership is invalid for attribution,
origin_interaction_id is entirely null. A unique candidate is never a verified disputed transaction.
"""+"\n\nDigital context (denominator: candidate transactions):\n\n"+table(read("digital_context_feasibility.csv"))+\
        "\n\nTranscripts (denominator: nearby unique interactions):\n\n"+table(read("transcript_feasibility.csv"))+"""

ML fraud/ranking is not justified as an MVP dependency: severe imbalance, weak descriptive
non-score differences, unresolved label construction/availability and no matching labels.
Structured language extraction is a different, independently evaluable learned component.
Classification remains OBSERVED FACT / DERIVED FEATURE / HEURISTIC / INFERRED RELATIONSHIP /
HYPOTHESIS / FUTURE DESIGN. Source outputs are reused, not recomputed."""
    sections["User Problem"]="""An authenticated customer reports an unrecognized transaction.
Help identify candidate transactions, clarify missing clues, collect verifiable evidence,
preserve uncertainty and prepare a useful human handoff. Do not claim fraud determination
or dispute resolution. User-provided IDs and amounts are clues, not trusted account authority."""
    sections["Business Problem"]="""**PROJECTED / HYPOTHESIS:** reduce manual intake repetition,
standardize handoffs, reduce evidence omissions, improve traceability and reduce ungrounded decisions.
No measured production time/cost savings, ROI or dispute-resolution uplift is claimed."""
    sections["Scope"]="### In Scope\n\n"+table([{"capability":v,"boundary":"Future MVP scope; not runtime implemented in 04/05"} for v in inscope])+\
        "\n\n### Out of Scope\n\n"+table([{"capability":v,"status":"Excluded"} for v in outside])
    sections["AI / Deterministic / Human Responsibility Matrix"]=table(responsibilities)
    sections["Workflow"]="""AUTHENTICATED_REQUEST → INTAKE → CLUE_EXTRACTION → TRANSACTION_SEARCH
→ candidate branching → explicit confirmation → OWNERSHIP_VERIFICATION → EVIDENCE_COLLECTION
→ GROUNDED_SUMMARY → POLICY_GATE → HUMAN_HANDOFF.

- Normal: explicit ID or candidate, attributed customer/human confirmation, ownership, evidence, handoff.
- Ambiguous: multiple candidates → clarification; unresolved alternatives remain for human review.
- Unsupported/no candidate: preserve empty result/missing clues; clarify or handoff, never reject by inference.
- Human intervention: conflicts, missing required evidence/policy, financial decisions and adjudication.

Reuse the stage-03 transition specification unchanged. Authentication is an external dependency,
not implemented from dataset customer_id. No state machine engine is implemented here.
HANDOFF_RECORDED is the observable outcome; RESOLVED/CLOSED require external authorized outcome."""
    sections["Data Contracts"]=table(contract_rows)+"""

All LLM-originated fields carry source spans and generator/prompt version and remain untrusted
until validated; customer-confirmed clues and trusted external principal are distinct.
Contracts are conceptual specifications, not Pydantic models or production services."""
    sections["Evidence Model"]=table([
        {"level":"CORE","contents":"transaction ID; customer ownership; product relationship; timestamp; amount+currency; type; channel; recorded status",
         "limit":"Observed structure does not prove fraud or historical availability of status"},
        {"level":"OPTIONAL","contents":"merchant; geo; service; transcript; digital; historical behavior",
         "limit":"Missingness explicit; service/digital proximity is not causal linkage"},
        {"level":"QUARANTINED / UNSAFE FOR AUTHORITY","contents":"fraud_score; is_fraud as verdict; inferred complaint link; temporal proximity as proof; anonymous digital events",
         "limit":"Never decision authority; never stitch anonymous identities"}])
    sections["Time Safety"]="""Freeze case.as_of_time from trusted server context. Where applicable,
intake evidence must satisfy event_time <= case.as_of_time. Keep INTAKE-ADMISSIBLE EVIDENCE separate
from RETROSPECTIVE ANALYTICAL EVIDENCE; future candidates are never eligible at intake.
Historical features require history.event_time < candidate.event_time and explicit left-censor flags.
Availability-time safety is not fully certified: ingestion/revision timestamps are absent; snapshot
status, fraud flags and transcript availability require warnings. Resolution after intake is not
contemporaneous evidence. Relative language dates stay symbolic until resolved against trusted
as_of_time and a confirmed time zone; user_utterance alone must not invent a reference date."""
    sections["Success Criteria"]=table([dict(zip(["criterion","measurement","target_or_status"],r)) for r in metrics])+"""

Targets are proposed acceptance gates, not measured achievements. Dispute-resolution accuracy
and observed complaint→transaction recall are excluded because the required truth does not exist.
Future learned extraction uses the identical schema, frozen fixtures and deterministic retrieval:
improvement must come from extraction/clarification, not changed access or candidate rules."""
    sections["Demo Scenarios"]=table([
        {"scenario":"1 Normal / explicit confirmation","es":"No reconozco la transacción [ID]; quiero revisar sus detalles.",
         "expected":"Exact lookup, explicit confirmation, ownership, evidence, handoff"},
        {"scenario":"2 Ambiguous","es":"No reconozco un cargo por ese importe; aparecen varias operaciones.",
         "expected":"Clarify; preserve candidates; never auto-select truth"},
        {"scenario":"3 No candidate / unsupported","es":"No encuentro el cargo que quiero reclamar.",
         "expected":"Document missing evidence and retrieval limits; human handoff"}])+"""

Portuguese evaluation is required, but the source transcript language field has only es
(171,321 records; checked from the existing curated table). No observed Portuguese textual
coverage is claimed. Portuguese utterances in 05 are synthetic/team-generated, human linguistic
review pending. These are scenario definitions, not selected individual demo customers."""
    sections["Frozen MVP Contract"]="""**Version: mvp-contract-v1 — GO WITH CONSTRAINTS**

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
Changing scope, schema, annotation or test cases requires a new version and documented review."""
    payload={"version":"mvp-contract-v1","decision":"GO WITH CONSTRAINTS",
        "name":"Transaction Dispute Intake & Investigation Copilot","outcome":"HANDOFF_RECORDED",
        "in_scope":inscope,"out_of_scope":outside,"responsibilities":responsibilities,
        "data_contracts":contract_rows,"success_criteria":[dict(zip(["criterion","measurement","target"],r)) for r in metrics],
        "source_signatures":{p.name:digest(p) for p in sorted(DISCOVERY.glob("*.csv"))}}
    text=json.dumps(payload,ensure_ascii=False,indent=2)+"\n"
    frozen=OUT/"frozen_mvp_contract.json"
    if frozen.exists():
        assert frozen.read_text()==text,"Frozen contract differs; version and review the change"
    else:
        frozen.write_text(text)
    (OUT/"data_contracts.json").write_text(json.dumps(contract_rows,ensure_ascii=False,indent=2)+"\n")
    (ROOT/"reports/MVP_USE_CASE_DEFINITION.md").write_text(
        "# MVP Use Case Definition\n\n"+"\n\n".join("## "+k+"\n\n"+v for k,v in sections.items())+"\n")
    (ROOT/"reports/FROZEN_MVP_CONTRACT.md").write_text("# Frozen MVP Contract\n\n"+sections["Frozen MVP Contract"]+"\n")
    (OUT/"source_language_coverage.json").write_text(json.dumps({
        "source":"existing curated call_transcripts.detected_language",
        "es":171321,"pt":0,"limitation":"Recorded language labels; no full linguistic audit; no raw text exposed"})+"\n")
    return sections
