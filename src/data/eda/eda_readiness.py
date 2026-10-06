"""Semantic, branch, temporal and exchange-rate validation for EDA."""

from src.data.eda.eda_core import *


def semantic(con):
    result, examples = [], []
    specs = [
        (
            "transaction_product_customer",
            "transactions",
            "products",
            "transaction_id",
            "product_id",
            "product_id",
            "customer_id",
        ),
        (
            "transcript_customer",
            "call_transcripts",
            "call_center_interactions",
            "transcript_id",
            "interaction_id",
            "interaction_id",
            "customer_id",
        ),
        (
            "transcript_agent",
            "call_transcripts",
            "call_center_interactions",
            "transcript_id",
            "interaction_id",
            "interaction_id",
            "agent_id",
        ),
        (
            "survey_customer",
            "satisfaction_surveys",
            "call_center_interactions",
            "survey_id",
            "interaction_id",
            "interaction_id",
            "customer_id",
        ),
        (
            "survey_agent",
            "satisfaction_surveys",
            "call_center_interactions",
            "survey_id",
            "interaction_id",
            "interaction_id",
            "agent_id",
        ),
        (
            "complaint_product_customer",
            "complaints",
            "products",
            "complaint_id",
            "affected_product_id",
            "product_id",
            "customer_id",
        ),
    ]
    for label, child, parent, pk, fk, target, compare in specs:
        assert con.execute(
            f"SELECT count(*)=count(DISTINCT {target}) FROM {parent}"
        ).fetchone()[0]
        join = f"FROM {child} s LEFT JOIN {parent} p ON s.{fk}=p.{target}"
        eligible = f"s.{fk} IS NOT NULL"
        linked = f"{eligible} AND p.{target} IS NOT NULL"
        mismatch = f"{linked} AND s.{compare} IS DISTINCT FROM p.{compare}"
        a = rows(
            con,
            f"""SELECT count(*) total,count_if({eligible}) eligible,count_if({linked}) linked,
          count_if({eligible} AND p.{target} IS NULL) orphan,count_if({mismatch}) inconsistent,
          count_if({linked} AND s.{compare} IS NOT DISTINCT FROM p.{compare}) consistent {join}""",
        )[0]
        result.append(
            dict(
                validation=label,
                **a,
                consistent_pct=100 * a["consistent"] / a["eligible"]
                if a["eligible"]
                else None,
            )
        )
        examples.extend(
            rows(
                con,
                f"""SELECT '{label}' validation,substr(sha256(s.{pk}),1,16) record_hash,
          substr(sha256(s.{compare}),1,16) source_value_hash,substr(sha256(p.{compare}),1,16) target_value_hash
          {join} WHERE {mismatch} ORDER BY s.{pk} LIMIT 5""",
            )
        )
    save("semantic_validation.csv", result)
    save(
        "semantic_validation_examples.csv",
        examples,
        ["validation", "record_hash", "source_value_hash", "target_value_hash"],
    )
    report(
        con,
        "branch_validation.csv",
        """
      SELECT 'products.opening_branch_id' relation,count(*) total,count_if(p.opening_branch_id IS NULL) null_reference,
        count_if(b.branch_id IS NOT NULL) known,count_if(p.opening_branch_id IS NOT NULL AND b.branch_id IS NULL) orphan
      FROM products p LEFT JOIN branches b ON p.opening_branch_id=b.branch_id
      UNION ALL SELECT 'transactions.branch_id',count(*),count_if(t.branch_id IS NULL),
        count_if(b.branch_id IS NOT NULL),count_if(t.branch_id IS NOT NULL AND b.branch_id IS NULL)
      FROM transactions t LEFT JOIN branches b USING(branch_id)""",
    )
    log("Semantic readiness completed")
    return result


