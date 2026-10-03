# Frozen MVP Contract

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
