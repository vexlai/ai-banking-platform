"""Casos pequeños que cubren riesgos de ingestión y conteo."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack

from src.data_utils import connect, load
from src.profiling_utils import basic_profile, detailed_column, profiling


class ProfilingTests(unittest.TestCase):
    @patch("src.profiling_utils.save_json")
    def test_multiline_ids_nulls_and_invalid_dates(self, _save_json):
        with tempfile.TemporaryDirectory() as directory, connect() as con:
            path = Path(directory) / "input.csv"
            path.write_text('\ufeffrecord_id,event_date,amount,note\n001,2024-02-29,1,"line one\nline two"\n002,2024-02-30,2,\n002,,100,  \n', encoding="utf-8")
            columns = load(con, [path])
            self.assertEqual(columns, ["record_id", "event_date", "amount", "note"])
            self.assertEqual(con.execute("SELECT record_id FROM current_data ORDER BY record_id LIMIT 1").fetchone()[0], "001")
            bases = {p["column"]: p for p in basic_profile(con, "test", columns, 3)}
            self.assertEqual(bases["record_id"]["cardinality"], 2)
            self.assertFalse(bases["record_id"]["unique_non_null"])
            self.assertEqual(bases["note"]["nulls"], 1)
            self.assertEqual(bases["note"]["whitespace_only"], 1)
            dates = detailed_column(con, bases["event_date"])
            self.assertEqual(dates["invalid_dates"], 1)
            self.assertEqual(dates["nulls"], 1)
            numeric = detailed_column(con, bases["amount"])
            self.assertEqual(numeric["minimum"], 1)
            self.assertEqual(numeric["maximum"], 100)

    def test_full_profile_with_orphans_duplicates_and_composite_key(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            data = root / "dataset"
            data.mkdir()
            (data / "branches.csv").write_text("branch_id,branch_name\nb1,Alpha\nb1,Beta\n")
            (data / "customers.csv").write_text("customer_id,registration_branch_id,amount,registration_date\nc1,b1,1,2024-02-29\nc2,b2,100,2024-02-30\nc3,,3,\n")
            (data / "daily_exchange_rates.csv").write_text("date,source_currency,target_currency,exchange_rate\n2024-01-01,EUR,USD,1.1\n2024-01-01,EUR,USD,1.1\n")
            for name, value in {
                "src.data_utils.ROOT": root, "src.data_utils.DATA": data,
                "src.data_utils.REPORTS": root / "reports",
                "src.profiling_utils.ROOT": root,
                "src.profiling_utils.REPORTS": root / "reports",
            }.items():
                stack.enter_context(patch(name, value))
            columns, datasets, keys, relations = profiling()
            relation = next(r for r in relations if r["source_column"] == "registration_branch_id")
            self.assertEqual((relation["matched_rows"], relation["orphan_rows"], relation["null_rows"]), (1, 1, 1))
            self.assertEqual(relation["parent_duplicate_excess"], 1)
            self.assertEqual(next(d for d in datasets if d["dataset"] == "daily_exchange_rates")["duplicate_rows_excess"], 1)
            self.assertFalse(next(k for k in keys if k["scope"] == "composite_tested")["candidate_key"])
            self.assertEqual(next(c for c in columns if c["column"] == "registration_date")["invalid_dates"], 1)


if __name__ == "__main__":
    unittest.main()