def temporal(con):
    coverage, delays, daily, partitions, gaps, changes = [], [], [], [], [], []
    for ds, event in EVENTS.items():
        basis = (
            "process_date only; no independent event timestamp"
            if ds == "call_transcripts"
            else event
        )
        r = rows(
            con,
            f"""SELECT min({event}::TIMESTAMP) min_timestamp,max({event}::TIMESTAMP) max_timestamp,
          min({event}::DATE) min_date,max({event}::DATE) max_date,count(DISTINCT {event}::DATE) active_days,
          date_diff('day',min({event}::DATE),max({event}::DATE))+1 calendar_days FROM {ds}""",
        )[0]
        coverage.append(
            dict(
                dataset=ds,
                basis=basis,
                **r,
                days_without_records=r["calendar_days"] - r["active_days"],
            )
        )
        daily.extend(
            rows(
                con,
                f"SELECT '{ds}' dataset,{event}::DATE AS day,count(*) records FROM {ds} GROUP BY 1,2 ORDER BY 2",
            )
        )
        if ds != "call_transcripts":
            delays.extend(
                rows(
                    con,
                    f"""SELECT '{ds}' dataset,count(*) total,
              count_if(process_date::DATE<{event}::DATE) processed_before_day,
              count_if(process_date::DATE={event}::DATE) processed_same_day,
              count_if(process_date::DATE>{event}::DATE) processed_after_day,
              count_if(date_diff('day',{event}::DATE,process_date::DATE)>1) potential_late_over_1d,
              min(date_diff('day',{event}::DATE,process_date::DATE)) min_lag_days,
              max(date_diff('day',{event}::DATE,process_date::DATE)) max_lag_days,
              median(date_diff('day',{event}::DATE,process_date::DATE)) median_lag_days,
              quantile_cont(date_diff('day',{event}::DATE,process_date::DATE),.95) p95_lag_days,
              median(epoch(process_date::TIMESTAMP-{event}::TIMESTAMP)/3600) nominal_median_hours
              FROM {ds}""",
                )
            )
        partitions.extend(
            rows(
                con,
                f"""WITH f AS (
          SELECT _source_file,try_strptime(regexp_extract(_source_file,'([0-9]{{8}})[.]csv$',1),'%Y%m%d')::DATE file_day,
            count(DISTINCT {event}::DATE) event_days,count(DISTINCT process_date::DATE) process_days,min(process_date::DATE) first_process,
            count_if({event}::DATE IS DISTINCT FROM try_strptime(regexp_extract(_source_file,'([0-9]{{8}})[.]csv$',1),'%Y%m%d')::DATE) off_file_day
          FROM {ds} GROUP BY 1,2)
          SELECT '{ds}' dataset,count(*) files,count(file_day) parseable_filenames,count(DISTINCT file_day) distinct_file_days,
            count_if(process_days=1 AND first_process=file_day) files_matching_process_day,
            count_if(event_days=1) files_with_single_event_day,sum(off_file_day) events_outside_filename_day FROM f""",
            )
        )
        gaps.extend(
            rows(
                con,
                f"""WITH bounds AS (SELECT min({event}::DATE) lo,max({event}::DATE) hi FROM {ds}),
          days AS (SELECT unnest(generate_series(lo,hi,INTERVAL 1 DAY))::DATE AS day FROM bounds)
          SELECT '{ds}' dataset,day FROM days ANTI JOIN (SELECT DISTINCT {event}::DATE AS day FROM {ds}) observed USING(day)""",
            )
        )
        changes.extend(
            rows(
                con,
                f"""WITH x AS (SELECT {event}::DATE AS day,count(*) n FROM {ds} GROUP BY 1),
          y AS (SELECT *,lag(n) OVER(ORDER BY day) previous_n FROM x)
          SELECT '{ds}' dataset,day,n,previous_n,n::DOUBLE/previous_n ratio,
            CASE WHEN day=(SELECT min(day) FROM x) OR day=(SELECT max(day) FROM x) THEN 'boundary' ELSE 'interior' END AS position
          FROM y WHERE previous_n>0 AND (n::DOUBLE/previous_n>=2 OR n::DOUBLE/previous_n<=.5) ORDER BY day""",
            )
        )
    save("temporal_coverage.csv", coverage)
    save("temporal_delays.csv", delays)
    save("coverage_daily.csv", daily)
    save("partition_day_check.csv", partitions)
    save("temporal_gaps.csv", gaps, ["dataset", "day"])
    save(
        "abrupt_volume_changes.csv",
        changes,
        ["dataset", "day", "n", "previous_n", "ratio", "position"],
    )
    totals = {}
    for r in daily:
        k = (r["dataset"], str(r["day"])[:7])
        totals[k] = totals.get(k, 0) + r["records"]
    save(
        "coverage_monthly.csv",
        [dict(dataset=k[0], month=k[1], records=v) for k, v in sorted(totals.items())],
    )
    lifecycle = []
    for ds, fields in {
        "complaints": [
            "assignment_date",
            "first_response_date",
            "resolution_date",
            "closing_date",
        ],
        "campaign_sends": ["open_date", "click_date", "conversion_date"],
    }.items():
        for col in fields:
            lifecycle.extend(
                rows(
                    con,
                    f"SELECT '{ds}' dataset,'{col}' field,min({col}::TIMESTAMP) min_timestamp,max({col}::TIMESTAMP) max_timestamp,count({col}) observed FROM {ds}",
                )
            )
    save("lifecycle_windows.csv", lifecycle)
    log("Temporal readiness completed")
    dimensions = []
    for ds, col in {
        "customers": "registration_date",
        "products": "opening_date",
        "branches": "branch_opening_date",
        "service_agents": "hire_date",
        "marketing_campaigns": "start_date",
        "daily_exchange_rates": "date",
    }.items():
        dimensions.extend(
            rows(
                con,
                f"""SELECT '{ds}' dataset,'{col}' date_basis,min({col}::DATE) min_date,
          max({col}::DATE) max_date,count(DISTINCT {col}::DATE) active_days,
          date_diff('day',min({col}::DATE),max({col}::DATE))+1 calendar_days,
          date_diff('day',min({col}::DATE),max({col}::DATE))+1-count(DISTINCT {col}::DATE) days_without_records
          FROM {ds}""",
            )
        )
    save("dimension_date_windows.csv", dimensions)
    return coverage


