"""Descriptive domain analyses and independent customer aggregates."""
from src.eda_core import *


def cutoff(ctx):
    return "DATE "+literal(ctx["feature_cutoff_inclusive"])

def feature(con,name,query):
    con.execute(f"CREATE OR REPLACE TABLE {name} AS {query}")
    assert con.execute(f"SELECT count(*)=count(DISTINCT customer_id) AND count(*)=count(customer_id) FROM {name}").fetchone()[0]
    export(con,name,f"SELECT * FROM {name}")

def monthly(con,table,col,name):
    return report(con,name,f"SELECT date_trunc('month',{col}::TIMESTAMP)::DATE AS month,count(*) records FROM {table} GROUP BY 1 ORDER BY 1")

def customers_products(con,ctx):
    ref=cutoff(ctx)
    con.execute(f"""CREATE OR REPLACE TEMP VIEW customer_age AS SELECT *,
      date_diff('year',date_of_birth::DATE,{ref})-
      CASE WHEN strftime({ref},'%m%d')<strftime(date_of_birth::DATE,'%m%d') THEN 1 ELSE 0 END age FROM customers""")
    numeric(con,"customer_age",["age","credit_score"],"customer_numeric.csv")
    numeric(con,"customers",["estimated_monthly_income"],"customer_income_by_country.csv","country")
    categories(con,"customers",["country","state","city","segment","customer_status","gender","occupation"],"customer_categories.csv")
    report(con,"customer_age_bands.csv","SELECT floor(age/10)*10 age_band,count(*) customers FROM customer_age GROUP BY 1 ORDER BY 1")
    monthly(con,"customers","registration_date","customer_registrations.csv")
    categories(con,"products",["product_type","product_status","currency","opening_channel"],"product_categories.csv")
    numeric(con,"products",["current_balance","credit_limit"],"product_money_by_currency.csv","currency")
    numeric(con,"products",["days_past_due","interest_rate"],"product_numeric.csv")
    report(con,"product_date_ranges.csv","""SELECT min(opening_date::DATE) earliest_opening,max(opening_date::DATE) latest_opening,
      min(last_transaction_date::TIMESTAMP) earliest_last_transaction,max(last_transaction_date::TIMESTAMP) latest_last_transaction,
      count_if(last_transaction_date IS NULL) no_last_transaction FROM products""")
    monthly(con,"products","opening_date","product_openings.csv")
    report(con,"products_per_customer.csv","""SELECT count(*) customers,median(n) median_products,
      quantile_cont(n,.9) p90,quantile_cont(n,.95) p95,quantile_cont(n,.99) p99,max(n) maximum
      FROM (SELECT c.customer_id,count(p.product_id) n FROM customers c LEFT JOIN products p USING(customer_id) GROUP BY 1)""")
    # Only dated openings enter features. Balances/status are undated snapshot attributes.
    feature(con,"products_customer_features",f"""SELECT customer_id,count(*) product_count,
      count(DISTINCT product_type) product_type_count FROM products WHERE opening_date::DATE<={ref} GROUP BY 1""")
    log("Clientes y productos completados")


