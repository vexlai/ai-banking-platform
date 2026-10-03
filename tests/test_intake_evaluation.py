"""Independent unit specifications; not tests tuned to held-out utterance results."""
import unittest
import tempfile
from pathlib import Path
from copy import deepcopy
from src.evaluation.baseline_intake_parser import extract,parse_amount,schema_valid,intake_flags
from src.evaluation.metrics import retrieve_fixture,extraction_metrics,handoff_score,HANDOFF_FIELDS


class IntakeEvaluationTests(unittest.TestCase):
    def test_frozen_dataset_rejects_silent_replacement(self):
        from src.evaluation.dataset import freeze
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"test.jsonl"
            freeze(target,'{"case_id":"a"}\n')
            freeze(target,'{"case_id":"a"}\n')
            with self.assertRaises(AssertionError):
                freeze(target,'{"case_id":"changed"}\n')
            self.assertEqual(target.read_text(),'{"case_id":"a"}\n')

    def test_spanish_complete_and_unknowns(self):
        r=extract('No reconozco 12,50 USD del 2026-06-10 en comercio "Local".')
        self.assertEqual(r["amount"],"12.50")
        self.assertEqual(r["merchant"],"Local")
        self.assertEqual(r["date_hint"],"2026-06-10")
        self.assertIsNone(r["transaction_id"])
        self.assertFalse(intake_flags(r)["should_clarify"])
        self.assertTrue(schema_valid(r))

    def test_portuguese_relative_not_invented_date(self):
        r=extract("Não reconheço 30 BRL de ontem pelo aplicativo.")
        self.assertEqual(r["intent"],"dispute_intake")
        self.assertEqual(r["date_hint"],"relative:yesterday")
        self.assertEqual(r["channel_hint"],"App")

    def test_contradictions_no_arbitrary_choice(self):
        r=extract("No reconozco 10 USD o 20 EUR, TX-123456789ABC o TX-ABCDEF123456.")
        self.assertIsNone(r["amount"])
        self.assertIsNone(r["currency"])
        self.assertIsNone(r["transaction_id"])
        self.assertTrue(intake_flags(r)["should_clarify"])

    def test_malformed_negative_and_symbol_currency_not_inferred(self):
        for value in ("-10","12..34","1,234","NaN","inf"):
            self.assertIsNone(parse_amount(value))
        self.assertIsNone(extract("No reconozco $25")["currency"])
        self.assertIsNone(extract("No reconozco 25 XYZ")["currency"])

    def test_invalid_dates_extra_keys_and_fixture_id(self):
        r=extract("No reconozco TX-123456789ABC del 2026-02-30")
        self.assertIsNone(r["date_hint"])
        self.assertEqual(r["transaction_id"],"TX-123456789ABC")
        self.assertFalse(schema_valid({**r,"authorization":True}))
        self.assertFalse(schema_valid({**r,"date_hint":"20260228"}))
        self.assertFalse(schema_valid({**r,"date_hint":"2026-02-30"}))

    def test_protected_requests_are_not_financial_actions(self):
        for text in ("Reembolsa 10 USD","Marca como fraude","Cierra la disputa"):
            self.assertEqual(extract(text)["intent"],"unsupported_action")
            self.assertTrue(intake_flags(extract(text))["should_handoff"])

    def test_metric_hallucination_and_wrong_value_denominators(self):
        gold=extract("No reconozco un cargo")
        case={**{"expected_"+k:v for k,v in gold.items()},"expected_missing_fields":intake_flags(gold)["missing_fields"],
              "expected_should_clarify":True,"expected_should_handoff":False}
        bad={**gold,"currency":"USD"}
        m=extraction_metrics([case],[bad])
        self.assertEqual(m["hallucinated_fields"],1)
        self.assertEqual(m["per_field"]["currency"]["false_positive"],1)
        self.assertEqual(m["full_schema_exact_match"],0)

    def test_retrieval_guards_boundaries_and_ambiguity(self):
        r={"auth_status":"valid","principal":"p","as_of_time":"2026-06-17T12:00:00","lookback_days":1}
        tx=[{"transaction_id":"a","owner":"p","timestamp":"2026-06-16T12:00:00","amount":"10.00","currency":"USD"},
            {"transaction_id":"b","owner":"p","timestamp":"2026-06-17T12:00:00","amount":"10.00","currency":"USD"},
            {"transaction_id":"future","owner":"p","timestamp":"2026-06-17T12:00:01","amount":"10.00","currency":"USD"},
            {"transaction_id":"foreign","owner":"q","timestamp":"2026-06-17T12:00:00","amount":"10.00","currency":"USD"}]
        self.assertEqual(retrieve_fixture(r,tx),["a","b"])
        self.assertEqual(retrieve_fixture({**r,"auth_status":"expired"},tx),[])
        self.assertEqual(retrieve_fixture({**r,"transaction_id":"foreign"},tx),[])
        self.assertEqual(retrieve_fixture({**r,"currency":"COP"},tx),[])

    def test_handoff_invented_reference_and_value(self):
        p={k:[] for k in HANDOFF_FIELDS}
        p["verified_facts"]=[{"field":"amount","value":"99","evidence_id":"e"}]
        p["evidence_references"]=["bad"]
        result=handoff_score(p,{"e":{"amount":"10"}})
        self.assertEqual(result["unsupported_claim_count"],1)
        self.assertEqual(result["invalid_reference_count"],1)


if __name__=="__main__":
    unittest.main()