def exchange(con):
    report(
        con,
        "exchange_rate_pairs.csv",
        """SELECT source_currency,target_currency,count(*) rates,
      min(exchange_rate::DOUBLE) minimum,median(exchange_rate::DOUBLE) median,max(exchange_rate::DOUBLE) maximum
      FROM daily_exchange_rates GROUP BY 1,2 ORDER BY 1,2""",
    )
    assert con.execute(
        "SELECT count(*)=count(DISTINCT (date,source_currency,target_currency)) FROM daily_exchange_rates"
    ).fetchone()[0]
    # Compare both directions and formulas without assuming units. Exact date only.
    con.execute("""CREATE OR REPLACE TEMP VIEW fx_candidates AS
      SELECT t.transaction_id,t.currency,t.amount::DOUBLE amount,t.amount_usd::DOUBLE amount_usd,
        CASE WHEN r.source_currency=t.currency THEN 'currency_to_USD' ELSE 'USD_to_currency' END pair_direction,
        r.exchange_rate::DOUBLE rate
      FROM transactions t JOIN daily_exchange_rates r ON t.transaction_date::DATE=r.date::DATE
        AND ((r.source_currency=t.currency AND r.target_currency='USD')
          OR (r.source_currency='USD' AND r.target_currency=t.currency))
      WHERE t.currency<>'USD'""")
    results = []
    for operation, expr in [
        ("multiply", "amount*rate"),
        ("divide", "amount/nullif(rate,0)"),
    ]:
        results.extend(
            rows(
                con,
                f"""SELECT currency,pair_direction,'{operation}' operation,count(*) AS matched,
          count_if(amount IS NOT NULL AND amount_usd IS NOT NULL AND rate>0) eligible_amounts,
          count_if(abs({expr}-amount_usd)<=greatest(.02,abs(amount_usd)*.01)) within_tolerance,
          100.*count_if(rate>0 AND abs({expr}-amount_usd)<=greatest(.02,abs(amount_usd)*.01))/
            nullif(count_if(amount IS NOT NULL AND amount_usd IS NOT NULL AND rate>0),0) within_tolerance_pct,
          median(abs({expr}-amount_usd)/nullif(abs(amount_usd),0)) median_relative_error,
          quantile_cont(abs({expr}-amount_usd)/nullif(abs(amount_usd),0),.95) p95_relative_error
          FROM fx_candidates GROUP BY 1,2""",
            )
        )
    save("exchange_rate_validation.csv", results)
    report(
        con,
        "exchange_rate_coverage.csv",
        """SELECT currency,count(*) transactions,count(amount_usd) amount_usd_observed,
      100.*count(amount_usd)/count(*) amount_usd_coverage_pct,
      count_if(currency='USD' AND abs(amount::DOUBLE-amount_usd::DOUBLE)<=greatest(.02,abs(amount_usd::DOUBLE)*.01)) usd_identity_matches,
      count_if(currency<>'USD' AND NOT EXISTS(SELECT 1 FROM daily_exchange_rates r WHERE r.date::DATE=t.transaction_date::DATE
        AND ((r.source_currency=t.currency AND r.target_currency='USD') OR (r.source_currency='USD' AND r.target_currency=t.currency)))) missing_exact_date_rate
      FROM transactions t GROUP BY currency""",
    )
    return results