def transactions(con,ctx):
    categories(con,"transactions",["transaction_type","transaction_category","channel","transaction_status","currency","merchant_category"],"transaction_categories.csv")
    numeric(con,"transactions",["amount_usd","fraud_score"],"transaction_numeric.csv")
    numeric(con,"transactions",["amount"],"transaction_amount_by_currency.csv","currency")
    report(con,"transaction_merchant_coverage.csv","""SELECT count(*) transactions,count(merchant_name) merchant_known,
      count(merchant_category) category_known,count(DISTINCT merchant_name) distinct_merchants FROM transactions""")
    report(con,"transaction_top_merchants.csv","""SELECT merchant_name,count(*) transactions,
      median(amount_usd::DOUBLE) median_usd,sum(amount_usd::DOUBLE) total_usd FROM transactions
      WHERE merchant_name IS NOT NULL GROUP BY 1 ORDER BY transactions DESC,merchant_name LIMIT 30""")
    for key in ("customer_id","product_id"):
        report(con,"transactions_per_"+key+".csv",f"""SELECT count(*) active_entities,median(n) median,
          quantile_cont(n,.9) p90,quantile_cont(n,.95) p95,quantile_cont(n,.99) p99,max(n) maximum
          FROM (SELECT {key},count(*) n FROM transactions GROUP BY 1)""")
    report(con,"amount_usd_histogram.csv","""SELECT CASE WHEN amount_usd::DOUBLE>0 THEN 'positive'
      WHEN amount_usd::DOUBLE=0 THEN 'zero' WHEN amount_usd IS NULL THEN 'missing' ELSE 'negative' END sign,
      CASE WHEN abs(amount_usd::DOUBLE)>0 THEN floor(log10(abs(amount_usd::DOUBLE))*10)/10 END log10_bin,
      count(*) records FROM transactions GROUP BY 1,2 ORDER BY 1,2""")
    feature(con,"transactions_customer_features",f"""SELECT customer_id,count(*) transaction_count,
      count(amount_usd) transaction_amount_usd_observed_count,
      100.*count(amount_usd)/count(*) transaction_amount_usd_coverage_pct,
      sum(amount_usd::DOUBLE) transaction_amount_usd_sum,avg(amount_usd::DOUBLE) transaction_amount_usd_mean,
      median(amount_usd::DOUBLE) transaction_amount_usd_median,quantile_cont(amount_usd::DOUBLE,.95) transaction_amount_usd_p95,
      count(DISTINCT product_id) distinct_products_transacted,max(fraud_score::DOUBLE) fraud_score_max,
      count(DISTINCT transaction_date::DATE) active_transaction_days FROM transactions
      WHERE transaction_date::DATE<={cutoff(ctx)} GROUP BY 1""")
    log("Transacciones completadas")


def digital(con,ctx):
    report(con,"digital_coverage.csv","""SELECT count(*) events,count(customer_id) identified,
      count(*)-count(customer_id) anonymous,100.*count(customer_id)/count(*) identified_pct,
      100.*(count(*)-count(customer_id))/count(*) anonymous_pct,count(DISTINCT customer_id) identified_customers,
      count(product_id) product_known,100.*count(product_id)/count(*) product_known_pct,count(session_id) session_known
      FROM digital_events""")
    for label,condition in (("identified","customer_id IS NOT NULL"),("anonymous","customer_id IS NULL")):
        categories(con,"digital_events",["event_type","event_category","channel","platform","browser","is_mobile"],
                   "digital_"+label+"_categories.csv",condition)
    report(con,"digital_events_per_customer.csv","""SELECT count(*) identified_customers,median(n) median,
      quantile_cont(n,.9) p90,quantile_cont(n,.95) p95,quantile_cont(n,.99) p99,max(n) maximum
      FROM (SELECT customer_id,count(*) n FROM digital_events WHERE customer_id IS NOT NULL GROUP BY 1)""")
    con.execute("""CREATE OR REPLACE TABLE eda_sessions AS SELECT session_id,count(*) events,
      count(DISTINCT customer_id) identified_customers,count_if(customer_id IS NULL) anonymous_events,
      epoch(max(event_date::TIMESTAMP)-min(event_date::TIMESTAMP)) observed_span_seconds
      FROM digital_events WHERE session_id IS NOT NULL GROUP BY session_id""")
    numeric(con,"eda_sessions",["events","observed_span_seconds","identified_customers"],"digital_sessions_numeric.csv")
    report(con,"digital_sessions_quality.csv","""SELECT count(*) sessions,count_if(events=1) singleton_sessions,
      count_if(identified_customers>1) multi_customer_sessions,count_if(identified_customers=0) anonymous_only_sessions,
      count_if(identified_customers>0 AND anonymous_events>0) mixed_identity_sessions FROM eda_sessions""")
    con.execute("DROP TABLE eda_sessions")
    feature(con,"digital_customer_features",f"""SELECT customer_id,count(*) digital_event_count,
      count(DISTINCT event_date::DATE) digital_active_days,count(DISTINCT session_id) session_count,
      count(DISTINCT event_type) distinct_event_types FROM digital_events
      WHERE customer_id IS NOT NULL AND event_date::DATE<={cutoff(ctx)} GROUP BY 1""")
    log("Digital identificado, anónimo y sesiones completados")


