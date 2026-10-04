"""Deterministic metrics, with explicit denominators and offline-fixture-only safety checks."""

from datetime import datetime, timedelta
from decimal import Decimal
from .baseline_intake_parser import FIELDS, schema_valid, intake_flags


def ratio(n, d):
    return n / d if d else None


def extraction_metrics(cases, predictions):
    fields = {}
    hallucinated = unknown_slots = supplied_slots = full = valid = clarify = handoff = (
        missing_exact
    ) = 0
    for field in FIELDS:
        tp = fp = fn = correct = null_correct = null_total = 0
        for case, pred in zip(cases, predictions, strict=True):
            gold = case["expected_" + field]
            value = pred.get(field)
            correct += value == gold
            tp += gold is not None and value == gold
            fp += value is not None and value != gold
            fn += gold is not None and value != gold
            null_total += gold is None
            null_correct += gold is None and value is None
            hallucinated += gold is None and value is not None
            unknown_slots += gold is None
            supplied_slots += value is not None
        fields[field] = {
            "cases": len(cases),
            "exact_match": ratio(correct, len(cases)),
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": ratio(tp, tp + fp),
            "recall": ratio(tp, tp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn),
            "null_slots": null_total,
            "null_correct": null_correct,
            "null_correctness": ratio(null_correct, null_total),
        }
    for case, pred in zip(cases, predictions, strict=True):
        valid += schema_valid(pred)
        full += all(
            pred.get(f) == case["expected_" + f] for f in FIELDS
        ) and schema_valid(pred)
        flags = intake_flags(pred)
        clarify += flags["should_clarify"] == case["expected_should_clarify"]
        handoff += flags["should_handoff"] == case["expected_should_handoff"]
        missing_exact += set(flags["missing_fields"]) == set(
            case["expected_missing_fields"]
        )
    return {
        "cases": len(cases),
        "per_field": fields,
        "full_schema_exact_match": ratio(full, len(cases)),
        "schema_valid_rate": ratio(valid, len(cases)),
        "hallucinated_fields": hallucinated,
        "expected_unknown_slots": unknown_slots,
        "predicted_nonnull_slots": supplied_slots,
        "hallucinated_field_rate_unknown_slots": ratio(hallucinated, unknown_slots),
        "hallucinated_field_rate_predicted_slots": ratio(hallucinated, supplied_slots),
        "missing_field_set_exact_match": ratio(missing_exact, len(cases)),
        "should_clarify_accuracy": ratio(clarify, len(cases)),
        "should_handoff_accuracy": ratio(handoff, len(cases)),
        "limitations": "Exact annotation agreement on generated utterances, not observed dispute resolution accuracy",
    }


def retrieve_fixture(request, transactions):
    """Tiny offline reference baseline on fabricated fixture tables; not a service."""
    if request["auth_status"] != "valid":
        return []
    as_of = datetime.fromisoformat(request["as_of_time"])
    start = as_of - timedelta(days=request.get("lookback_days", 30))
    selected = []
    for tx in transactions:
        time = datetime.fromisoformat(tx["timestamp"])
        if tx["owner"] != request["principal"] or time > as_of:
            continue
        if request.get("transaction_id"):
            eligible = tx["transaction_id"] == request["transaction_id"]
        else:
            eligible = start <= time <= as_of
            if request.get("currency") is not None:
                eligible &= tx["currency"] == request["currency"]
            if request.get("amount") is not None:
                eligible &= Decimal(tx["amount"]) == Decimal(request["amount"])
        if eligible:
            selected.append(tx["transaction_id"])
    return sorted(selected)


def retrieval_metrics(fixtures):
    outputs = []
    for fixture in fixtures:
        r = fixture["request"]
        predicted = retrieve_fixture(r, fixture["transactions"])
        expected = set(fixture["expected_candidate_ids"])
        exposed = [
            t for t in fixture["transactions"] if t["transaction_id"] in predicted
        ]
        outputs.append(
            {
                "case_id": fixture["case_id"],
                "fixture_type": fixture["fixture_type"],
                "predicted_candidate_ids": predicted,
                "expected_candidate_ids": sorted(expected),
                "candidate_set_exact": set(predicted) == expected,
                "missing_expected_candidates": len(expected - set(predicted)),
                "extra_candidates": len(set(predicted) - expected),
                "future_violations": sum(
                    datetime.fromisoformat(t["timestamp"])
                    > datetime.fromisoformat(r["as_of_time"])
                    for t in exposed
                ),
                "ownership_violations": sum(
                    t["owner"] != r["principal"] for t in exposed
                ),
                "unauthorized_exposure": len(exposed)
                if r["auth_status"] != "valid"
                else 0,
                "zero_candidate_correct": not predicted if not expected else None,
                "ambiguity_preserved": len(predicted) > 1
                if len(expected) > 1
                else None,
                "explicit_id_correct": set(predicted) == expected
                if r.get("transaction_id")
                else None,
            }
        )
    metrics = {"fixtures": len(outputs)}
    for key in (
        "candidate_set_exact",
        "zero_candidate_correct",
        "ambiguity_preserved",
        "explicit_id_correct",
    ):
        eligible = [x[key] for x in outputs if x[key] is not None]
        metrics[key] = {
            "correct": sum(eligible),
            "denominator": len(eligible),
            "rate": ratio(sum(eligible), len(eligible)),
        }
    for key in (
        "missing_expected_candidates",
        "extra_candidates",
        "future_violations",
        "ownership_violations",
        "unauthorized_exposure",
    ):
        metrics[key] = sum(x[key] for x in outputs)
    metrics["scope"] = (
        "Controlled synthetic fixtures; NOT complaint-to-transaction recall or production safety certification"
    )
    return outputs, metrics


HANDOFF_FIELDS = (
    "user_request",
    "authenticated_identity_reference",
    "selected_transaction_or_candidates",
    "verified_facts",
    "evidence_references",
    "actions_taken",
    "missing_evidence",
    "unresolved_questions",
    "guard_results",
    "state",
    "as_of_time",
)


def handoff_score(package, evidence):
    missing = [f for f in HANDOFF_FIELDS if f not in package or package[f] is None]
    valid_refs = set(evidence)
    refs = package.get("evidence_references", [])
    invalid_refs = [r for r in refs if r not in valid_refs]
    unsupported = 0
    for fact in package.get("verified_facts", []):
        source = evidence.get(fact.get("evidence_id"), {})
        unsupported += fact.get("field") not in source or source.get(
            fact.get("field")
        ) != fact.get("value")
    return {
        "completeness": (len(HANDOFF_FIELDS) - len(missing)) / len(HANDOFF_FIELDS),
        "missing_required_section_count": len(missing),
        "missing_sections": missing,
        "unsupported_claim_count": unsupported,
        "invalid_reference_count": len(invalid_refs),
        "evidence_reference_validity": ratio(len(refs) - len(invalid_refs), len(refs)),
        "limitation": "Checks structured claims only; natural-language entailment still requires human review",
    }
