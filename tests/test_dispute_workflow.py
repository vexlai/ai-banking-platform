"""Small fixtures for retrieval boundaries, empty sets, currency and strict event-time history."""
import tempfile
import csv
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb
from src import dispute_workflow_data as data
from src import dispute_workflow_context as context


def fixture(con):
    con.execute("""CREATE TABLE co AS SELECT * FROM (VALUES
      ('c1','u1',TIMESTAMP '2024-04-15 12:00:00','Claim','Transactions','Cargo no reconocido',
       100::DECIMAL(24,6),'USD',false,'Open','High','Phone','False'),
      ('c2','u1',TIMESTAMP '2024-04-15 12:00:00','Complaint','Transactions',NULL,
       NULL,NULL,false,'Open','High','Phone','False'),
      ('c3','u3',TIMESTAMP '2024-04-15 12:00:00','Claim','Transactions','Cargo no reconocido',
       100,'USD',false,'Open','High','Phone','False'),
      ('c4','u1',TIMESTAMP '2024-04-15 12:00:00','Claim','Fees','Cobro indebido',
       100,'MXN',false,'Open','High','Phone','False')
      ) t(complaint_id,customer_id,complaint_time,case_type,category,subcategory,claim_amount,
        currency,resolution_present,status,priority,reception_channel,is_repeat_complainer)""")
    con.execute("""CREATE TABLE tx AS SELECT transaction_id,customer_id,tx_time,amount,currency,
      'App' AS channel,'Payment' AS transaction_type,NULL::VARCHAR AS merchant_name,
      'Approved' AS transaction_status,false AS fraud_recorded FROM (VALUES
      ('prior','u1',TIMESTAMP '2024-04-14 12:00:00',100::DECIMAL(24,6),'USD'),
      ('future','u1',TIMESTAMP '2024-04-16 12:00:00',100,'USD'),
      ('other_currency','u1',TIMESTAMP '2024-04-14 12:00:00',10000,'EUR'),
      ('same_time','u1',TIMESTAMP '2024-04-15 12:00:00',100,'USD'),
      ('same_time_peer','u1',TIMESTAMP '2024-04-15 12:00:00',100,'USD'),
      ('foreign_customer','u2',TIMESTAMP '2024-04-14 12:00:00',100,'USD'),
      ('older','u1',TIMESTAMP '2024-04-13 12:00:00',90,'USD'),
      ('outside_90d','u1',TIMESTAMP '2024-01-01 12:00:00',800,'USD')
      ) t(transaction_id,customer_id,tx_time,amount,currency)""")


class WorkflowDiscoveryTests(unittest.TestCase):
    def test_currency_eligibility_empty_sets_and_symmetric_boundaries(self):
        with duckdb.connect() as con,tempfile.TemporaryDirectory() as directory:
            fixture(con)
            with patch.object(data,"ART",Path(directory)):
                data.cohorts(con,{})
                data.retrieval(con,{})
                with (Path(directory)/"candidate_currency_support.csv").open() as f:
                    support=list(csv.DictReader(f))
                self.assertTrue(all(r["support"]=="missing_claim_currency" for r in support if r["currency"]==""))
            self.assertEqual(con.execute("SELECT count(*) FROM candidate_pairs WHERE transaction_id='foreign_customer'").fetchone()[0],0)
            r=con.execute("""SELECT temporal_count,exact_count,prior_exact_count FROM complaint_counts
              WHERE complaint_id='c1' AND days=1""").fetchone()
            self.assertEqual(r,(5,4,3))
            self.assertEqual(con.execute("""SELECT temporal_count,currency_count,exact_count,prior_count
              FROM complaint_counts WHERE complaint_id='c3' AND days=1""").fetchone(),(0,0,0,0))
            self.assertFalse(con.execute("""SELECT eligible FROM rule_counts
              WHERE complaint_id='c2' AND days=1 AND rule='exact'""").fetchone()[0])
            self.assertEqual(con.execute("""SELECT exact_count FROM complaint_counts
              WHERE complaint_id='c4' AND days=30""").fetchone()[0],0)
            self.assertEqual(con.execute("""SELECT count(*) FROM candidate_pairs
              WHERE same_currency IS NOT TRUE AND amount_difference IS NOT NULL""").fetchone()[0],0)

    def test_strict_prior_time_currency_and_unknown_merchant(self):
        with duckdb.connect() as con,tempfile.TemporaryDirectory() as directory:
            fixture(con)
            con.execute("ALTER TABLE tx ADD COLUMN is_fraud VARCHAR DEFAULT 'False'")
            with patch.object(data,"ART",Path(directory)),patch.object(context,"ART",Path(directory)):
                data.cohorts(con,{})
                context.behavior(con)
            r=con.execute("""SELECT customer_transaction_count_prior_7d,median_amount_prior_30d,
              same_merchant_count_prior_90d FROM behavior_features WHERE transaction_id='same_time'""").fetchone()
            self.assertEqual(r[0],3)
            self.assertEqual(float(r[1]),95.0)
            self.assertIsNone(r[2])
            self.assertEqual(con.execute("""SELECT count(*) FROM prior_pairs WHERE transaction_id='same_time'
              AND historical_id IN ('future','same_time','same_time_peer','outside_90d')""").fetchone()[0],0)


if __name__=="__main__":
    unittest.main()