def service(con,ctx):
    categories(con,"call_center_interactions",["interaction_type","contact_reason","reason_category","channel","agent_id",
      "was_resolved","requires_followup","was_escalated","detected_sentiment"],"service_categories.csv")
    numeric(con,"call_center_interactions",["duration_seconds","wait_time_seconds","sentiment_score"],"service_numeric.csv")
    hist=[]
    for col,width in (("duration_seconds",120),("wait_time_seconds",30)):
        hist.extend(rows(con,f"SELECT '{col}' AS variable,floor({col}::DOUBLE/{width})*{width} lower_seconds,count(*) records FROM call_center_interactions GROUP BY 2 ORDER BY 2"))
    save("service_histograms.csv",hist)
    report(con,"service_per_customer.csv","""SELECT count(*) customers,median(n) median_interactions,
      quantile_cont(n,.95) p95_interactions,max(n) maximum FROM (
      SELECT customer_id,count(*) n FROM call_center_interactions GROUP BY 1)""")
    feature(con,"call_customer_features",f"""SELECT customer_id,count(*) interaction_count,
      avg(wait_time_seconds::DOUBLE) avg_wait_time,median(wait_time_seconds::DOUBLE) median_wait_time,
      avg(duration_seconds::DOUBLE) avg_duration,count(DISTINCT agent_id) distinct_agents,
      count_if(detected_sentiment IN ('Negativo','Muy Negativo')) negative_sentiment_interactions
      FROM call_center_interactions WHERE interaction_date::DATE<={cutoff(ctx)} GROUP BY 1""")
    log("Interacciones de servicio completadas")


def selection(con,table,prefix):
    # EXISTS keeps the parent denominator stable even if the child relation is nonunique.
    con.execute(f"""CREATE OR REPLACE TEMP VIEW selected_calls AS SELECT i.*,
      EXISTS(SELECT 1 FROM {table} x WHERE x.interaction_id=i.interaction_id) has_child
      FROM call_center_interactions i""")
    coverage=report(con,prefix+"_coverage.csv",f"""SELECT count(*) n_interactions,
      count_if(has_child) n_interactions_with_{prefix},100.*count_if(has_child)/count(*) interaction_coverage_pct,
      count_if(interaction_type IN ('Inbound Call','Outbound Call')) n_calls,
      count_if(has_child AND interaction_type IN ('Inbound Call','Outbound Call')) n_calls_with_{prefix},
      100.*count_if(has_child AND interaction_type IN ('Inbound Call','Outbound Call'))/
        nullif(count_if(interaction_type IN ('Inbound Call','Outbound Call')),0) call_coverage_pct,
      (SELECT count(*) FROM {table}) child_rows FROM selected_calls""")
    numeric(con,"selected_calls",["duration_seconds","wait_time_seconds","sentiment_score"],prefix+"_selection_numeric.csv","has_child")
    cat=[]
    for col in ("contact_reason","channel","detected_sentiment","agent_id","interaction_type"):
        cat.extend(rows(con,f"""SELECT '{col}' AS variable,{ident(col)} category,count(*) interactions,
          count_if(has_child) with_child,100.*count_if(has_child)/count(*) coverage_pct,
          100.*count_if(has_child)/nullif(sum(count_if(has_child)) OVER(),0) pct_with_group,
          100.*count_if(NOT has_child)/nullif(sum(count_if(NOT has_child)) OVER(),0) pct_without_group
          FROM selected_calls GROUP BY {ident(col)} ORDER BY interactions DESC"""))
    save(prefix+"_selection_categories.csv",cat)
    report(con,prefix+"_selection_monthly.csv","""SELECT date_trunc('month',interaction_date::TIMESTAMP)::DATE AS month,
      count(*) interactions,count_if(has_child) with_child,100.*count_if(has_child)/count(*) coverage_pct
      FROM selected_calls GROUP BY 1 ORDER BY 1""")
    return coverage


def transcripts(con):
    coverage=selection(con,"call_transcripts","transcript")
    con.execute("""CREATE OR REPLACE TEMP VIEW transcript_lengths AS SELECT length(full_text) chars,
      CASE WHEN full_text IS NULL THEN NULL WHEN trim(full_text)='' THEN 0
        ELSE len(regexp_split_to_array(trim(full_text),'\\s+')) END words FROM call_transcripts""")
    numeric(con,"transcript_lengths",["chars","words"],"transcript_text_lengths.csv")
    report(con,"transcript_length_histogram.csv","SELECT floor(chars/200)*200 lower_chars,count(*) records FROM transcript_lengths GROUP BY 1 ORDER BY 1")
    log("Cobertura y selección de transcripts completadas")
    return coverage


