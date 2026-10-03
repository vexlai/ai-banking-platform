"""Small synthetic edge cases; no changes to real analytical artifacts."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb
from src import dispute_eda as eda


class AddendumTests(unittest.TestCase):
    def test_validity_keeps_null_blank_invalid_and_range_failures_separate(self):
        with duckdb.connect() as con, tempfile.TemporaryDirectory() as directory:
            con.execute("""CREATE TABLE demo(amount VARCHAR, latitude VARCHAR, is_fraud VARCHAR)""")
            con.executemany("INSERT INTO demo VALUES (?,?,?)",
                [(None,None,None), (" ","91","unknown"), ("10","-90"," true "),
                 ("NaN","0","false"), ("Infinity","bad","1"), ("-2","90","FALSE")])
            with patch.object(eda, "ART", Path(directory)):
                result = eda.coverage(con,"demo",["amount","latitude","is_fraud"],[],"coverage.csv")
            found = {r["field"]:r for r in result}
            self.assertEqual(found["amount"]["valid_count"],2)
            self.assertEqual(found["amount"]["null_count"],1)
            self.assertEqual(found["amount"]["blank_count"],1)
            self.assertEqual(found["amount"]["invalid_nonnull_count"],3)
            self.assertEqual(found["latitude"]["valid_count"],3)
            self.assertEqual(found["is_fraud"]["valid_count"],3)

    def test_fixed_bucket_boundaries_and_missing_scores_conserve_population(self):
        with duckdb.connect() as con, tempfile.TemporaryDirectory() as directory:
            con.execute("""CREATE TABLE transactions(fraud_score VARCHAR,is_fraud VARCHAR,
              transaction_status VARCHAR,channel VARCHAR,transaction_type VARCHAR)""")
            values = ["0","10","20","30","50","75","100",None,"NaN","-1","101"]
            con.executemany("INSERT INTO transactions VALUES (?,?,?,?,?)",
                            [(v,"True","Approved","App","Payment") for v in values])
            con.execute(f"""CREATE VIEW tx AS SELECT *,
              {eda.boolean('is_fraud')} AS fraud_label,'True' AS label_state,
              CASE WHEN {eda.finite('fraud_score')} THEN fraud_score::DOUBLE END AS score
              FROM transactions""")
            with patch.object(eda, "ART", Path(directory)):
                eda.fraud_scores(con)
                with (Path(directory)/"fraud_score_buckets.csv").open() as f:
                    buckets = list(csv.DictReader(f))
            found = {r["score_bucket"]:int(r["transaction_count"]) for r in buckets}
            self.assertEqual(sum(found.values()),len(values))
            self.assertEqual(found["06 [75,100]"],2)
            for name in ("07 NULL","08 INVALID_NONFINITE","09 BELOW_0","10 ABOVE_100"):
                self.assertEqual(found[name],1)

    def test_unknown_currency_is_counted_but_never_pooled_in_amount_quantiles(self):
        with duckdb.connect() as con, tempfile.TemporaryDirectory() as directory:
            con.execute("""CREATE TABLE co(case_type VARCHAR,category VARCHAR,subcategory VARCHAR,
              claimed_amount VARCHAR,currency VARCHAR)""")
            con.executemany("INSERT INTO co VALUES (?,?,?,?,?)", [
                ("Claim","Transactions","Cargo no reconocido","10","USD"),
                ("Claim","Transactions",None,"1000","COP"),
                ("Claim","Transactions",None,"999999",None),
                ("Request","Fees",None,None,"USD"),
            ])
            with patch.object(eda, "ART", Path(directory)):
                eda.claimed_amount(con)
                with (Path(directory)/"claimed_amount_by_currency.csv").open() as f:
                    distributions = list(csv.DictReader(f))
                with (Path(directory)/"claimed_amount_checks_overall.csv").open() as f:
                    checks = next(csv.DictReader(f))
            self.assertEqual({r["currency"] for r in distributions},{"USD","COP"})
            self.assertEqual({r["currency"]:float(r["median"]) for r in distributions},
                             {"USD":10.0,"COP":1000.0})
            self.assertEqual(int(checks["amount_without_currency"]),1)
            self.assertEqual(int(checks["currency_without_amount"]),1)


if __name__ == "__main__":
    unittest.main()
