"""Scoped discovery data access and candidate retrieval. No verified dispute links."""

import csv
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from src.data.config import ARTIFACTS_DIR, REPORTS, REPORTS_DIR, ROOT
from src.data.data_utils import connect, discover, ident, literal
from src.data.eda.dispute_eda import digest, boolean, present, stats
from src.data.eda.eda_core import CACHE, EXCLUDE, rows

ART = ARTIFACTS_DIR / "dispute_case_workflow"
DOMAINS = (
    "transactions",
    "complaints",
    "call_center_interactions",
    "call_transcripts",
    "digital_events",
)
WINDOWS = (1, 3, 7, 14, 30)
COHORTS = {
    "A": "case_type IN ('Complaint','Claim') AND category='Transactions'",
    "B": "case_type IN ('Complaint','Claim') AND category='Transactions' AND subcategory='Cargo no reconocido'",
    "C": "case_type IN ('Complaint','Claim') AND category='Fees' AND subcategory='Cobro indebido'",
}


def save(name, data):
    data = list(data)
    keys = list(dict.fromkeys(k for r in data for k in r)) or ["no_records"]
    with (ART / name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows(data)
    return data


def query(con, name, sql):
    return save(name, rows(con, sql))


def export(con, name, sql):
    con.execute(
        f"COPY ({sql}) TO {literal(ART / name)} (FORMAT PARQUET,COMPRESSION ZSTD)"
    )


def log(text):
    print(text, flush=True)
    with (ART / "execution.log").open("a") as f:
        f.write(datetime.now().isoformat() + " " + text + "\n")


def raw_relation(manifest, groups, domain):
    columns = next(r["columns"] for r in manifest if r["dataset"] == domain)
    schema = "{" + ",".join(literal(c) + ":'VARCHAR'" for c in columns) + "}"
    paths = "[" + ",".join(literal(p) for p in groups[domain]) + "]"
    return f"""read_csv({paths},columns={schema},auto_detect=false,header=true,
       delim=',',quote='"',escape='"',strict_mode=true,ignore_errors=false,
       null_padding=false,hive_partitioning=false)"""


@contextmanager
def sources():
    ART.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((REPORTS / "source_manifest.json").read_text())
    groups = discover()
    assert {str(p.relative_to(ROOT)) for ps in groups.values() for p in ps} == {
        r["path"] for r in manifest
    }
    before = {
        r["path"]: (
            (ROOT / r["path"]).stat().st_size,
            (ROOT / r["path"]).stat().st_mtime_ns,
        )
        for r in manifest
    }
    protected_paths = [
        ROOT / p
        for p in [
            "notebooks/00_dataset_inventory.ipynb",
            "notebooks/01_ingestion_profiling.ipynb",
            "notebooks/02_eda.ipynb",
            "notebooks/02b_transaction_dispute_eda_addendum.ipynb",
        ]
    ] + [
        REPORTS_DIR / "eda" / "EDA_FINDINGS.md",
        REPORTS_DIR / "EDA_TRANSACTION_DISPUTE_ADDENDUM.md",
        REPORTS / "source_manifest.json",
    ]
    protected_paths += list((ARTIFACTS_DIR / "eda_transaction_dispute").glob("*.csv"))
    protected = {str(p.relative_to(ROOT)): digest(p) for p in protected_paths}
    signature = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    cache = CACHE / "analysis.duckdb"
    cache_hash = digest(cache) if cache.exists() else None
    # The only supplemental raw reads: complaint resolution presence and transcript metadata presence.
    supplements = [
        r for r in manifest if r["dataset"] in ("complaints", "call_transcripts")
    ]
    log(
        f"Validating {len(supplements)} supplemental sources and read-only curated cache"
    )
    for r in supplements:
        assert digest(ROOT / r["path"]) == r["sha256"], r["path"]
    prior = json.loads((REPORTS_DIR / "eda" / "analysis_context.json").read_text())
    context = {
        "execution_timestamp": datetime.now(ZoneInfo("America/Guayaquil")).isoformat(),
        "feature_cutoff_inclusive": prior["feature_cutoff_inclusive"],
        "source_manifest_sha256": signature,
        "inherited_cache_sha256": cache_hash,
        "method": "Exact DuckDB aggregates; no sampling; no raw modification",
        "relationship_class": "INFERRED RELATIONSHIP / HEURISTIC, never ground truth",
        "temporal_policy": "Strict event timestamps; no time zone conversion without semantics. Cutoff inclusive by date.",
        "point_in_time_limit": "Event-time ordered, NOT certified ingestion-time safe: availability/revision timestamps absent.",
        "windows": "Symmetric +/-24*n hours, inclusive; after-complaint candidates retrospective only.",
        "currency_policy": "Exact DECIMAL(24,6); compare only same currency; relative difference / abs(claimed_amount), undefined at zero.",
        "protected_artifacts_sha256": protected,
    }
    with connect() as con:
        con.execute("SET memory_limit='1500MB'")
        con.execute("SET threads=2")
        use_cache = False
        if cache.exists():
            con.execute(f"ATTACH {literal(cache)} AS inherited (READ_ONLY)")
            metadata = dict(
                con.execute(
                    "SELECT dataset,signature FROM inherited.cache_info"
                ).fetchall()
            )
            use_cache = all(
                metadata.get(d, "").split("|")[0] == signature for d in DOMAINS
            )
        for domain in DOMAINS:
            if use_cache:
                con.execute(
                    f"CREATE VIEW {ident(domain)} AS SELECT * FROM inherited.{ident(domain)}"
                )
            else:
                columns = next(r["columns"] for r in manifest if r["dataset"] == domain)
                projection = ",".join(
                    ident(c) for c in columns if c not in EXCLUDE.get(domain, set())
                )
                con.execute(
                    f"CREATE TABLE {ident(domain)} AS SELECT {projection} FROM {raw_relation(manifest, groups, domain)}"
                )
        context["input_mode"] = (
            "read-only curated DuckDB"
            if use_cache
            else "scoped projected strict CSV fallback"
        )
        con.execute(f"""CREATE TABLE complaint_supplement AS
          SELECT complaint_id,{present("resolution")} AS resolution_present
          FROM {raw_relation(manifest, groups, "complaints")}""")
        fields = [
            "detected_keywords",
            "mentioned_entities",
            "detected_intents",
            "main_topics",
        ]
        # Do not materialize or export contents; distinguish absent, blank, empty-container and nonempty.
        expressions = []
        for field in fields:
            c = ident(field)
            expressions += [
                f"{c} IS NOT NULL AS {field}_nonnull",
                f"({present(c)} AND lower(trim({c})) NOT IN ('[]','{{}}','null')) AS {field}_nonempty",
            ]
        con.execute(f"""CREATE TABLE transcript_metadata AS SELECT transcript_id,interaction_id,
          {",".join(expressions)} FROM {raw_relation(manifest, groups, "call_transcripts")}""")
        for table, key, base in [
            ("complaint_supplement", "complaint_id", "complaints"),
            ("transcript_metadata", "transcript_id", "call_transcripts"),
        ]:
            assert con.execute(
                f"SELECT count(*)=count(DISTINCT {key}) FROM {table}"
            ).fetchone()[0]
            assert (
                con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                == con.execute(f"SELECT count(*) FROM {base}").fetchone()[0]
            )
            assert (
                con.execute(
                    f"SELECT count(*) FROM {base} b ANTI JOIN {table} t USING({key})"
                ).fetchone()[0]
                == 0
            )
        cutoff = literal(context["feature_cutoff_inclusive"])
        for table, field in [
            ("transactions", "amount"),
            ("complaints", "claimed_amount"),
        ]:
            invalid = con.execute(f"""SELECT count(*) FROM {table} WHERE {ident(field)} IS NOT NULL
              AND (NOT regexp_full_match({ident(field)},'-?[0-9]+([.][0-9]{{1,6}})?')
                   OR try_cast({ident(field)} AS DECIMAL(24,6)) IS NULL)""").fetchone()[
                0
            ]
            assert invalid == 0, (table, "monetary precision requires explicit review")
        con.execute(f"""CREATE TABLE tx AS SELECT * EXCLUDE(transaction_date,amount),
          transaction_date::TIMESTAMP AS tx_time,amount::DECIMAL(24,6) AS amount,
          {boolean("is_fraud")} AS fraud_recorded FROM transactions
          WHERE transaction_date::DATE<=DATE {cutoff}""")
        con.execute(f"""CREATE TABLE co AS SELECT c.* EXCLUDE(creation_date,claimed_amount),
          creation_date::TIMESTAMP AS complaint_time,claimed_amount::DECIMAL(24,6) AS claim_amount,
          s.resolution_present FROM complaints c JOIN complaint_supplement s USING(complaint_id)
          WHERE creation_date::DATE<=DATE {cutoff}""")
        con.execute(f"""CREATE TABLE calls AS SELECT * EXCLUDE(interaction_date),
          interaction_date::TIMESTAMP AS call_time,{boolean("was_resolved")} AS resolved_recorded,
          {boolean("was_escalated")} AS escalated_recorded
          FROM call_center_interactions WHERE interaction_date::DATE<=DATE {cutoff}""")
        audit = []
        for domain, field in [
            ("transactions", "transaction_date"),
            ("complaints", "creation_date"),
            ("call_center_interactions", "interaction_date"),
            ("digital_events", "event_date"),
        ]:
            audit += rows(
                con,
                f"""SELECT '{domain}' AS dataset,count(*) AS full_rows,
              count_if(try_cast({field} AS DATE)<=DATE {cutoff}) AS cutoff_rows,
              count_if(try_cast({field} AS DATE)>DATE {cutoff}) AS after_cutoff_rows,
              count_if(try_cast({field} AS TIMESTAMP) IS NULL) AS invalid_or_missing_timestamp
              FROM {domain}""",
            )
        save("population_cutoff_audit.csv", audit)
        context["transaction_min"], context["transaction_max"] = [
            str(x)
            for x in con.execute("SELECT min(tx_time),max(tx_time) FROM tx").fetchone()
        ]
        (ART / "analysis_context.json").write_text(json.dumps(context, indent=2) + "\n")
        yield con, context
        log("Verifying source files and prior results are unchanged")
        assert before == {
            r["path"]: (
                (ROOT / r["path"]).stat().st_size,
                (ROOT / r["path"]).stat().st_mtime_ns,
            )
            for r in manifest
        }
        for r in supplements:
            assert digest(ROOT / r["path"]) == r["sha256"]
        assert protected == {
            str(p.relative_to(ROOT)): digest(p) for p in protected_paths
        }
        if cache_hash:
            assert digest(cache) == cache_hash
        (ART / "integrity.json").write_text(
            json.dumps(
                {
                    "all_raw_size_mtime_unchanged": len(before),
                    "supplemental_raw_sha256_unchanged": len(supplements),
                    "inherited_cache_sha256_unchanged": bool(cache_hash),
                    "prior_artifacts_sha256_unchanged": len(protected),
                },
                indent=2,
            )
            + "\n"
        )


def cohorts(con, context):
    con.execute(
        "CREATE TABLE membership AS "
        + " UNION ALL ".join(
            f"SELECT '{name}' AS cohort,complaint_id FROM co WHERE {condition}"
            for name, condition in COHORTS.items()
        )
    )
    con.execute(
        "CREATE TABLE cases AS SELECT * FROM co SEMI JOIN membership USING(complaint_id)"
    )
    query(
        con,
        "candidate_dispute_cohorts.csv",
        """SELECT m.cohort,count(*) AS records,
      count(DISTINCT customer_id) AS customers,min(complaint_time) AS date_min,max(complaint_time) AS date_max,
      count(claim_amount) AS claimed_amount_present,100.*count(claim_amount)/count(*) AS claimed_amount_pct,
      count(currency) AS currency_present,100.*count(currency)/count(*) AS currency_pct,
      count_if(claim_amount IS NOT NULL AND currency IS NOT NULL) AS amount_currency_present,
      count_if(resolution_present) AS resolution_present,
      100.*count_if(resolution_present)/count(*) AS resolution_pct
      FROM co JOIN membership m USING(complaint_id) GROUP BY 1 ORDER BY 1""",
    )
    distributions = []
    for field in ("status", "priority", "reception_channel", "is_repeat_complainer"):
        distributions += rows(
            con,
            f"""SELECT cohort,'{field}' AS field,{ident(field)} AS value,
          count(*) AS records,100.*count(*)/sum(count(*)) OVER(PARTITION BY cohort) AS pct_cohort
          FROM co JOIN membership USING(complaint_id) GROUP BY 1,3 ORDER BY 1,3 NULLS LAST""",
        )
    save("candidate_cohort_distributions.csv", distributions)
    query(
        con,
        "candidate_currency_support.csv",
        """WITH transaction_units AS (
      SELECT currency,count(*) AS transaction_records,min(amount) AS transaction_minimum,
        median(amount) AS transaction_median,max(amount) AS transaction_maximum
      FROM tx GROUP BY 1),
      claim_units AS (SELECT cohort,currency,count(*) AS complaints,
        count(claim_amount) AS observed_claim_amounts,min(claim_amount) AS claim_minimum,
        median(claim_amount) AS claim_median,max(claim_amount) AS claim_maximum
        FROM co JOIN membership USING(complaint_id) GROUP BY 1,2)
      SELECT c.*,coalesce(t.transaction_records,0) AS transaction_records_same_currency,
        t.transaction_minimum,t.transaction_median,t.transaction_maximum,
        CASE WHEN c.currency IS NULL THEN 'missing_claim_currency'
          WHEN t.transaction_records IS NULL THEN 'no_transaction_currency'
          WHEN c.claim_maximum<t.transaction_minimum OR c.claim_minimum>t.transaction_maximum
            THEN 'disjoint_observed_amount_ranges'
          ELSE 'overlapping_ranges_not_proof_of_linkage' END AS support
      FROM claim_units c LEFT JOIN transaction_units t USING(currency)
      ORDER BY cohort,currency NULLS LAST""",
    )
    save(
        "candidate_cohort_definitions.csv",
        [
            dict(
                cohort=k,
                sql_predicate=v,
                semantic_strength=s,
                semantic_weakness=w,
                linkage_limitation="Customer only; no verified transaction or origin-interaction link",
                potential_role=role,
                relationship_class="HEURISTIC cohort, not ground truth",
            )
            for (k, v), (s, w, role) in zip(
                COHORTS.items(),
                [
                    (
                        "Explicit transaction category in Claim/Complaint",
                        "Includes unspecified subcategory",
                        "Broad sensitivity population",
                    ),
                    (
                        "Explicit recorded Cargo no reconocido",
                        "Allegation not adjudication; B is subset of A",
                        "Primary discovery scope, subject to evidence and human review",
                    ),
                    (
                        "Explicit recorded Cobro indebido",
                        "Fees may not correspond to an individual transaction",
                        "Separate optional intake lane, not pooled with B",
                    ),
                ],
            )
        ],
    )
    query(
        con,
        "cohort_overlap.csv",
        """SELECT a.cohort AS cohort_left,b.cohort AS cohort_right,
       count(*) AS shared_complaints FROM membership a JOIN membership b USING(complaint_id)
       GROUP BY 1,2 ORDER BY 1,2""",
    )
    # One bounded join, deduplicated complaint population (A already contains B).
    con.execute("""CREATE TABLE candidate_pairs AS SELECT c.complaint_id,t.transaction_id,
      epoch(t.tx_time-c.complaint_time)/3600. AS delta_hours,
      t.tx_time<=c.complaint_time AS before_or_at_complaint,
      t.currency=c.currency AS same_currency,
      CASE WHEN t.currency=c.currency THEN abs(t.amount-c.claim_amount) END AS amount_difference,
      CASE WHEN t.currency=c.currency AND c.claim_amount<>0
        THEN abs(t.amount-c.claim_amount)/abs(c.claim_amount) END AS relative_difference
      FROM cases c JOIN tx t ON t.customer_id=c.customer_id
      AND t.tx_time BETWEEN c.complaint_time-INTERVAL '30 days' AND c.complaint_time+INTERVAL '30 days'""")
    assert con.execute(
        "SELECT count(*)=count(DISTINCT (complaint_id,transaction_id)) FROM candidate_pairs"
    ).fetchone()[0]
    con.execute(
        "CREATE TABLE candidates AS SELECT * FROM tx SEMI JOIN candidate_pairs USING(transaction_id)"
    )
    con.execute("""CREATE TABLE historical_population AS SELECT t.* FROM tx t JOIN
      (SELECT customer_id,max(complaint_time) AS last_complaint FROM cases GROUP BY 1) c
      ON t.customer_id=c.customer_id AND t.tx_time<c.last_complaint""")
    query(
        con,
        "retrieval_population.csv",
        """SELECT
      (SELECT count(*) FROM cases) AS unique_complaints,
      (SELECT count(*) FROM candidate_pairs) AS complaint_candidate_pairs,
      (SELECT count(*) FROM candidates) AS unique_candidate_transactions,
      (SELECT count(*) FROM historical_population) AS same_customer_history_transactions""",
    )
    log("1. Cohorts and +/-30-day candidates built; no relationship declared true")


def retrieval(con, context):
    con.execute(
        "CREATE TABLE windows AS SELECT * FROM (VALUES "
        + ",".join(f"({d})" for d in WINDOWS)
        + ") AS w(days)"
    )
    con.execute("""CREATE TABLE complaint_counts AS
      SELECT c.complaint_id,w.days,c.currency,c.claim_amount,
        c.complaint_time- w.days*INTERVAL '1 day'>=(SELECT min(tx_time) FROM tx)
        AND c.complaint_time+w.days*INTERVAL '1 day'<=(SELECT max(tx_time) FROM tx) AS full_window_observed,
        count(p.transaction_id) AS temporal_count,
        count(*) FILTER(WHERE p.same_currency) AS currency_count,
        count(*) FILTER(WHERE p.amount_difference=0) AS exact_count,
        count(*) FILTER(WHERE p.amount_difference<=1) AS absolute_1_count,
        count(*) FILTER(WHERE p.relative_difference<=.01) AS relative_1pct_count,
        count(*) FILTER(WHERE p.relative_difference<=.05) AS relative_5pct_count,
        count(*) FILTER(WHERE p.before_or_at_complaint) AS prior_count,
        count(*) FILTER(WHERE p.before_or_at_complaint AND p.same_currency) AS prior_currency_count,
        count(*) FILTER(WHERE p.before_or_at_complaint AND p.amount_difference=0) AS prior_exact_count,
        count(*) FILTER(WHERE p.before_or_at_complaint AND p.relative_difference<=.05) AS prior_relative_5pct_count
      FROM cases c CROSS JOIN windows w LEFT JOIN candidate_pairs p
      ON p.complaint_id=c.complaint_id AND abs(p.delta_hours)<=24*w.days
      GROUP BY c.complaint_id,w.days,c.currency,c.claim_amount,c.complaint_time""")
    query(
        con,
        "complaint_transaction_window_summary.csv",
        """SELECT cohort,days,count(*) AS eligible_complaints,
      count_if(temporal_count=0) AS zero_candidates,count_if(temporal_count=1) AS unique_candidate,
      count_if(temporal_count>1) AS multiple_candidates,avg(temporal_count) AS candidate_count_mean,
      median(temporal_count) AS candidate_count_median,quantile_cont(temporal_count,.9) AS candidate_count_p90,
      quantile_cont(temporal_count,.95) AS candidate_count_p95,max(temporal_count) AS candidate_count_max,
      count_if(full_window_observed) AS complete_window_complaints,
      count_if(NOT full_window_observed) AS boundary_censored_complaints
      FROM complaint_counts JOIN membership USING(complaint_id) GROUP BY 1,2 ORDER BY 1,2""",
    )
    con.execute("""CREATE TABLE rule_counts AS SELECT c.*,r.* FROM complaint_counts c,
      LATERAL (VALUES
       ('temporal',true,temporal_count),
       ('same_currency',currency IS NOT NULL,currency_count),
       ('exact',claim_amount IS NOT NULL AND currency IS NOT NULL,exact_count),
       ('absolute_1',claim_amount IS NOT NULL AND currency IS NOT NULL,absolute_1_count),
       ('relative_1pct',claim_amount IS NOT NULL AND currency IS NOT NULL AND claim_amount<>0,relative_1pct_count),
       ('relative_5pct',claim_amount IS NOT NULL AND currency IS NOT NULL AND claim_amount<>0,relative_5pct_count),
       ('prior_temporal',true,prior_count),
       ('prior_currency',currency IS NOT NULL,prior_currency_count),
       ('prior_exact',claim_amount IS NOT NULL AND currency IS NOT NULL,prior_exact_count),
       ('prior_relative_5pct',claim_amount IS NOT NULL AND currency IS NOT NULL AND claim_amount<>0,prior_relative_5pct_count)
      ) AS r(rule,eligible,candidate_count)""")
    query(
        con,
        "candidate_rule_comparison.csv",
        """SELECT cohort,days,currency,rule,
      count(*) AS cohort_currency_complaints,count_if(eligible) AS eligible_complaints,
      count_if(NOT eligible) AS ineligible_complaints,
      count_if(eligible AND candidate_count=0) AS no_candidate,
      count_if(eligible AND candidate_count=1) AS unique_candidate,
      count_if(eligible AND candidate_count>1) AS multiple_candidates,
      median(candidate_count) FILTER(WHERE eligible) AS median_candidate_set_size,
      100.*count_if(eligible AND candidate_count>0)/nullif(count_if(eligible),0) AS candidate_rate_pct,
      100.*count_if(eligible AND candidate_count>1)/nullif(count_if(eligible),0) AS ambiguity_pct_eligible,
      100.*count_if(eligible AND candidate_count>1)/nullif(count_if(eligible AND candidate_count>0),0) AS ambiguity_pct_with_candidates
      FROM rule_counts JOIN membership USING(complaint_id) GROUP BY 1,2,3,4 ORDER BY 1,2,3,4 NULLS LAST""",
    )
    # Same monetary eligibility gives fair rule comparisons without shifting populations.
    query(
        con,
        "candidate_rules_common_eligibility.csv",
        """SELECT cohort,days,currency,rule,
      count(*) AS eligible_complaints,count_if(candidate_count=0) AS no_candidate,
      count_if(candidate_count=1) AS unique_candidate,count_if(candidate_count>1) AS multiple_candidates,
      median(candidate_count) AS median_candidate_set_size
      FROM rule_counts JOIN membership USING(complaint_id)
      WHERE claim_amount IS NOT NULL AND claim_amount<>0 AND currency IS NOT NULL
      GROUP BY 1,2,3,4 ORDER BY 1,2,3,4""",
    )
    query(
        con,
        "amount_currency_candidate_matching.csv",
        """SELECT * FROM
      read_csv_auto("""
        + literal(ART / "candidate_rule_comparison.csv")
        + """,all_varchar=true)
      WHERE rule IN ('exact','absolute_1','relative_1pct','relative_5pct')""",
    )
    # Save per-complaint counts for reproducibility without displaying personal identifiers.
    export(con, "complaint_candidate_counts.parquet", "SELECT * FROM complaint_counts")
    log(
        "2-3,12. Ambiguity, eligibility and per-currency monetary rules; no weights or trained ranking"
    )


def temporal_direction(con):
    query(
        con,
        "temporal_candidate_distribution.csv",
        """WITH directions AS (
      SELECT p.*,c.complaint_time,t.tx_time,
        CASE WHEN t.tx_time::DATE<c.complaint_time::DATE THEN 'calendar_before'
             WHEN t.tx_time::DATE=c.complaint_time::DATE THEN 'calendar_same_day'
             ELSE 'calendar_after' END AS calendar_direction,
        CASE WHEN delta_hours=0 THEN 'same_timestamp'
             WHEN delta_hours>0 THEN 'after_complaint_up_to_30d'
             WHEN delta_hours>=-24 THEN 'before_0_1d'
             WHEN delta_hours>=-72 THEN 'before_1_3d'
             WHEN delta_hours>=-168 THEN 'before_3_7d'
             WHEN delta_hours>=-336 THEN 'before_7_14d'
             ELSE 'before_14_30d' END AS elapsed_direction
      FROM candidate_pairs p JOIN cases c USING(complaint_id) JOIN candidates t USING(transaction_id))
      SELECT cohort,calendar_direction,elapsed_direction,count(*) AS candidate_pairs,
        count(DISTINCT complaint_id) AS complaints_with_candidates,
        100.*count(*)/sum(count(*)) OVER(PARTITION BY cohort) AS pct_cohort_candidate_pairs
      FROM directions JOIN membership USING(complaint_id) GROUP BY 1,2,3 ORDER BY 1,2,3""",
    )
    log(
        "4. Temporal direction by calendar day and elapsed time; non-causal association"
    )