def complaints(con,ctx):
    categories(con,"complaints",["case_type","category","subcategory","reception_channel","priority","status",
      "assigned_agent_id","sla_breached","is_repeat_complainer"],"complaint_categories.csv")
    report(con,"complaint_conditional_nulls.csv","""SELECT status,count(*) records,
      count_if(assignment_date IS NULL) assignment_null,count_if(first_response_date IS NULL) first_response_null,
      count_if(resolution_date IS NULL) resolution_null,count_if(closing_date IS NULL) closing_null,
      100.*count_if(resolution_date IS NULL)/count(*) resolution_null_pct,
      100.*count_if(closing_date IS NULL)/count(*) closing_null_pct,
      count_if(origin_interaction_id IS NULL) origin_interaction_null FROM complaints GROUP BY status ORDER BY status""")
    numeric(con,"complaints",["resolution_days"],"complaint_resolution_by_status.csv","status")
    numeric(con,"complaints",["claimed_amount","compensation_granted"],"complaint_money_by_currency.csv","currency")
    lifecycle=[]
    for col in ("assignment_date","first_response_date","resolution_date","closing_date"):
        lifecycle.extend(rows(con,f"""SELECT '{col}' milestone,status,count({col}) observed,
          count_if({col}::TIMESTAMP<creation_date::TIMESTAMP) before_creation,
          median(epoch({col}::TIMESTAMP-creation_date::TIMESTAMP)/3600) median_hours,
          quantile_cont(epoch({col}::TIMESTAMP-creation_date::TIMESTAMP)/3600,.95) p95_hours
          FROM complaints GROUP BY status"""))
    save("complaint_lifecycle.csv",lifecycle)
    for key in ("customer_id","affected_product_id"):
        report(con,"complaints_per_"+key+".csv",f"""SELECT count(*) entities,median(n) median,
          quantile_cont(n,.95) p95,max(n) maximum FROM (
          SELECT {key},count(*) n FROM complaints WHERE {key} IS NOT NULL GROUP BY 1)""")
    ref=cutoff(ctx)
    # Open status cannot be reconstructed as-of from an undated status snapshot.
    feature(con,"complaint_customer_features",f"""SELECT customer_id,count(*) complaint_count,
      NULL::BIGINT open_complaint_count,
      count_if(resolution_date IS NULL OR resolution_date::DATE>{ref}) no_observed_resolution_by_cutoff_count,
      count_if(resolution_date::DATE<={ref}) resolved_complaint_count,
      avg(epoch(resolution_date::TIMESTAMP-creation_date::TIMESTAMP)/86400)
        FILTER(WHERE resolution_date::DATE<={ref}) avg_resolution_days
      FROM complaints WHERE creation_date::DATE<={ref} GROUP BY 1""")
    log("Reclamos y nulos condicionales completados")


def satisfaction(con,ctx):
    coverage=selection(con,"satisfaction_surveys","survey")
    numeric(con,"satisfaction_surveys",["main_score"],"survey_scores_by_type.csv","survey_type")
    report(con,"survey_score_distribution.csv","SELECT survey_type,main_score,count(*) responses FROM satisfaction_surveys GROUP BY 1,2 ORDER BY 1,try_cast(main_score AS DOUBLE)")
    questions=[]
    for i in (1,2,3):
        questions.extend(rows(con,f"""SELECT {i} question,survey_type,question_{i}_text question_text,
          question_{i}_response response,count(*) records FROM satisfaction_surveys GROUP BY 1,2,3,4 ORDER BY 2,3,4"""))
    save("survey_questions.csv",questions)
    comparisons=[]
    for col in ("contact_reason","channel","agent_id"):
        comparisons.extend(rows(con,f"""SELECT '{col}' AS variable,i.{col} category,s.survey_type,count(*) responses,
          median(s.main_score::DOUBLE) median_score,avg(s.main_score::DOUBLE) mean_score
          FROM satisfaction_surveys s JOIN call_center_interactions i USING(interaction_id)
          WHERE s.customer_id=i.customer_id AND s.agent_id=i.agent_id
          GROUP BY 1,2,3"""))
    save("survey_scores_by_interaction.csv",comparisons)
    ref=cutoff(ctx)
    feature(con,"survey_customer_features",f"""SELECT customer_id,count(*) survey_count,
      count_if(survey_type='CSAT') csat_count,
      avg(main_score::DOUBLE) FILTER(WHERE survey_type='CSAT') avg_satisfaction,
      first(main_score::DOUBLE ORDER BY survey_date::TIMESTAMP DESC,survey_id DESC)
        FILTER(WHERE survey_type='CSAT') latest_satisfaction
      FROM satisfaction_surveys WHERE survey_date::DATE<={ref} GROUP BY 1""")
    log("Encuestas por escala y selección completadas")
    return coverage


