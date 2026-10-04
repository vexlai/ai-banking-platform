"""Customer-grain joins, targeted associations, figures and evidence-based findings."""

from src.data.eda.eda_core import *

FEATURES = [
    "products_customer_features",
    "transactions_customer_features",
    "digital_customer_features",
    "call_customer_features",
    "complaint_customer_features",
    "survey_customer_features",
    "campaign_customer_features",
]


def customer360(con, ctx):
    checks = []
    select = ["c.customer_id"]
    joins = []
    for i, name in enumerate(FEATURES):
        a = rows(
            con,
            f"SELECT count(*) AS rows,count(DISTINCT customer_id) distinct_customers,count_if(customer_id IS NULL) null_ids FROM {name}",
        )[0]
        assert a["rows"] == a["distinct_customers"] and a["null_ids"] == 0
        checks.append(dict(table=name, **a))
        for col in [
            r[0]
            for r in con.execute(f"DESCRIBE {name}").fetchall()
            if r[0] != "customer_id"
        ]:
            select.append(f"f{i}.{ident(col)}")
        select.append(
            f"(f{i}.customer_id IS NOT NULL) AS has_{name.removesuffix('_customer_features')}_observations"
        )
        joins.append(f"LEFT JOIN {name} f{i} ON c.customer_id=f{i}.customer_id")
    con.execute(
        "CREATE OR REPLACE TABLE customer_360_eda AS SELECT "
        + ",".join(select)
        + " FROM customers c "
        + " ".join(joins)
    )
    a = rows(
        con,
        "SELECT count(*) AS rows,count(DISTINCT customer_id) distinct_customers,count_if(customer_id IS NULL) null_ids FROM customer_360_eda",
    )[0]
    assert (
        a["rows"]
        == a["distinct_customers"]
        == con.execute("SELECT count(*) FROM customers").fetchone()[0]
    )
    checks.append(dict(table="customer_360_eda", **a))
    save("feature_cardinality.csv", checks)
    export(con, "customer_360_eda", "SELECT * FROM customer_360_eda")
    feature_cols = [
        "transaction_count",
        "digital_event_count",
        "interaction_count",
        "complaint_count",
        "survey_count",
        "sends",
    ]
    numeric(con, "customer_360_eda", feature_cols, "customer_feature_distributions.csv")
    pairs = [
        ("digital_event_count", "interaction_count"),
        ("transaction_count", "complaint_count"),
        ("complaint_count", "avg_satisfaction"),
        ("median_wait_time", "avg_satisfaction"),
        ("interaction_count", "avg_satisfaction"),
    ]
    associations = []
    for x, y in pairs:
        associations.extend(
            rows(
                con,
                f"""WITH z AS (
          SELECT {x}::DOUBLE x,{y}::DOUBLE y FROM customer_360_eda WHERE {x} IS NOT NULL AND {y} IS NOT NULL),
          ranked AS (SELECT *,rank() OVER(ORDER BY x)+(count(*) OVER(PARTITION BY x)-1)/2.0 rx,
            rank() OVER(ORDER BY y)+(count(*) OVER(PARTITION BY y)-1)/2.0 ry FROM z)
          SELECT '{x}' x,'{y}' y,count(*) paired_customers,corr(x,y) pearson_raw,
            corr(ln(1+x),y) pearson_log1p_x,corr(rx,ry) spearman,
            'paired observed domains; CSAT only for satisfaction; no causal inference' interpretation FROM ranked""",
            )
        )
    save("cross_domain_associations.csv", associations)
    groups = []
    for x, y in pairs:
        groups.extend(
            rows(
                con,
                f"""WITH q AS (SELECT quantile_cont({x},.25) q1,quantile_cont({x},.5) q2,
          quantile_cont({x},.75) q3 FROM customer_360_eda WHERE {x} IS NOT NULL AND {y} IS NOT NULL),
          z AS (SELECT {y} y,CASE WHEN {x}<=q1 THEN '1 <= p25' WHEN {x}<=q2 THEN '2 <= p50'
             WHEN {x}<=q3 THEN '3 <= p75' ELSE '4 > p75' END x_band
             FROM customer_360_eda CROSS JOIN q WHERE {x} IS NOT NULL AND {y} IS NOT NULL)
          SELECT '{x}' x,'{y}' y,x_band,count(*) customers,median(y) median_y,avg(y) mean_y FROM z GROUP BY 3 ORDER BY 3""",
            )
        )
    save("cross_domain_groups.csv", groups)
    # Outcome-time restriction audit, not a retrospective feature availability guarantee.
    audit = []
    for ds, event in EVENTS.items():
        if ds == "call_transcripts":
            continue
        audit.extend(
            rows(
                con,
                f"SELECT '{ds}' dataset,count(*) total,count_if({event}::DATE>DATE {literal(ctx['feature_cutoff_inclusive'])}) events_after_cutoff FROM {ds}",
            )
        )
    save("feature_temporal_audit.csv", audit)
    log("Customer 360 y asociaciones completadas")
    return checks


