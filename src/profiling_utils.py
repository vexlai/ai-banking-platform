"""Perfilado completo, sin imputación, limpieza ni EDA."""
import json

from src.config import ROOT, REPORTS, REFERENCE_DATE
from src.data_utils import (connect, discover, ident, load, manifest,
                            save_csv, save_json, verify_manifest, check_previous_manifest)


def is_date(column):
    return "date" in column or column == "last_updated"


def basic_profile(con, dataset, columns, n):
    result = []
    for col in columns:
        save_json("execution_progress.json", {"stage": "column_inventory", "dataset": dataset, "column": col})
        c = ident(col)
        nulls, distinct, blanks, padded = con.execute(f"""SELECT
            count(*) FILTER (WHERE {c} IS NULL), count(DISTINCT {c}),
            count(*) FILTER (WHERE {c} IS NOT NULL AND trim({c})=''),
            count(*) FILTER (WHERE {c} != trim({c})) FROM current_data""").fetchone()
        result.append(dict(dataset=dataset, column=col, physical_type="VARCHAR", rows=n,
                           nulls=nulls, null_pct=100 * nulls / n if n else None,
                           cardinality=distinct, whitespace_only=blanks, padded_values=padded,
                           possible_id=col.endswith("_id"), possible_date=is_date(col),
                           unique_non_null=bool(n and nulls == 0 and distinct == n)))
    return result


def inventory(reuse_verified=False):
    before = manifest()
    check_previous_manifest(before)
    if reuse_verified and all((REPORTS / name).exists() for name in
                             ("inventory.json", "inventory_integrity.json", "source_manifest.json")):
        integrity = json.loads((REPORTS / "inventory_integrity.json").read_text())
        saved_manifest = json.loads((REPORTS / "source_manifest.json").read_text())
        if integrity.get("sha256_unchanged") and saved_manifest == before:
            cached = json.loads((REPORTS / "inventory.json").read_text())
            print("Inventario completo reutilizado; SHA-256 de todos los originales verificado de nuevo.", flush=True)
            return cached["datasets"], cached["columns"]
    save_json("source_manifest.json", before)
    summaries, profiles, file_rows = [], [], []
    with connect() as con:
        for dataset, files in discover().items():
            print(f"Inventario: {dataset}", flush=True)
            save_json("execution_progress.json", {"stage": "inventory", "dataset": dataset})
            schemas = {tuple(r["columns"]) for r in before if r["dataset"] == dataset}
            if len(schemas) != 1:
                raise ValueError(f"Schema drift en {dataset}: {schemas}")
            columns = load(con, files)
            n = con.execute("SELECT count(*) FROM current_data").fetchone()[0]
            counts = dict(con.execute("SELECT _source_file, count(*) FROM current_data GROUP BY 1").fetchall())
            for path in files:
                file_rows.append(dict(dataset=dataset, path=path.relative_to(ROOT).as_posix(),
                                      rows=counts.get(str(path), 0), columns=len(columns), bytes=path.stat().st_size))
            profiles.extend(basic_profile(con, dataset, columns, n))
            summaries.append(dict(dataset=dataset, files=len(files), rows=n, columns=len(columns),
                                  bytes=sum(p.stat().st_size for p in files), schema_variants=len(schemas)))
            save_csv("datasets.partial.csv", summaries)
    save_csv("datasets.csv", summaries)
    save_csv("files.csv", file_rows)
    save_csv("inventory_columns.csv", profiles)
    save_json("inventory.json", dict(datasets=summaries, columns=profiles))
    save_json("inventory_integrity.json", verify_manifest(before))
    save_json("execution_progress.json", {"stage": "inventory", "status": "complete"})
    return summaries, profiles