def campaigns(con,ctx):
    categories(con,"marketing_campaigns",["campaign_type","campaign_objective","promoted_product","target_segment",
      "target_country","campaign_status"],"campaign_categories.csv")
    report(con,"campaign_dimension_summary.csv","""SELECT count(*) campaigns,min(start_date::DATE) first_start,
      max(end_date::DATE) last_planned_end,median(budget::DOUBLE) median_budget_currency_unspecified
      FROM marketing_campaigns""")
    report(con,"campaign_funnel.csv","""SELECT count(*) sent,
      count_if(was_delivered::BOOLEAN) delivered,count_if(was_opened::BOOLEAN) opened,
      count_if(was_clicked::BOOLEAN) clicked,count_if(had_conversion::BOOLEAN) converted,
      count_if(was_delivered::BOOLEAN AND was_opened::BOOLEAN AND was_clicked::BOOLEAN AND had_conversion::BOOLEAN) strict_full_funnel,
      sum(conversion_value::DOUBLE) conversion_value_sum_currency_unspecified,
      sum(send_cost::DOUBLE) send_cost_sum_currency_unspecified,
      count_if(was_opened::BOOLEAN AND NOT coalesce(was_delivered::BOOLEAN,false)) opened_without_delivered,
      count_if(was_clicked::BOOLEAN AND NOT coalesce(was_opened::BOOLEAN,false)) clicked_without_opened,
      count_if(had_conversion::BOOLEAN AND NOT coalesce(was_clicked::BOOLEAN,false)) converted_without_clicked,
      count_if(had_conversion::BOOLEAN AND conversion_date IS NULL) converted_missing_date,
      count_if(NOT had_conversion::BOOLEAN AND conversion_date IS NOT NULL) nonconverted_with_date,
      count_if(NOT had_conversion::BOOLEAN AND conversion_date IS NULL) nonconverted_without_date
      FROM campaign_sends""")
    report(con,"campaign_performance.csv","""SELECT campaign_id,send_channel,count(*) sends,
      count_if(was_delivered::BOOLEAN) delivered,count_if(was_opened::BOOLEAN) opens,
      count_if(was_clicked::BOOLEAN) clicks,count_if(had_conversion::BOOLEAN) conversions
      FROM campaign_sends GROUP BY 1,2""")
    ref=cutoff(ctx)
    feature(con,"campaign_customer_features",f"""SELECT customer_id,count(*) sends,
      count_if(was_opened::BOOLEAN AND open_date::DATE<={ref}) opens,
      count_if(was_clicked::BOOLEAN AND click_date::DATE<={ref}) clicks,
      count_if(had_conversion::BOOLEAN AND conversion_date::DATE<={ref}) conversions
      FROM campaign_sends WHERE send_date::DATE<={ref} GROUP BY 1""")
    log("Campañas y coherencia del funnel completadas")


def branches(con):
    report(con,"branch_geography.csv","""SELECT 'products' dataset,
      CASE WHEN b.branch_id IS NULL THEN 'unknown' ELSE 'known' END branch_coverage,b.country,b.city,count(*) records
      FROM products p LEFT JOIN branches b ON p.opening_branch_id=b.branch_id GROUP BY 1,2,3,4
      UNION ALL SELECT 'transactions',CASE WHEN b.branch_id IS NULL THEN 'unknown' ELSE 'known' END,b.country,b.city,count(*)
      FROM transactions t LEFT JOIN branches b USING(branch_id) GROUP BY 1,2,3,4""")
    # Existing profiling findings are documentation, not used as geographic join paths.
    save("branch_relationship_limitations.csv",[
      {"relation":"customers.registration_branch_id -> branches.branch_id","nonnull":150000,"unmatched":149995,"use":"excluded; existing profiling"},
      {"relation":"service_agents.assigned_branch_id -> branches.branch_id","nonnull":833,"unmatched":831,"use":"excluded; existing profiling"}])
