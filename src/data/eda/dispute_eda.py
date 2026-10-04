"""Small, read-only EDA addendum; no matching, models, thresholds or agent logic."""

import csv
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import duckdb
from src.data.config import ROOT
from src.data.data_utils import connect, discover, ident, literal, load
from src.data.eda.eda_core import CACHE, rows

ART = ROOT / "artifacts/eda_transaction_dispute"
REPORT = ROOT / "reports/EDA_TRANSACTION_DISPUTE_ADDENDUM.md"
USED = ("transactions", "complaints", "call_center_interactions")
EVIDENCE_FIELDS = [
    "transaction_id",
    "transaction_date",
    "product_id",
    "customer_id",
    "transaction_type",
    "transaction_category",
    "amount",
    "currency",
    "amount_usd",
    "channel",
    "branch_id",
    "merchant_name",
    "merchant_category",
    "transaction_country",
    "transaction_city",
    "transaction_status",
    "response_code",
    "is_fraud",
    "fraud_score",
    "latitude",
    "longitude",
]
REFERENCE_FILES = [
    "notebooks/02_eda.ipynb",
    "reports/eda/EDA_FINDINGS.md",
    "reports/eda/analysis_context.json",
    "reports/eda/semantic_validation.csv",
    "reports/eda/transcript_coverage.csv",
    "reports/eda/survey_coverage.csv",
    "reports/profiling/source_manifest.json",
]


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def save(name, data, fields=None):
    data = list(data)
    fields = fields or list(dict.fromkeys(k for r in data for k in r))
    with (ART / name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=fields or ["no_records"], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(data)
    return data


def query(con, name, sql):
    return save(name, rows(con, sql))


def present(col):
    return f"({col} IS NOT NULL AND trim({col})<>'')"


def finite(col):
    return f"(try_cast({col} AS DOUBLE) IS NOT NULL AND isfinite(try_cast({col} AS DOUBLE)))"


def boolean(col):
    return f"CASE lower(trim({col})) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END"


def stats(expr):
    return f"""avg({expr}) AS mean,median({expr}) AS median,
      quantile_cont({expr},.75) AS p75,quantile_cont({expr},.90) AS p90,
      quantile_cont({expr},.95) AS p95,quantile_cont({expr},.99) AS p99,
      min({expr}) AS minimum,max({expr}) AS maximum"""


def log(text):
    stamp = datetime.now(ZoneInfo("America/Guayaquil")).isoformat()
    print(text, flush=True)
    with (ART / "execution.log").open("a") as f:
        f.write(stamp + " " + text + "\n")


@contextmanager
def sources():
    """Reuse verified EDA projections; fallback reads only the three required domains."""
    ART.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((ROOT / "reports/profiling/source_manifest.json").read_text())
    groups = discover()
    assert {str(p.relative_to(ROOT)) for paths in groups.values() for p in paths} == {
        r["path"] for r in baseline
    }
    all_stats = {r["path"]: (ROOT / r["path"]).stat() for r in baseline}
    protected = {p: digest(ROOT / p) for p in REFERENCE_FILES}
    selected = [r for r in baseline if r["dataset"] in USED]
    log(
        f"Verificando SHA-256 de {len(selected)} fuentes de los tres dominios utilizados"
    )
    for r in selected:
        assert digest(ROOT / r["path"]) == r["sha256"], r["path"]
    signature = hashlib.sha256(
        json.dumps(baseline, sort_keys=True).encode()
    ).hexdigest()
    prior = json.loads((ROOT / "reports/eda/analysis_context.json").read_text())
    context = {
        "execution_started": datetime.now(ZoneInfo("America/Guayaquil")).isoformat(),
        "feature_cutoff_inclusive": prior["feature_cutoff_inclusive"],
        "primary_population": "Full observed extract; row dates beyond the inherited cutoff are counted separately.",
        "availability_warning": "Labels and snapshot outcomes have no known availability timestamp; a row before cutoff does not prove its label was available.",
        "source_manifest_sha256": signature,
        "source_files_sha256_checked": len(selected),
        "reference_files_sha256": protected,
        "fraud_rate_denominator": "valid boolean labels in the indicated population; rate is a fraction, *_pct is percent.",
        "coverage_denominator": "all rows of the indicated dataset or explicit group, including nulls.",
        "potential_taxonomy": "Descriptive annotations on observed categories; not a final cohort.",
    }
    cache = CACHE / "analysis.duckdb"
    resource = None
    con = None
    try:
        use_cache = False
        if cache.exists():
            con = duckdb.connect(str(cache), read_only=True)
            metadata = dict(
                con.execute("SELECT dataset,signature FROM cache_info").fetchall()
            )
            use_cache = all(
                metadata.get(ds, "").split("|")[0] == signature for ds in USED
            )
            if not use_cache:
                con.close()
                con = None
        if not use_cache:
            resource = connect()
            con = resource.__enter__()
            for ds in USED:
                log("Fallback de ingesta estricta, solo dominio requerido: " + ds)
                load(con, groups[ds])
                con.execute(f"ALTER TABLE current_data RENAME TO {ident(ds)}")
        con.execute("SET memory_limit='1500MB'")
        con.execute("SET threads=2")
        con.execute("SET preserve_insertion_order=false")
        with (ROOT / "reports/profiling/datasets.csv").open() as f:
            inventory = {r["dataset"]: int(r["rows"]) for r in csv.DictReader(f)}
        for ds in USED:
            assert (
                con.execute(f"SELECT count(*) FROM {ident(ds)}").fetchone()[0]
                == inventory[ds]
            )
        complaint_cols = {r[0] for r in con.execute("DESCRIBE complaints").fetchall()}
        if "resolution" not in complaint_cols:
            log(
                "Recuperando únicamente complaint_id/resolution: columna excluida de la caché del EDA general"
            )
            cols = next(r["columns"] for r in selected if r["dataset"] == "complaints")
            schema = "{" + ",".join(literal(c) + ":'VARCHAR'" for c in cols) + "}"
            paths = "[" + ",".join(literal(p) for p in groups["complaints"]) + "]"
            con.execute(f"""CREATE TEMP TABLE resolution_source AS SELECT complaint_id,resolution
                FROM read_csv({paths},columns={schema},auto_detect=false,header=true,
                delim=',',quote='"',escape='"',hive_partitioning=false,strict_mode=true,
                ignore_errors=false,null_padding=false)""")
            assert con.execute(
                "SELECT count(*)=count(DISTINCT complaint_id) FROM resolution_source"
            ).fetchone()[0]
            assert (
                con.execute("SELECT count(*) FROM resolution_source").fetchone()[0]
                == inventory["complaints"]
            )
            assert (
                con.execute(
                    "SELECT count(*) FROM complaints c ANTI JOIN resolution_source r USING(complaint_id)"
                ).fetchone()[0]
                == 0
            )
            con.execute(
                "CREATE TEMP VIEW co AS SELECT c.*,r.resolution FROM complaints c LEFT JOIN resolution_source r USING(complaint_id)"
            )
        else:
            con.execute("CREATE TEMP VIEW co AS SELECT * FROM complaints")
        assert (
            con.execute("SELECT count(*) FROM co").fetchone()[0]
            == inventory["complaints"]
        )
        con.execute(f"""CREATE TEMP VIEW tx AS SELECT *,{boolean("is_fraud")} AS fraud_label,
          CASE WHEN {finite("fraud_score")} THEN fraud_score::DOUBLE END AS score,
          CASE WHEN is_fraud IS NULL THEN 'NULL' WHEN {boolean("is_fraud")} IS NULL THEN 'INVALID'
            WHEN {boolean("is_fraud")} THEN 'True' ELSE 'False' END AS label_state FROM transactions""")
        context["input_mode"] = (
            "read-only EDA DuckDB + missing resolution column"
            if use_cache
            else "scoped strict CSV fallback"
        )
        (ART / "analysis_context.json").write_text(
            json.dumps(context, indent=2, ensure_ascii=False) + "\n"
        )
        query(
            con,
            "population_cutoff_audit.csv",
            f"""SELECT 'transactions' AS dataset,count(*) AS records,
          count_if(transaction_date::DATE>DATE {literal(prior["feature_cutoff_inclusive"])}) AS after_cutoff
          FROM tx UNION ALL SELECT 'complaints',count(*),
          count_if(creation_date::DATE>DATE {literal(prior["feature_cutoff_inclusive"])}) FROM co
          UNION ALL SELECT 'call_center_interactions',count(*),
          count_if(interaction_date::DATE>DATE {literal(prior["feature_cutoff_inclusive"])}) FROM call_center_interactions""",
        )
        yield con, context
        log("Verificación final de fuentes utilizadas y artefactos del EDA general")
        for r in selected:
            assert digest(ROOT / r["path"]) == r["sha256"], r["path"]
        for p, old in all_stats.items():
            new = (ROOT / p).stat()
            assert (old.st_size, old.st_mtime_ns) == (new.st_size, new.st_mtime_ns), p
        assert protected == {p: digest(ROOT / p) for p in REFERENCE_FILES}
        (ART / "integrity.json").write_text(
            json.dumps(
                {
                    "used_source_files_sha256_unchanged": len(selected),
                    "all_raw_files_size_mtime_unchanged": len(all_stats),
                    "general_eda_reference_artifacts_sha256_unchanged": True,
                    "completed_at": datetime.now(
                        ZoneInfo("America/Guayaquil")
                    ).isoformat(),
                },
                indent=2,
            )
            + "\n"
        )
    finally:
        if resource:
            resource.__exit__(None, None, None)
        elif con:
            con.close()


def fraud_label(con, context):
    summaries = []
    for scope, where in [
        ("full_extract", "TRUE"),
        (
            "row_date_at_cutoff",
            f"transaction_date::DATE<=DATE {literal(context['feature_cutoff_inclusive'])}",
        ),
    ]:
        summaries += rows(
            con,
            f"""SELECT '{scope}' AS population,count(*) AS total_transactions,
          count(fraud_label) AS valid_is_fraud,count_if(is_fraud IS NULL) AS null_is_fraud,
          count_if(is_fraud IS NOT NULL AND fraud_label IS NULL) AS invalid_is_fraud,
          count_if(fraud_label=true) AS fraud_transactions,count_if(fraud_label=false) AS nonfraud_transactions,
          count_if(fraud_label=true)::DOUBLE/nullif(count(fraud_label),0) AS fraud_rate
          FROM tx WHERE {where}""",
        )
    save("fraud_label_summary.csv", summaries)
    query(
        con,
        "fraud_label_tokens.csv",
        "SELECT is_fraud AS raw_value,count(*) AS records FROM tx GROUP BY 1 ORDER BY 1 NULLS LAST",
    )
    for dim in (
        "transaction_status",
        "transaction_type",
        "transaction_category",
        "channel",
        "transaction_country",
        "currency",
        "merchant_category",
    ):
        query(
            con,
            "fraud_by_" + dim + ".csv",
            f"""SELECT {ident(dim)},count(*) AS records,
          count(fraud_label) AS valid_labels,count_if(is_fraud IS NULL) AS null_labels,
          count_if(is_fraud IS NOT NULL AND fraud_label IS NULL) AS invalid_labels,
          count_if(fraud_label=true) AS fraud_records,count_if(fraud_label=false) AS nonfraud_records,
          count_if(fraud_label=true)::DOUBLE/nullif(count(fraud_label),0) AS fraud_rate
          FROM tx GROUP BY 1 ORDER BY records DESC,{ident(dim)} NULLS LAST""",
        )
    log("1. Label de fraude y segmentaciones completadas")


def fraud_scores(con):
    for dim in ("label_state", "transaction_status", "channel", "transaction_type"):
        query(
            con,
            "fraud_score_by_" + dim + ".csv",
            f"""SELECT {ident(dim)},count(*) AS records,
          count(score) AS valid_score_count,count_if(fraud_score IS NULL) AS null_score_count,
          100.*count_if(fraud_score IS NULL)/count(*) AS null_pct,
          count_if(fraud_score IS NOT NULL AND score IS NULL) AS invalid_score_count,
          count(fraud_label) AS valid_labels,count_if(fraud_label=true) AS fraud_records,{stats("score")}
          FROM tx GROUP BY 1 ORDER BY {ident(dim)} NULLS LAST""",
        )
    bucket = """CASE WHEN fraud_score IS NULL THEN '07 NULL'
      WHEN score IS NULL THEN '08 INVALID_NONFINITE' WHEN score<0 THEN '09 BELOW_0'
      WHEN score<10 THEN '01 [0,10)' WHEN score<20 THEN '02 [10,20)' WHEN score<30 THEN '03 [20,30)'
      WHEN score<50 THEN '04 [30,50)' WHEN score<75 THEN '05 [50,75)'
      WHEN score<=100 THEN '06 [75,100]' ELSE '10 ABOVE_100' END"""
    con.execute(
        f"CREATE TEMP VIEW score_buckets AS SELECT *,{bucket} AS score_bucket FROM tx"
    )
    labels = [
        "01 [0,10)",
        "02 [10,20)",
        "03 [20,30)",
        "04 [30,50)",
        "05 [50,75)",
        "06 [75,100]",
        "07 NULL",
        "08 INVALID_NONFINITE",
        "09 BELOW_0",
        "10 ABOVE_100",
    ]
    found = rows(
        con,
        """SELECT score_bucket,count(*) AS transaction_count,count(fraud_label) AS valid_labels,
      count_if(fraud_label=true) AS fraud_count,count_if(fraud_label=false) AS nonfraud_count,
      count_if(fraud_label=true)::DOUBLE/nullif(count(fraud_label),0) AS fraud_rate
      FROM score_buckets GROUP BY 1""",
    )
    by_bucket = {r["score_bucket"]: r for r in found}
    save(
        "fraud_score_buckets.csv",
        [
            by_bucket.get(
                b,
                dict(
                    score_bucket=b,
                    transaction_count=0,
                    valid_labels=0,
                    fraud_count=0,
                    nonfraud_count=0,
                    fraud_rate=None,
                ),
            )
            for b in labels
        ],
    )
    log("2. Score por label, dimensión y buckets fijos completado")


def taxonomy(con):
    for cols, name in [
        (["case_type", "category"], "complaint_case_category.csv"),
        (["category", "subcategory"], "complaint_category_subcategory.csv"),
        (["case_type", "category", "subcategory"], "complaint_taxonomy.csv"),
    ]:
        keys = ",".join(ident(c) for c in cols)
        query(
            con,
            name,
            f"""SELECT {keys},count(*) AS records,
          100.*count(*)/(SELECT count(*) FROM co) AS pct_of_complaints,
          count_if({present("claimed_amount")}) AS claimed_amount_present_count,
          100.*count_if({present("claimed_amount")})/count(*) AS claimed_amount_present_pct
          FROM co GROUP BY {keys} ORDER BY {keys}""",
        )
    observed = {
        r[0] for r in con.execute("SELECT DISTINCT category FROM co").fetchall()
    }
    assert {"Transactions", "Fees"} <= observed
    observed_pairs = set(
        con.execute("SELECT DISTINCT category,subcategory FROM co").fetchall()
    )
    assert {
        ("Transactions", "Cargo no reconocido"),
        ("Fees", "Cobro indebido"),
    } <= observed_pairs
    save(
        "taxonomy_relevance_annotations.csv",
        [
            dict(
                observed_category="Transactions",
                observed_subcategory="Cargo no reconocido",
                interpretation="Candidate transaction dispute / unauthorized charge signal",
                limitation="Recorded taxonomy only; not proof of unauthorized payment or a final cohort",
            ),
            dict(
                observed_category="Fees",
                observed_subcategory="Cobro indebido",
                interpretation="Candidate incorrect charge / fee dispute signal",
                limitation="May concern fees rather than a specific transaction; no matching attempted",
            ),
            dict(
                observed_category="Transactions",
                observed_subcategory=None,
                interpretation="Broad transaction-related record; subtype unknown",
                limitation="Missing subcategory preserved; no inference of payment, transfer or ATM dispute",
            ),
        ],
    )
    save(
        "requested_themes_taxonomy_evidence.csv",
        [
            dict(theme=t, observed_evidence=e, limitation=l)
            for t, e, l in [
                (
                    "transaction dispute",
                    "Transactions",
                    "Broad category; not a final cohort",
                ),
                (
                    "unauthorized charge",
                    "Transactions / Cargo no reconocido",
                    "Customer taxonomy; not confirmed fraud",
                ),
                (
                    "incorrect charge",
                    "Fees / Cobro indebido",
                    "May refer to fees rather than transaction amount",
                ),
                (
                    "payment dispute",
                    "No dedicated observed category/subcategory",
                    "Cannot infer from generic Transactions",
                ),
                (
                    "transfer dispute",
                    "No dedicated observed category/subcategory",
                    "Cannot infer from generic Transactions",
                ),
                (
                    "ATM/withdrawal dispute",
                    "No dedicated observed category/subcategory",
                    "Cannot infer from generic Transactions",
                ),
            ]
        ],
    )
    log("3. Taxonomía real y anotaciones exploratorias completadas")


def validity(field):
    """Basic lexical/type/range checks, never a claim of business correctness."""
    c = ident(field)
    if field in {
        "amount",
        "amount_usd",
        "fraud_score",
        "claimed_amount",
        "compensation_granted",
        "resolution_satisfaction",
        "resolution_days",
    }:
        return finite(c)
    if field in {"latitude", "longitude"}:
        bound = 90 if field == "latitude" else 180
        return f"({finite(c)} AND try_cast({c} AS DOUBLE) BETWEEN {-bound} AND {bound})"
    if field in {"is_fraud", "sla_breached", "was_resolved", "was_escalated"}:
        return f"({boolean(c)}) IS NOT NULL"
    if field.endswith("_date"):
        return f"try_cast({c} AS TIMESTAMP) IS NOT NULL"
    return present(c)


def coverage(con, table, fields, dimensions, output, where="TRUE", scope="all"):
    """One aggregate scan per dimension, then reshape only small aggregate results."""
    result = []
    for dim in [None, *dimensions]:
        prefix = f"{ident(dim)} AS group_value," if dim else "'ALL' AS group_value,"
        expressions = []
        for i, field in enumerate(fields):
            c = ident(field)
            expressions += [
                f"count_if({c} IS NULL) AS n{i}",
                f"count_if({present(c)}) AS p{i}",
                f"count_if({validity(field)}) AS v{i}",
            ]
        grouped = rows(
            con,
            f"SELECT {prefix} count(*) AS records,"
            + ",".join(expressions)
            + f" FROM {table} WHERE {where}"
            + (" GROUP BY 1 ORDER BY 1 NULLS LAST" if dim else ""),
        )
        for r in grouped:
            for i, field in enumerate(fields):
                n, p, v = (r[f"{k}{i}"] for k in ("n", "p", "v"))
                result.append(
                    dict(
                        scope=scope,
                        dimension=dim or "overall",
                        group_value=r["group_value"],
                        field=field,
                        records=r["records"],
                        present_count=p,
                        valid_count=v,
                        null_count=n,
                        blank_count=r["records"] - n - p,
                        invalid_nonnull_count=r["records"] - n - v,
                        coverage_pct=100 * v / r["records"],
                        present_pct=100 * p / r["records"],
                        validity_rule=validity(field),
                    )
                )
    return save(output, result)


def claimed_amount(con):
    coverage(
        con,
        "co",
        ["claimed_amount", "currency"],
        ["case_type", "category", "subcategory", "currency"],
        "complaint_claimed_amount_coverage.csv",
    )
    for dim in [None, "case_type", "category", "subcategory", "currency"]:
        prefix = f"{ident(dim)} AS group_value," if dim else "'ALL' AS group_value,"
        query(
            con,
            f"claimed_amount_checks_{dim or 'overall'}.csv",
            f"""
          SELECT {prefix} count(*) AS records,
          count_if(claimed_amount IS NULL) AS null_amount,
          count_if({present("claimed_amount")} AND NOT {finite("claimed_amount")}) AS invalid_amount,
          count_if(try_cast(claimed_amount AS DOUBLE)=0) AS zero_amount,
          count_if(try_cast(claimed_amount AS DOUBLE)<0) AS negative_amount,
          count_if({present("claimed_amount")} AND NOT {present("currency")}) AS amount_without_currency,
          count_if({present("currency")} AND NOT {present("claimed_amount")}) AS currency_without_amount
          FROM co {"GROUP BY 1 ORDER BY 1 NULLS LAST" if dim else ""}""",
        )
    query(
        con,
        "claimed_amount_by_currency.csv",
        f"""
      SELECT currency,count(*) AS records,count(claim) AS valid_amounts,{stats("claim")}
      FROM (SELECT currency,CASE WHEN {finite("claimed_amount")}
        THEN claimed_amount::DOUBLE END AS claim FROM co WHERE {present("currency")}) GROUP BY 1 ORDER BY 1 NULLS LAST""",
    )
    query(
        con,
        "claimed_amount_upper_tail_by_currency.csv",
        f"""
      WITH amounts AS (SELECT currency,CASE WHEN {finite("claimed_amount")}
        THEN claimed_amount::DOUBLE END AS claim FROM co WHERE {present("currency")}),
      limits AS (SELECT currency,quantile_cont(claim,.99) AS p99,
        quantile_cont(claim,.999) AS p999 FROM amounts GROUP BY 1)
      SELECT a.currency,count(a.claim) AS valid_amounts,l.p99,l.p999,
        count_if(a.claim>l.p99) AS above_p99,count_if(a.claim>l.p999) AS above_p999,
        max(a.claim) AS maximum FROM amounts a JOIN limits l
        ON a.currency IS NOT DISTINCT FROM l.currency GROUP BY 1,3,4 ORDER BY 1 NULLS LAST""",
    )
    query(
        con,
        "potential_transaction_taxonomy_amount.csv",
        f"""
      SELECT case_type,category,subcategory,count(*) AS complaints_count,
        count_if({finite("claimed_amount")}) AS claimed_amount_available,
        100.*count_if({finite("claimed_amount")})/count(*) AS claimed_amount_coverage_pct,
        100.*count_if({present("currency")})/count(*) AS currency_coverage_pct,
        count_if({finite("claimed_amount")} AND {present("currency")}) AS amount_and_currency_available,
        100.*count_if({finite("claimed_amount")} AND {present("currency")})/count(*) AS amount_and_currency_pct
      FROM co WHERE category IN ('Transactions','Fees')
      GROUP BY 1,2,3 ORDER BY 1,2,3 NULLS LAST""",
    )
    log(
        "4. Claimed amount: cobertura condicional y distribuciones por moneda completadas"
    )


def transaction_evidence(con):
    coverage(
        con,
        "tx",
        EVIDENCE_FIELDS,
        ["channel", "transaction_type", "transaction_status"],
        "transaction_evidence_coverage.csv",
    )
    query(
        con,
        "transaction_identifier_check.csv",
        """
      SELECT count(*) AS records,count(transaction_id) AS nonnull_ids,
      count(DISTINCT transaction_id) AS distinct_ids FROM tx""",
    )
    log("5. Evidencia recuperable y unicidad de transaction_id verificadas")


def geography(con):
    output = []
    for dim in [None, "channel", "transaction_type", "transaction_country"]:
        prefix = f"{ident(dim)} AS group_value," if dim else "'ALL' AS group_value,"
        result = rows(
            con,
            f"""SELECT {prefix} count(*) AS records,
          count_if({present("transaction_country")}) AS country_count,
          count_if({present("transaction_city")}) AS city_count,
          count(latitude) AS latitude_present,count(longitude) AS longitude_present,
          count_if(latitude IS NOT NULL AND longitude IS NOT NULL) AS lat_lon_pair_present,
          count_if({finite("latitude")}) AS latitude_numeric,
          count_if({finite("longitude")}) AS longitude_numeric,
          count_if({validity("latitude")}) AS latitude_valid,
          count_if({validity("longitude")}) AS longitude_valid,
          count_if({validity("latitude")} AND {validity("longitude")}) AS lat_lon_pair_valid,
          count_if({finite("latitude")} AND abs(try_cast(latitude AS DOUBLE))>90) AS latitude_out_of_range,
          count_if({finite("longitude")} AND abs(try_cast(longitude AS DOUBLE))>180) AS longitude_out_of_range
          FROM tx {"GROUP BY 1 ORDER BY 1 NULLS LAST" if dim else ""}""",
        )
        for r in result:
            r["dimension"] = dim or "overall"
            for field in (
                "country_count",
                "city_count",
                "latitude_present",
                "longitude_present",
                "lat_lon_pair_present",
                "latitude_valid",
                "longitude_valid",
                "lat_lon_pair_valid",
            ):
                r[field + "_pct"] = 100 * r[field] / r["records"]
            r["latitude_invalid_nonnull"] = (
                r["latitude_present"] - r["latitude_numeric"]
            )
            r["longitude_invalid_nonnull"] = (
                r["longitude_present"] - r["longitude_numeric"]
            )
        output += result
    save("transaction_geography_coverage.csv", output)
    log("6. Geografía: cobertura y rangos físicos completados, sin geocoding")


def status_evidence(con):
    for dim in ("transaction_type", "channel", "response_code"):
        query(
            con,
            "status_by_" + dim + ".csv",
            f"""
          WITH counts AS (SELECT transaction_status,{ident(dim)},count(*) AS records
            FROM tx GROUP BY 1,2)
          SELECT *,100.*records/sum(records) OVER(PARTITION BY transaction_status) AS pct_within_status,
            100.*records/sum(records) OVER(PARTITION BY {ident(dim)}) AS pct_within_dimension
          FROM counts ORDER BY transaction_status,records DESC,{ident(dim)} NULLS LAST""",
        )
    query(
        con,
        "response_code_associations.csv",
        """
      WITH counts AS (SELECT response_code,transaction_status,count(*) AS records FROM tx GROUP BY 1,2),
      ranked AS (SELECT *,sum(records) OVER(PARTITION BY response_code) AS code_records,
        count(*) OVER(PARTITION BY response_code) AS observed_status_count,
        row_number() OVER(PARTITION BY response_code ORDER BY records DESC,transaction_status) AS rank
        FROM counts)
      SELECT response_code,code_records,observed_status_count,transaction_status AS dominant_status,
        records AS dominant_status_records,100.*records/code_records AS dominant_status_pct,
        response_code IS NOT NULL AND observed_status_count=1 AS exclusive_in_this_extract
        FROM ranked WHERE rank=1 ORDER BY code_records DESC,response_code NULLS LAST""",
    )
    log("7. Estados y códigos como evidencia observable, sin atribuir causas")


def outcomes(con, context):
    fields = [
        "status",
        "resolution",
        "resolution_date",
        "closing_date",
        "compensation_granted",
        "resolution_satisfaction",
        "sla_breached",
        "resolution_days",
        "priority",
    ]
    all_results = []
    for scope, condition in [
        ("all", "TRUE"),
        ("exploratory_Transactions_or_Fees", "category IN ('Transactions','Fees')"),
    ]:
        all_results += coverage(
            con,
            "co",
            fields,
            ["status", "case_type", "category", "subcategory"],
            "complaint_outcome_coverage.csv",
            where=condition,
            scope=scope,
        )
    save("complaint_outcome_coverage.csv", all_results)
    query(
        con,
        "complaint_outcome_distributions.csv",
        """
      SELECT 'status' AS field,category,status AS raw_value,count(*) AS records FROM co GROUP BY 2,3
      UNION ALL SELECT 'priority',category,priority,count(*) FROM co GROUP BY 2,3
      UNION ALL SELECT 'sla_breached',category,sla_breached,count(*) FROM co GROUP BY 2,3
      UNION ALL SELECT 'resolution_satisfaction',category,resolution_satisfaction,count(*) FROM co GROUP BY 2,3
      ORDER BY field,category,raw_value NULLS LAST""",
    )
    query(
        con,
        "complaint_resolution_days_by_status.csv",
        f"""
      SELECT status,count(*) AS records,count(try_cast(resolution_days AS DOUBLE)) AS numeric_count,
      {stats("try_cast(resolution_days AS DOUBLE)")} FROM co GROUP BY 1 ORDER BY 1""",
    )
    query(
        con,
        "compensation_by_currency_status.csv",
        f"""
      SELECT currency,status,count(*) AS records,
      count(try_cast(compensation_granted AS DOUBLE)) AS numeric_count,
      {stats("try_cast(compensation_granted AS DOUBLE)")}
      FROM co WHERE {present("currency")} GROUP BY 1,2 ORDER BY 1,2 NULLS LAST""",
    )
    cutoff = literal(context["feature_cutoff_inclusive"])
    audit = []
    for field in ("resolution_date", "closing_date"):
        audit += rows(
            con,
            f"""SELECT '{field}' AS field,status,category,count(*) AS records,
          count_if({ident(field)} IS NULL) AS null_date,
          count_if(try_cast({ident(field)} AS DATE)<=DATE {cutoff}) AS date_at_or_before_cutoff,
          count_if(try_cast({ident(field)} AS DATE)>DATE {cutoff}) AS date_after_cutoff,
          count_if({ident(field)} IS NOT NULL AND try_cast({ident(field)} AS DATE) IS NULL) AS invalid_date
          FROM co GROUP BY 2,3 ORDER BY 2,3""",
        )
    save("complaint_outcome_cutoff_audit.csv", audit)
    log("8. Outcomes observables y límites temporales documentados")


def label_distributions(con):
    specs = [
        ("transactions", "tx", "is_fraud"),
        ("complaints", "co", "status"),
        ("complaints", "co", "compensation_granted"),
        ("complaints", "co", "resolution_satisfaction"),
        ("call_center_interactions", "call_center_interactions", "was_resolved"),
        ("call_center_interactions", "call_center_interactions", "was_escalated"),
    ]
    summary, distributions = [], []
    for dataset, table, field in specs:
        valid = validity(field)
        summary += rows(
            con,
            f"""SELECT '{dataset}.{field}' AS label,count(*) AS records,
          count_if({valid}) AS valid_count,count_if({ident(field)} IS NULL) AS null_count,
          count_if({ident(field)} IS NOT NULL AND NOT ({valid})) AS invalid_nonnull_count,
          100.*count_if({valid})/count(*) AS coverage_pct FROM {table}""",
        )
        if field == "compensation_granted":
            value = """CASE WHEN compensation_granted IS NULL THEN NULL
              WHEN NOT isfinite(try_cast(compensation_granted AS DOUBLE))
                OR try_cast(compensation_granted AS DOUBLE) IS NULL THEN 'INVALID'
              WHEN compensation_granted::DOUBLE<0 THEN 'negative'
              WHEN compensation_granted::DOUBLE=0 THEN 'zero' ELSE 'positive' END"""
        else:
            value = ident(field)
        distributions += rows(
            con,
            f"""SELECT '{dataset}.{field}' AS label,{value} AS observed_class,
          count(*) AS records,100.*count(*)/(SELECT count(*) FROM {table}) AS pct_all_rows,
          'Recorded values; compensation bins are descriptive, not fraud labels' AS interpretation
          FROM {table} GROUP BY 2 ORDER BY 2 NULLS LAST""",
        )
    save("potential_label_coverage.csv", summary)
    save("potential_label_distributions.csv", distributions)
    log("9. Candidatos de labels caracterizados; ninguno aprobado para modelado")
