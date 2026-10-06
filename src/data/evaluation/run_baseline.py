"""Freeze evaluation/code before scoring. No calls to learned models or production services."""

import csv
import json
import platform
import subprocess
from collections import Counter
from datetime import datetime, timezone
from time import perf_counter
from statistics import median

from src.data.config import ARTIFACTS_DIR, REPORTS_DIR, ROOT
from src.data.eda.dispute_eda import digest
from .baseline_intake_parser import (
    FIELDS,
    VERSION as PARSER_VERSION,
    extract,
    intake_flags,
)
from .dataset import OUT, VERSION, freeze, jsonl, write_json
from .metrics import (
    extraction_metrics,
    retrieval_metrics,
    handoff_score,
    HANDOFF_FIELDS,
)


def load(name):
    return [json.loads(line) for line in (OUT / name).read_text().splitlines()]


def run():
    cases = load("dispute_intake_eval.jsonl")
    fixtures = load("retrieval_fixtures.jsonl")
    groups = {
        split: {c["group_id"] for c in cases if c["split"] == split}
        for split in ("development", "test")
    }
    assert not groups["development"] & groups["test"]
    for split in groups:
        assert {f["group_id"] for f in fixtures if f["split"] == split} <= groups[split]
    code_files = [
        ROOT / "src/data/evaluation/baseline_intake_parser.py",
        ROOT / "src/data/evaluation/metrics.py",
    ]
    lock = {
        "baseline_version": PARSER_VERSION,
        "dataset_version": VERSION,
        "code_sha256": {str(p.relative_to(ROOT)): digest(p) for p in code_files},
        "dataset_sha256": digest(OUT / "dispute_intake_eval.jsonl"),
        "retrieval_fixtures_sha256": digest(OUT / "retrieval_fixtures.jsonl"),
    }
    freeze(
        OUT / "baseline_lock.json", json.dumps(lock, sort_keys=True, indent=2) + "\n"
    )
    # Gold labels are not passed to the extractor.
    predictions = []
    latencies = []
    for case in cases:
        start = perf_counter()
        predicted = extract(case["user_utterance"])
        latencies.append(1000 * (perf_counter() - start))
        flags = intake_flags(predicted)
        if flags["should_handoff"]:
            template = (
                "Requiere revisión humana; no se realizó ninguna acción financiera."
                if case["language"] == "es"
                else "É necessária revisão humana; nenhuma ação financeira foi realizada."
            )
        elif flags["should_clarify"]:
            template = (
                "Indica el ID de transacción o importe, moneda y fecha; confirma las pistas."
                if case["language"] == "es"
                else "Informe o ID da transação ou valor, moeda e data; confirme as informações."
            )
        else:
            template = (
                "Pistas listas para búsqueda; la transacción requiere confirmación explícita."
                if case["language"] == "es"
                else "Informações prontas para consulta; a transação exige confirmação explícita."
            )
        predictions.append(
            {
                "case_id": case["case_id"],
                "split": case["split"],
                "language": case["language"],
                "prediction": predicted,
                **flags,
                "static_response": template,
                "scope": "Offline extraction/template only; no live query, handoff acceptance or financial action",
            }
        )
    (OUT / "baseline_predictions.jsonl").write_text(
        jsonl(predictions), encoding="utf-8"
    )
    slices = {}
    for split in ("development", "test"):
        for language in ("all", "es", "pt"):
            idx = [
                i
                for i, c in enumerate(cases)
                if c["split"] == split
                and (language == "all" or c["language"] == language)
            ]
            gold = [cases[i] for i in idx]
            predicted = [predictions[i]["prediction"] for i in idx]
            metrics = extraction_metrics(gold, predicted)
            required_correct = 0
            for c, p in zip(gold, predicted, strict=True):
                actual = (
                    []
                    if p["transaction_id"] or p["intent"] == "unsupported_action"
                    else [
                        f for f in ("amount", "currency", "date_hint") if p[f] is None
                    ]
                )
                required_correct += set(actual) == set(
                    c["expected_missing_required_fields"]
                )
            metrics["missing_required_clue_set_exact_match"] = required_correct / len(
                gold
            )
            slices[split + "/" + language] = metrics
    retrieval = {}
    retrieval_outputs = []
    for split in ("development", "test"):
        outputs, metrics = retrieval_metrics(
            [f for f in fixtures if f["split"] == split]
        )
        retrieval[split] = metrics
        retrieval_outputs += [dict(r, split=split) for r in outputs]
    (OUT / "retrieval_predictions.jsonl").write_text(jsonl(retrieval_outputs))
    latency = sorted(latencies)
    result = {
        "baseline_version": PARSER_VERSION,
        "dataset_version": VERSION,
        "extraction": slices,
        "retrieval": retrieval,
        "parser_latency_ms": {
            "calls": len(latency),
            "median": median(latency),
            "p95": latency[int(0.95 * (len(latency) - 1))],
            "max": max(latency),
            "scope": "local in-process regex only; not end-to-end system/LLM latency",
        },
        "external_model_calls": 0,
        "external_model_cost": 0,
        "production_cost": "NOT MEASURED",
        "unsafe_action_rate": "NOT MEASURED: no actions/runtime implemented",
        "state_transition_validity": "NOT MEASURED: specification only",
        "safety": "Retrieval invariants measured on synthetic tables; other safety fixtures are expected contracts, not certification",
    }
    write_json(OUT / "baseline_metrics.json", result)
    # Rubric validator is exercised independently with a valid and a deliberately corrupt handoff.
    evidence = {"e1": {"amount": "10.00", "currency": "USD"}}
    package = {f: [] for f in HANDOFF_FIELDS}
    package.update(
        user_request="Synthetic request",
        authenticated_identity_reference="fixture-principal",
        selected_transaction_or_candidates=["fixture-tx"],
        verified_facts=[{"field": "amount", "value": "10.00", "evidence_id": "e1"}],
        evidence_references=["e1"],
        guard_results={"fixture_only": True},
        state="HUMAN_REVIEW",
        as_of_time="2026-06-17T12:00:00",
    )
    corrupt = {
        **package,
        "verified_facts": [{"field": "amount", "value": "999.00", "evidence_id": "e1"}],
        "evidence_references": ["invented"],
    }
    del corrupt["as_of_time"]
    rubric = {
        "required_fields": list(HANDOFF_FIELDS),
        "completeness": "present nonnull required sections / required sections",
        "unsupported_claim": "structured fact lacks an equal field/value in its referenced evidence",
        "evidence_reference_validity": "references found / supplied references; undefined if no references",
        "limitations": "Presence does not prove meaningful content; prose entailment/policy meaning require human review; no LLM judge",
    }
    write_json(OUT / "handoff_rubric.json", rubric)
    scores = {
        "valid_fixture": handoff_score(package, evidence),
        "corrupt_fixture": handoff_score(corrupt, evidence),
    }
    assert scores["valid_fixture"]["unsupported_claim_count"] == 0
    assert scores["corrupt_fixture"]["unsupported_claim_count"] == 1
    assert scores["corrupt_fixture"]["missing_required_section_count"] == 1
    assert scores["corrupt_fixture"]["invalid_reference_count"] == 1
    write_json(OUT / "handoff_fixture_results.json", scores)
    write_json(
        OUT / "safety_contract_status.json",
        {
            "cases": len(load("safety_fixtures.jsonl")),
            "implemented_offline_checks": [
                "invalid/expired auth blocks fixture retrieval",
                "ownership",
                "as_of",
                "currency",
                "candidate ambiguity",
            ],
            "not_implemented": [
                "production authentication/authorization",
                "prompt-injection defense runtime",
                "tool orchestration",
                "policy engine",
                "financial action",
                "state engine",
                "handoff UI",
            ],
            "remaining_scenarios": "Expected deny/clarify/abstain/handoff in safety_fixtures.jsonl; future implementation must be tested",
        },
    )
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": list(FIELDS),
        "properties": {f: {"type": ["string", "null"]} for f in FIELDS},
    }
    schema["properties"]["intent"] = {
        "enum": [
            "dispute_intake",
            "transaction_inquiry",
            "unsupported_action",
            "unknown",
        ]
    }
    schema["properties"]["amount"] = {
        "anyOf": [{"type": "null"}, {"type": "string", "pattern": r"^\d+\.\d{2}$"}]
    }
    schema["properties"]["currency"] = {
        "anyOf": [{"type": "null"}, {"type": "string", "pattern": "^[A-Z]{3}$"}]
    }
    schema["properties"]["transaction_id"] = {
        "anyOf": [{"type": "null"}, {"type": "string", "pattern": "^TX-[A-Z0-9]{12}$"}]
    }
    schema["properties"]["date_hint"] = {
        "anyOf": [
            {"type": "null"},
            {
                "type": "string",
                "pattern": r"^(\d{4}-\d{2}-\d{2}|relative:(today|yesterday|days_ago:\d+))$",
            },
        ]
    }
    schema["properties"]["transaction_type_hint"] = {
        "enum": [
            None,
            "Purchase",
            "Withdrawal",
            "Transfer",
            "Payment",
            "Deposit",
            "Adjustment",
        ]
    }
    schema["properties"]["channel_hint"] = {
        "enum": [None, "ATM", "App", "Web", "POS", "Branch"]
    }
    freeze(OUT / "intake_output.schema.json", json.dumps(schema, indent=2) + "\n")
    interface = {
        "component": "Structured Dispute Intake Extraction",
        "input": {"user_utterance": "untrusted string only"},
        "output_schema": "intake_output.schema.json",
        "unknown_policy": "null; intent unknown; no inferred currency/customer/transaction",
        "relative_dates": "symbolic hints only; trusted as_of/time zone required for later resolution",
        "validation": "JSON schema plus semantic calendar validation; reject extra keys; preserve raw output and validation errors",
        "no_authority": [
            "auth",
            "authorization",
            "ownership",
            "selection truth",
            "policy",
            "fraud verdict",
            "financial action",
            "closure",
        ],
        "comparison": "Same cases, schema, normalization, metrics and retrieval fixtures; freeze prompt/model/version before test",
        "held_out_rule": "No test-driven tuning; changes need new version and a fresh holdout",
        "label_access": "Never send expected_* labels, fixture truth or split labels to the extractor",
    }
    write_json(OUT / "future_llm_evaluation_contract.json", interface)
    manifest_path = OUT / "eval_manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    generated = previous.get(
        "generation_timestamp", datetime.now(timezone.utc).isoformat()
    )
    source_paths = list((ARTIFACTS_DIR / "dispute_case_workflow").glob("*.csv")) + [
        ARTIFACTS_DIR / "dispute_case_workflow/case_evidence_bundles.parquet",
        ARTIFACTS_DIR / "mvp_definition/frozen_mvp_contract.json",
    ]
    manifest = {
        "dataset_version": VERSION,
        "generation_timestamp": generated,
        "number_of_cases": len(cases),
        "language_counts": dict(Counter(c["language"] for c in cases)),
        "source_type_counts": {
            "observed-derived": 0,
            "synthetic/team-generated": len(cases),
        },
        "split_counts": dict(Counter(c["split"] for c in cases)),
        "groups_per_split": {s: len(g) for s, g in groups.items()},
        "split_strategy": "Disjoint customer groups and source transaction fingerprints; deterministic hash ordering, 6 groups per split; NOT a temporal holdout",
        "template_limitation": "Shared authored scenario families; generated benchmark, not independent real-language generalization",
        "gold_provenance": "Expected values authored from scenario specification, never parser predictions or complaint links",
        "annotation_review": "Human ES/PT linguistic review pending",
        "code_reference": lock["code_sha256"],
        "python": previous.get("python", platform.python_version()),
        "git_commit": previous.get("git_commit")
        or subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_artifact_signatures": {
            str(p.relative_to(ROOT)): digest(p) for p in source_paths
        },
        "frozen_file_signatures": {
            p.name: digest(p)
            for p in OUT.glob("*.jsonl")
            if "predictions" not in p.name
        },
        "test_frozen_before_scoring": True,
        "baseline_lock_sha256": digest(OUT / "baseline_lock.json"),
    }
    freeze(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    return result


def report(result):
    from src.data.workflows.dispute_reporting import table

    scores = []
    for key, r in result["extraction"].items():
        scores.append(
            {
                "population": key,
                "n": r["cases"],
                "full_schema_EM": r["full_schema_exact_match"],
                "schema_valid": r["schema_valid_rate"],
                "hallucinated_fields": r["hallucinated_fields"],
                "clarify_accuracy": r["should_clarify_accuracy"],
                "missing_required_EM": r["missing_required_clue_set_exact_match"],
            }
        )
    text = (
        """# Baseline & Evaluation Dataset

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

"""
        + table(scores)
        + """

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
"""
    )
    (REPORTS_DIR / "BASELINE_AND_EVALUATION_FINDINGS.md").write_text(
        text, encoding="utf-8"
    )
    (OUT / "README.md").write_text(
        "# Offline evaluation v1\n\n"
        "See ../../reports/BASELINE_AND_EVALUATION_FINDINGS.md. All generated utterances are synthetic/team-generated.\n\n"
        + "\n".join(
            "- " + p.name
            for p in sorted(OUT.iterdir())
            if p.suffix in {".json", ".jsonl"}
        )
        + "\n"
    )
    return text