def detailed_column(con, base):
    col, n = base["column"], base["rows"]
    c = ident(col)
    non_null = n - base["nulls"]
    if base["cardinality"] == non_null:
        frequency = int(non_null > 0)
    elif base["cardinality"] == 1:
        frequency = non_null
    else:
        frequency = con.execute(f"SELECT max(n) FROM (SELECT count(*) n FROM current_data WHERE {c} IS NOT NULL GROUP BY {c})").fetchone()[0] or 0
    numeric_count, bool_count = con.execute(f"""SELECT
        count(try_cast({c} AS DOUBLE)),
        count(*) FILTER (WHERE lower({c}) IN ('true','false')) FROM current_data""").fetchone()
    result = dict(base, inferred_type="TEXT", constant=base["cardinality"] == 1,
                  almost_constant=bool(non_null and frequency / non_null >= .99 and base["cardinality"] > 1),
                  dominant_non_null_pct=100 * frequency / non_null if non_null else None,
                  invalid_dates=None, future_dates=None, minimum=None, maximum=None,
                  numeric_parse_failures=None, non_finite=None, q1=None, q3=None,
                  iqr_lower=None, iqr_upper=None, possible_outliers=None)
    if is_date(col):
        result["inferred_type"] = "TIMESTAMP_CANDIDATE"
        bad, future, lo, hi = con.execute(f"""SELECT
            count(*) FILTER (WHERE {c} IS NOT NULL AND try_cast({c} AS TIMESTAMP) IS NULL),
            count(*) FILTER (WHERE try_cast({c} AS TIMESTAMP) >= TIMESTAMP '{REFERENCE_DATE}' + INTERVAL 1 DAY),
            min(try_cast({c} AS TIMESTAMP)), max(try_cast({c} AS TIMESTAMP)) FROM current_data""").fetchone()
        result.update(invalid_dates=bad, future_dates=future, minimum=str(lo) if lo else None, maximum=str(hi) if hi else None)
    elif non_null and bool_count == non_null:
        result["inferred_type"] = "BOOLEAN"
    elif non_null and numeric_count / non_null >= .95 and not (col.endswith("_id") or any(t in col for t in ("code", "number", "phone", "postal"))):
        result["inferred_type"] = "NUMERIC_CANDIDATE"
        result["numeric_parse_failures"] = non_null - numeric_count
        result["non_finite"] = con.execute(f"SELECT count(*) FROM current_data WHERE NOT isfinite(try_cast({c} AS DOUBLE))").fetchone()[0]
        lo, hi, q1, q3 = con.execute(f"""SELECT min(v), max(v), quantile_cont(v,.25), quantile_cont(v,.75)
            FROM (SELECT try_cast({c} AS DOUBLE) v FROM current_data) WHERE isfinite(v)""").fetchone()
        result.update(minimum=lo, maximum=hi, q1=q1, q3=q3)
        if q1 is not None:
            lower, upper = q1 - 1.5 * (q3-q1), q3 + 1.5 * (q3-q1)
            outliers = con.execute(f"SELECT count(*) FROM current_data WHERE isfinite(try_cast({c} AS DOUBLE)) AND (try_cast({c} AS DOUBLE) < ? OR try_cast({c} AS DOUBLE) > ?)", [lower, upper]).fetchone()[0]
            result.update(iqr_lower=lower, iqr_upper=upper, possible_outliers=outliers)
    return result


# Nombres observados en los encabezados originales; son hipótesis semánticas.
ALIASES = {"registration_branch_id": "branch_id", "opening_branch_id": "branch_id",
           "assigned_branch_id": "branch_id", "related_branch_id": "branch_id",
           "assigned_agent_id": "agent_id", "affected_product_id": "product_id",
           "origin_interaction_id": "interaction_id"}
TARGETS = {"customer_id": "customers", "product_id": "products", "branch_id": "branches",
           "agent_id": "service_agents", "interaction_id": "call_center_interactions",
           "campaign_id": "marketing_campaigns"}


