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
    log("Customer 360 and associations completed")
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
        ax.set(title=domain, ylabel="Records/month")
        ax.tick_params(axis="x", rotation=35)
    axes.flat[-1].axis("off")
    fig.suptitle("Monthly coverage — extreme months may be partial")
    fig.savefig(FIG / "monthly_coverage.png", dpi=140)
    plt.close(fig)
    df = pd.read_csv(OUT / "amount_usd_histogram.csv")
    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    for sign, g in df[df.sign.isin(["positive", "negative"])].groupby("sign"):
        ax.plot(g.log10_bin, g.records, label=sign)
    special = df[df.sign.isin(["zero", "missing"])].records.sum()
    ax.set(
        xlabel="log10(|amount_usd|), bins of 0.1",
        ylabel="Transactions",
        yscale="log",
        title=f"USD amounts: full tail; zero/nulls outside the log axis: {special:,}",
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
            title=f"{variable}; missing: {missing:,}",
            xlabel="Seconds",
            ylabel="Observed interactions",
            yscale="log",
        )
    fig.savefig(FIG / "service_duration_wait.png", dpi=140)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
    for ax, prefix in zip(axes, ["transcript", "survey"]):
        df = pd.read_csv(OUT / (prefix + "_selection_monthly.csv"))
        ax.plot(pd.to_datetime(df.month), df.coverage_pct)
        ax.set(
            title=f"{prefix} coverage by interaction month",
            ylabel="% interactions",
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
        f"Executed: {ctx['execution_timestamp']}. Feature cutoff: {ctx['feature_cutoff_inclusive']} inclusive; age is as of that date.",
        "",
        "### Semantic consistency",
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
        "Matching IDs do not prove owner/agent consistency; the discrepancies above are preserved and the examples are pseudonymized in semantic_validation_examples.csv.",
        "",
        "The complaint affected_product_id relationship describes a declared reference; with a mismatching owner it does not attribute that product to the complaining customer.",
        "",
        "### Observed horizon",
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
        "Later resolution/closure/conversion dates are reported in lifecycle_windows.csv. Nominal process dates are compared by day; their computed hours against midnight do not prove real latency.",
        "",
        "### Customers and transactions",
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
        "The amount_usd summaries describe observed values only. USD transactions have a null amount_usd in this extract; amount stays separate per currency and amount_usd is not auto-filled. Features include per-customer count and observed monetary percentage.",
        "",
        _table(transaction_top, ["variable", "category", "records", "pct"]),
        "",
        "Income is shown by country without assuming currency or international equivalence. Balances and limits are segmented by currency. Per-month categories and sign-ups are in each domain's CSV.",
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
        "Session duration is the interval between the first and last observed event; a single event implies a zero interval, not a real zero duration.",
        "",
        "### Transcripts and surveys",
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
        "The *_selection_numeric/categories/monthly.csv tables compare both groups. Descriptive differences suggest selection; similarity in these variables does not prove absence of bias. CSAT, CES and NPS are kept separate; satisfaction features use only CSAT.",
        "",
        "### Complaints",
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
        "Nulls are evaluated by status. Resolution time aggregates use only dates <= cutoff; open_complaint_count stays NULL because a snapshot status does not reconstruct historical state. no_observed_resolution_by_cutoff_count is provided as a distinct observation, not as an equivalence to open.",
        "",
        "### Campaigns",
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
        "Marginal flags and the strict funnel are shown separately. A null date without conversion is not classified as a defect. conversion_value/send_cost currency is undocumented: sums are in original units, not equated to USD.",
        "",
        "### Exchange rates",
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
        "Both directions and formulas are checked using the exact calendar day, tolerance max(0.02 USD, 1% of amount_usd). The empirical fit is evidence of compatibility, not contractual confirmation of the units. Amounts are not corrected and no other day's rates are used.",
        "",
        "### Preliminary associations",
        "",
        _table(
            _read("cross_domain_associations.csv"),
            ["x", "y", "paired_customers", "pearson_raw", "spearman"],
        ),
        "",
        "Only customers with both observations; a missing domain stays NULL. These associations are not causal and may reflect exposure, selection or incoherent keys.",
        "",
        "## Data limitations",
        "",
        "- registration_branch_id and assigned_branch_id: unreliable relationships per profiling; excluded from geographic joins.",
        "- Complaints without origin_interaction_id; no observed link to the originating contact exists.",
        "- Anonymous digital events and sparse product_id; multi-customer sessions, if any, require review before linking sequences.",
        "- Transcripts and surveys have partial coverage; interactions include calls, chat, email and video.",
        "- last_updated is ambiguous; snapshot attributes (balance, segment, income, score and status) are not part of customer_360.",
        "- No availability/revision timestamps: features are EDA aggregates at cutoff, not point-in-time certification for models.",
        "- Extreme months/days may be partial; x2 or /2 changes are volume alerts, not automatic errors.",
        "- No personal text is exported; lengths/word counts are approximations by characters/space tokens.",
        "",
        "## Hypotheses",
        "",
        "- Explain the complaint-product mismatch before interpreting ownership and journeys between those domains.",
        "- Investigate continuity between anonymous and identified events within mixed sessions, without automatically attributing them at this stage.",
        "- Investigate the process calendar against events that cross midnight; confirm time zone and operational date.",
        "- Evaluate digital activity and service frequency while controlling for exposure and selection.",
        "- Examine wait and CSAT within comparable channels/reasons and with semantically valid links.",
        "- Confirm FX direction/units and session semantics with the data owners.",
        "- Determine how to represent complaints without an origin interaction, keeping hypothetical links separate.",
        "",
        "Stage 02 stops here. No journeys, modeling, embeddings or LLMs are run.",
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