def figures():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    plt.rcParams.update({"font.size": 9})
    df = pd.read_csv(OUT / "coverage_monthly.csv")
    fig, axes = plt.subplots(4, 2, figsize=(13, 13), constrained_layout=True)
    for ax, (domain, g) in zip(axes.flat, df.groupby("dataset")):
        ax.plot(pd.to_datetime(g.month), g.records, marker=".", linewidth=1)
        ax.set(title=domain, ylabel="Registros/mes")
        ax.tick_params(axis="x", rotation=35)
    axes.flat[-1].axis("off")
    fig.suptitle("Cobertura mensual — meses extremos pueden ser parciales")
    fig.savefig(FIG / "monthly_coverage.png", dpi=140)
    plt.close(fig)
    df = pd.read_csv(OUT / "amount_usd_histogram.csv")
    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    for sign, g in df[df.sign.isin(["positive", "negative"])].groupby("sign"):
        ax.plot(g.log10_bin, g.records, label=sign)
    special = df[df.sign.isin(["zero", "missing"])].records.sum()
    ax.set(
        xlabel="log10(|amount_usd|), bins de 0.1",
        ylabel="Transacciones",
        yscale="log",
        title=f"Montos USD: cola completa; cero/nulos fuera del eje log: {special:,}",
    )
    ax.legend()
    fig.savefig(FIG / "amount_usd_distribution.png", dpi=140)
    plt.close(fig)
    df = pd.read_csv(OUT / "service_histograms.csv")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    for ax, (variable, g) in zip(axes, df.groupby("variable")):
        missing = int(g.loc[g.lower_seconds.isna(), "records"].sum())
        observed = g[g.lower_seconds.notna()]
        ax.bar(
            observed.lower_seconds,
            observed.records,
            width=120 if variable == "duration_seconds" else 30,
        )
        ax.set(
            title=f"{variable}; sin valor: {missing:,}",
            xlabel="Segundos",
            ylabel="Interacciones observadas",
            yscale="log",
        )
    fig.savefig(FIG / "service_duration_wait.png", dpi=140)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
    for ax, prefix in zip(axes, ["transcript", "survey"]):
        df = pd.read_csv(OUT / (prefix + "_selection_monthly.csv"))
        ax.plot(pd.to_datetime(df.month), df.coverage_pct)
        ax.set(
            title=f"Cobertura de {prefix} por mes de interacción",
            ylabel="% interacciones",
        )
    fig.savefig(FIG / "selection_coverage.png", dpi=140)
    plt.close(fig)


def _read(name):
    with (OUT / name).open() as f:
        return list(csv.DictReader(f))


def _table(records, cols):
    text = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for row in records:
        text.append(
            "| "
            + " | ".join(str(row.get(c, "")).replace("|", "/") for c in cols)
            + " |"
        )
    return "\n".join(text)