def profiling():
    before = manifest()
    check_previous_manifest(before)
    # Las métricas de 00 se pueden reutilizar solo con el mismo manifiesto íntegro.
    cached_columns = []
    if (REPORTS / "inventory.json").exists() and (REPORTS / "inventory_integrity.json").exists():
        integrity = json.loads((REPORTS / "inventory_integrity.json").read_text())
        saved_manifest = json.loads((REPORTS / "source_manifest.json").read_text())
        if integrity.get("sha256_unchanged") and saved_manifest == before:
            cached_columns = json.loads((REPORTS / "inventory.json").read_text())["columns"]
    details, datasets, keys, relations = [], [], [], []
    id_tables = {}
    with connect() as con:
        for dataset, files in discover().items():
            print(f"Profiling: {dataset}", flush=True)
            save_json("execution_progress.json", {"stage": "profiling", "dataset": dataset})
            schemas = {tuple(r["columns"]) for r in before if r["dataset"] == dataset}
            if len(schemas) != 1:
                raise ValueError(f"Schema drift en {dataset}: {schemas}")
            columns = load(con, files)
            n = con.execute("SELECT count(*) FROM current_data").fetchone()[0]
            bases = [c for c in cached_columns if c["dataset"] == dataset]
            if [c["column"] for c in bases] != columns or any(c["rows"] != n for c in bases):
                bases = basic_profile(con, dataset, columns, n)
            cols = ','.join(map(ident, columns))
            # Una columna única y no nula demuestra que no hay filas duplicadas.
            unique_rows = n if any(b["unique_non_null"] for b in bases) else con.execute(
                f"SELECT count(*) FROM (SELECT DISTINCT {cols} FROM current_data)").fetchone()[0]
            datasets.append(dict(dataset=dataset, rows=n, duplicate_rows_excess=n-unique_rows))
            for base in bases:
                save_json("execution_progress.json", {"stage": "column_profiling", "dataset": dataset, "column": base["column"]})
                details.append(detailed_column(con, base))
                col = base["column"]
                if base["unique_non_null"] or col.endswith("_id"):
                    keys.append(dict(dataset=dataset, columns=col, null_rows=base["nulls"],
                                     distinct=base["cardinality"], duplicate_non_null_excess=n-base["nulls"]-base["cardinality"],
                                     candidate_key=base["unique_non_null"], scope="single_column"))
                if ALIASES.get(col, col) in TARGETS:
                    table = f"ids_{len(id_tables)}"
                    con.execute(f"CREATE TEMP TABLE {table} AS SELECT {ident(col)} AS key_value, count(*) n FROM current_data GROUP BY 1")
                    id_tables[(dataset, col)] = table
            if dataset == "daily_exchange_rates":
                combination = ["date", "source_currency", "target_currency"]
                if set(combination) <= set(columns):
                    sqlcols = ','.join(map(ident, combination))
                    distinct = con.execute(f"SELECT count(*) FROM (SELECT DISTINCT {sqlcols} FROM current_data)").fetchone()[0]
                    nulls = con.execute("SELECT count(*) FROM current_data WHERE " + ' OR '.join(f"{ident(c)} IS NULL" for c in combination)).fetchone()[0]
                    keys.append(dict(dataset=dataset, columns=' + '.join(combination), null_rows=nulls, distinct=distinct,
                                     duplicate_non_null_excess=n-distinct, candidate_key=distinct == n and nulls == 0,
                                     scope="composite_tested"))
            save_csv("column_profiles.partial.csv", details)
            save_csv("duplicates.partial.csv", datasets)
        con.execute("DROP TABLE current_data")
        for (dataset, col), table in id_tables.items():
            target_col = ALIASES.get(col, col)
            target = TARGETS.get(target_col)
            if target is None or target == dataset or (target, target_col) not in id_tables:
                continue
            parent = id_tables[(target, target_col)]
            total, missing, matched, orphan = con.execute(f"""SELECT coalesce(sum(s.n),0),
                coalesce(sum(s.n) FILTER (WHERE s.key_value IS NULL),0),
                coalesce(sum(s.n) FILTER (WHERE s.key_value IS NOT NULL AND p.key_value IS NOT NULL),0),
                coalesce(sum(s.n) FILTER (WHERE s.key_value IS NOT NULL AND p.key_value IS NULL),0)
                FROM {table} s LEFT JOIN {parent} p ON s.key_value=p.key_value""").fetchone()
            parent_duplicates = con.execute(f"SELECT coalesce(sum(n-1),0) FROM {parent} WHERE key_value IS NOT NULL").fetchone()[0]
            relations.append(dict(source_dataset=dataset, source_column=col, target_dataset=target,
                                  target_column=target_col, source_rows=total, null_rows=missing,
                                  matched_rows=matched, orphan_rows=orphan,
                                  match_pct_non_null=100*matched/(total-missing) if total != missing else None,
                                  parent_duplicate_excess=parent_duplicates,
                                  status="hypothesis; value overlap checked, business meaning unconfirmed"))
    save_csv("column_profiles.csv", details)
    save_csv("duplicates.csv", datasets)
    save_csv("candidate_keys.csv", keys)
    save_csv("relationships.csv", relations)
    save_json("profiling.json", dict(columns=details, datasets=datasets, keys=keys, relationships=relations))
    save_json("profiling_integrity.json", verify_manifest(before))
    save_json("execution_progress.json", {"stage": "profiling", "status": "complete"})
    return details, datasets, keys, relations
