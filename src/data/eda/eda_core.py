"""Reproducible DuckDB EDA: projected disk cache, exact aggregates, immutable inputs."""

import csv
import hashlib
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import duckdb
from src.data.config import REPORTS, REPORTS_DIR, ROOT
from src.data.data_utils import discover, ident, literal, manifest

OUT = REPORTS_DIR / "eda"
FIG = REPORTS_DIR / "figures" / "eda"
CACHE = ROOT / ".tmp/eda"
EVENTS = {
    "transactions": "transaction_date",
    "digital_events": "event_date",
    "call_center_interactions": "interaction_date",
    "call_transcripts": "process_date",
    "complaints": "creation_date",
    "satisfaction_surveys": "survey_date",
    "campaign_sends": "send_date",
}
EXCLUDE = {
    "customers": {
        "document_number",
        "first_name",
        "last_name",
        "email",
        "mobile_phone",
        "landline_phone",
        "address",
        "postal_code",
        "last_updated",
    },
    "products": {"product_number", "last_updated"},
    "digital_events": {
        "ip_address",
        "page_url",
        "page_title",
        "referrer",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "element_id",
    },
    "branches": {"address", "phone", "email"},
    "service_agents": {"first_name", "last_name", "email", "phone"},
    "complaints": {"description", "resolution"},
    "call_transcripts": {
        "customer_text",
        "agent_text",
        "mentioned_entities",
        "detected_keywords",
        "detected_intents",
        "main_topics",
    },
    "satisfaction_surveys": {"open_comments"},
    "campaign_sends": {"subject", "template_used"},
}


def rows(con, sql):
    c = con.execute(sql)
    names = [r[0] for r in c.description]
    return [dict(zip(names, r)) for r in c.fetchall()]


def save(name, data, fields=None):
    data = list(data)
    fields = fields or list(dict.fromkeys(k for r in data for k in r))
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields or ["no_records"])
        w.writeheader()
        w.writerows(data)
    return data


def report(con, name, sql):
    return save(name, rows(con, sql))


def export(con, name, query):
    con.execute(
        f"COPY ({query}) TO {literal(OUT / (name + '.parquet'))} (FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def log(stage):
    print(stage, flush=True)
    with (OUT / "execution.log").open("a") as f:
        f.write(datetime.now().isoformat(timespec="seconds") + " " + stage + "\n")


def start():
    for p in (OUT, FIG, CACHE):
        p.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(CACHE / "matplotlib")
    log("Verifying source SHA-256 against the existing profiling")
    current = manifest()
    baseline = json.loads((REPORTS / "source_manifest.json").read_text())
    assert current == baseline, "Sources differ from the profiling manifest"
    with (REPORTS / "datasets.csv").open() as f:
        inventory = {r["dataset"]: r for r in csv.DictReader(f)}
    signature = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
    con = duckdb.connect(str(CACHE / "analysis.duckdb"))
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    con.execute("SET preserve_insertion_order=false")
    con.execute(
        "CREATE TABLE IF NOT EXISTS cache_info(dataset VARCHAR PRIMARY KEY, signature VARCHAR)"
    )
    for ds, files in discover().items():
        cols = next(r["columns"] for r in current if r["dataset"] == ds)
        selected = [c for c in cols if c not in EXCLUDE.get(ds, set())]
        key = signature + "|" + ",".join(selected)
        hit = con.execute(
            "SELECT signature FROM cache_info WHERE dataset=?", [ds]
        ).fetchone()
        if hit and hit[0] == key:
            log("Cache verified: " + ds)
            continue
        log(
            f"Reading {ds}: {inventory[ds]['rows']} rows, {inventory[ds]['bytes']} bytes CSV"
        )
        paths = "[" + ",".join(literal(p) for p in files) + "]"
        schema = "{" + ",".join(literal(c) + ":'VARCHAR'" for c in cols) + "}"
        projection = ",".join(ident(c) for c in selected)
        con.execute(f"""CREATE OR REPLACE TABLE {ident(ds)} AS SELECT {projection},_source_file
          FROM read_csv({paths},columns={schema},auto_detect=false,header=true,delim=',',quote='"',escape='"',
          hive_partitioning=false,filename='_source_file',strict_mode=true,ignore_errors=false,null_padding=false)""")
        n = con.execute(f"SELECT count(*) FROM {ident(ds)}").fetchone()[0]
        assert n == int(inventory[ds]["rows"]), (ds, n)
        con.execute("INSERT OR REPLACE INTO cache_info VALUES (?,?)", [ds, key])
        con.execute("CHECKPOINT")
    cutoff = min(
        con.execute(f"SELECT max(process_date::DATE) FROM {ds}").fetchone()[0]
        for ds in EVENTS
    )
    ctx = {
        "execution_timestamp": datetime.now(ZoneInfo("America/Guayaquil")).isoformat(),
        "feature_cutoff_inclusive": str(cutoff),
        "age_reference_date": str(cutoff),
        "source_manifest_sha256": signature,
        "source_files": len(current),
        "method": "Exact DuckDB; no sampling, imputation or outlier removal",
        "satisfaction_policy": "avg_satisfaction/latest_satisfaction are CSAT only",
        "feature_policy": "Events and dated outcomes <= cutoff; ambiguous snapshot attributes excluded",
    }
    (OUT / "analysis_context.json").write_text(json.dumps(ctx, indent=2) + "\n")
    return con, ctx


def finish(con, ctx):
    current = manifest()
    assert (
        hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
        == ctx["source_manifest_sha256"]
    )
    (OUT / "source_integrity.json").write_text(
        json.dumps({"files_verified": len(current), "sha256_unchanged": True}, indent=2)
        + "\n"
    )
    con.close()
    log("EDA complete; sources verified SHA-256")


def numeric(con, table, columns, name, group=None, where="TRUE"):
    result = []
    prefix = (ident(group) + ",") if group else ""
    suffix = (" GROUP BY " + ident(group)) if group else ""
    for col in columns:
        expr = f"try_cast({ident(col)} AS DOUBLE)"
        result.extend(
            rows(
                con,
                f"""SELECT '{table}' dataset,'{col}' AS variable,{prefix}
          count(*) AS rows,count({expr}) AS valid,count_if({ident(col)} IS NOT NULL AND {expr} IS NULL) invalid_numeric,
          min({expr}) minimum,max({expr}) maximum,avg({expr}) mean,median({expr}) median,
          quantile_cont({expr},.9) p90,quantile_cont({expr},.95) p95,quantile_cont({expr},.99) p99
          FROM {table} WHERE {where}{suffix}""",
            )
        )
    return save(name, result)


def categories(con, table, columns, name, where="TRUE"):
    result = []
    for col in columns:
        result.extend(
            rows(
                con,
                f"""SELECT '{table}' dataset,'{col}' AS variable,{ident(col)} category,
           count(*) records,100.*count(*)/sum(count(*)) OVER() pct
           FROM {table} WHERE {where} GROUP BY {ident(col)} ORDER BY records DESC,category""",
            )
        )
    return save(name, result)