def findings(ctx):
    sem = _read("semantic_validation.csv")
    coverage = _read("temporal_coverage.csv")
    digital = _read("digital_coverage.csv")[0]
    tx = _read("transaction_numeric.csv")
    customer_cats = _read("customer_categories.csv")
    customer_top = [r for r in customer_cats if r["variable"] in ("country", "segment")]
    transaction_top = [
        r
        for r in _read("transaction_categories.csv")
        if r["variable"] in ("channel", "transaction_type", "transaction_status")
    ]
    lines = [
        "# EDA Findings & Implications for Customer Journey Discovery",
        "",
        "## Confirmed findings",
        "",
        f"Ejecutado: {ctx['execution_timestamp']}. Corte de features: {ctx['feature_cutoff_inclusive']} inclusive; edad referida a ese día.",
        "",
        "### Coherencia semántica",
        "",
        _table(
            sem,
            [
                "validation",
                "total",
                "eligible",
                "consistent",
                "inconsistent",
                "orphan",
                "consistent_pct",
            ],
        ),
        "",
        "Los IDs coincidentes no prueban coherencia de propietario/agente; las discrepancias anteriores se conservan y los ejemplos están seudonimizados en semantic_validation_examples.csv.",
        "",
        "La relación affected_product_id de reclamos describe una referencia declarada; con propietario discordante no permite atribuir ese producto al cliente del reclamo.",
        "",
        "### Horizonte observado",
        "",
        _table(
            coverage,
            [
                "dataset",
                "basis",
                "min_timestamp",
                "max_timestamp",
                "active_days",
                "days_without_records",
            ],
        ),
        "",
        "Fechas posteriores de resolución/cierre/conversión se reportan en lifecycle_windows.csv. Las fechas nominales de proceso se comparan por día; sus horas calculadas contra medianoche no prueban latencia real.",
        "",
        "### Clientes y transacciones",
        "",
        _table(
            _read("customer_numeric.csv"), ["variable", "valid", "median", "p90", "p99"]
        ),
        "",
        _table(customer_top, ["variable", "category", "records", "pct"]),
        "",
        _table(
            tx,
            ["variable", "valid", "minimum", "median", "p90", "p95", "p99", "maximum"],
        ),
        "",
        _table(
            _read("exchange_rate_coverage.csv"),
            [
                "currency",
                "transactions",
                "amount_usd_observed",
                "amount_usd_coverage_pct",
            ],
        ),
        "",
        "Los resúmenes de amount_usd describen exclusivamente valores observados. Las transacciones USD tienen amount_usd nulo en este extracto; amount se mantiene separado por moneda y no se rellena automáticamente amount_usd. Las features incluyen conteo y porcentaje monetario observado por cliente.",
        "",
        _table(transaction_top, ["variable", "category", "records", "pct"]),
        "",
        "Ingreso se presenta por país sin asumir moneda ni equivalencia internacional. Balances y límites se segmentan por moneda. Las categorías y altas por mes se encuentran en los CSV de cada dominio.",
        "",
        "### Digital",
        "",
        _table(
            [digital],
            [
                "events",
                "identified",
                "anonymous",
                "anonymous_pct",
                "identified_customers",
                "product_known_pct",
            ],
        ),
        "",
        _table(
            _read("digital_sessions_quality.csv"),
            [
                "sessions",
                "singleton_sessions",
                "multi_customer_sessions",
                "anonymous_only_sessions",
                "mixed_identity_sessions",
            ],
        ),
        "",
        "La duración de sesión es el intervalo entre el primer y último evento observado; un evento único implica intervalo cero, no duración real cero.",
        "",
        "### Transcripts y surveys",
        "",
        _table(
            _read("transcript_coverage.csv"),
            [
                "n_interactions",
                "n_interactions_with_transcript",
                "interaction_coverage_pct",
                "n_calls",
                "n_calls_with_transcript",
                "call_coverage_pct",
            ],
        ),
        "",
        _table(
            _read("survey_coverage.csv"),
            [
                "n_interactions",
                "n_interactions_with_survey",
                "interaction_coverage_pct",
                "n_calls",
                "n_calls_with_survey",
                "call_coverage_pct",
            ],
        ),
        "",
        _table(
            _read("survey_scores_by_type.csv"),
            ["survey_type", "valid", "minimum", "median", "maximum"],
        ),
        "",
        "Las tablas *_selection_numeric/categories/monthly.csv comparan ambos grupos. Diferencias descriptivas sugieren selección; semejanza en estas variables no demuestra ausencia de sesgo. CSAT, CES y NPS se mantienen separados; las features de satisfacción usan solo CSAT.",
        "",
        "### Reclamos",
        "",
        _table(
            _read("complaint_conditional_nulls.csv"),
            [
                "status",
                "records",
                "resolution_null_pct",
                "closing_null_pct",
                "origin_interaction_null",
            ],
        ),
        "",
        "Los nulos se evalúan por estado. Los agregados temporales de resolución usan únicamente fechas <= corte; open_complaint_count queda NULL porque un estado snapshot no reconstruye el estado histórico. Se proporciona no_observed_resolution_by_cutoff_count como observación distinta, no como equivalencia a abierto.",
        "",
        "### Campañas",
        "",
        _table(
            _read("campaign_funnel.csv"),
            [
                "sent",
                "delivered",
                "opened",
                "clicked",
                "converted",
                "strict_full_funnel",
                "converted_without_clicked",
                "converted_missing_date",
                "nonconverted_with_date",
            ],
        ),
        "",
        "Los flags marginales y el funnel estricto se muestran por separado. NULL de fecha sin conversión no se clasifica como defecto. Moneda de conversion_value/send_cost no documentada: sumas en unidades originales, sin equipararlas a USD.",
        "",
        "### Tipos de cambio",
        "",
        _table(
            _read("exchange_rate_validation.csv"),
            [
                "currency",
                "pair_direction",
                "operation",
                "matched",
                "eligible_amounts",
                "within_tolerance_pct",
                "median_relative_error",
            ],
        ),
        "",
        "Se contrastan ambas direcciones y fórmulas usando día calendario exacto, tolerancia max(0.02 USD, 1% de amount_usd). El ajuste empírico es evidencia de compatibilidad, no confirmación contractual de las unidades. No se corrigen montos ni se usan tasas de otro día.",
        "",
        "### Asociaciones preliminares",
        "",
        _table(
            _read("cross_domain_associations.csv"),
            ["x", "y", "paired_customers", "pearson_raw", "spearman"],
        ),
        "",
        "Solo clientes con ambas observaciones; ausencia de dominio permanece NULL. Estas asociaciones no son causales y pueden reflejar exposición, selección o claves incoherentes.",
        "",
        "## Data limitations",
        "",
        "- registration_branch_id y assigned_branch_id: relaciones no confiables según profiling; excluidas de joins geográficos.",
        "- Reclamos sin origin_interaction_id; no existe enlace observado al contacto que los originó.",
        "- Digital anónimo y product_id escaso; sesiones multi-cliente, si aparecen, requieren revisión antes de enlazar secuencias.",
        "- Transcripts y encuestas tienen cobertura parcial; interacciones incluyen llamadas, chat, email y video.",
        "- last_updated ambiguo; atributos de snapshot (saldo, segmento, income, score y estado) no entran en customer_360.",
        "- No hay timestamps de disponibilidad/revisiones: features son agregados EDA a corte, no certificación de point-in-time para modelos.",
        "- Meses/días extremos pueden ser parciales; cambios x2 o /2 son alertas de volumen, no errores automáticos.",
        "- No se exporta texto personal; lengths/word counts son aproximaciones por caracteres/tokens de espacio.",
        "",
        "## Hypotheses",
        "",
        "- Explicar la discordancia reclamo-producto antes de interpretar propiedad y recorridos entre esos dominios.",
        "- Investigar continuidad entre eventos anónimos e identificados dentro de sesiones mixtas, sin atribuirlos automáticamente en esta etapa.",
        "- Investigar el calendario de proceso frente a eventos que cruzan medianoche; confirmar zona horaria y fecha operativa.",
        "- Evaluar actividad digital y frecuencia de atención controlando exposición y selección.",
        "- Examinar espera y CSAT dentro de canales/motivos comparables y con enlaces semánticamente válidos.",
        "- Confirmar dirección/unidades FX y semántica de sesión con responsables de los datos.",
        "- Determinar cómo representar reclamos sin interacción de origen, manteniendo enlaces hipotéticos separados.",
        "",
        "Se detiene la etapa 02. No se ejecutan journeys, modelado, embeddings ni LLMs.",
    ]
    (OUT / "EDA_FINDINGS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    key = []
    for filename in [
        "semantic_validation.csv",
        "digital_coverage.csv",
        "transcript_coverage.csv",
        "survey_coverage.csv",
        "campaign_funnel.csv",
        "feature_cardinality.csv",
    ]:
        for i, r in enumerate(_read(filename)):
            for k, v in r.items():
                key.append({"source": filename, "record": i, "metric": k, "value": v})
    save("key_eda_metrics.csv", key)
