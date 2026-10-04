"""Independent context aggregates around candidate transactions, not causal links."""

from src.data.workflows.dispute_workflow_data import ART, query, save, export, log
from src.data.eda.dispute_eda import present, stats
from src.data.data_utils import ident, literal
from src.data.eda.eda_core import rows


def characteristics(con):
    result = []
    fields = {
        "transaction_type": "transaction_type",
        "transaction_status": "transaction_status",
        "channel": "channel",
        "transaction_category": "transaction_category",
        "merchant_available": f"cast({present('merchant_name')} AS VARCHAR)",
        "response_code": "response_code",
        "is_fraud": "is_fraud",
        "fraud_score_available": "cast(fraud_score IS NOT NULL AS VARCHAR)",
        "transaction_country": "transaction_country",
        "merchant_category": "merchant_category",
    }
    for population, table in [
        ("all_cutoff_transactions", "tx"),
        ("same_customer_history_before_last_complaint", "historical_population"),
        ("unique_candidates_plus_minus_30d", "candidates"),
    ]:
        for field, expr in fields.items():
            result += rows(
                con,
                f"""SELECT '{population}' AS population,'{field}' AS field,
              {expr} AS value,count(*) AS records,
              100.*count(*)/sum(count(*)) OVER() AS pct_population,
              count(fraud_recorded) AS valid_recorded_labels,
              count_if(fraud_recorded) AS fraud_recorded_count,
              100.*count_if(fraud_recorded)/nullif(count(fraud_recorded),0) AS recorded_fraud_pct
              FROM {table} GROUP BY 3 ORDER BY 3 NULLS LAST""",
            )
    save("candidate_transaction_characteristics.csv", result)
    save(
        "fraud_signal_without_score.csv",
        [r for r in result if r["field"] not in {"fraud_score_available", "is_fraud"}],
    )
    money = []
    for population, table in [
        ("all_cutoff_transactions", "tx"),
        ("unique_candidates_plus_minus_30d", "candidates"),
    ]:
        money += rows(
            con,
            f"""SELECT '{population}' AS population,currency,is_fraud,count(*) AS records,
          {stats("amount")} FROM {table} WHERE currency IS NOT NULL GROUP BY 2,3 ORDER BY 2,3""",
        )
    save("fraud_amount_without_score_by_currency.csv", money)
    log("5,7. Distribuciones comparables y señal descriptiva sin usar fraud_score")


def behavior(con):
    # Range join only candidate customers, strictly earlier timestamp. No event/event mega-join.
    con.execute("""CREATE TABLE prior_pairs AS SELECT t.transaction_id,
      h.transaction_id AS historical_id,h.tx_time AS history_time,
      epoch(t.tx_time-h.tx_time)/86400. AS age_days,
      h.amount AS historical_amount,h.currency=t.currency AS same_currency,
      h.channel=t.channel AS same_channel,h.transaction_type=t.transaction_type AS same_type,
      h.merchant_name=t.merchant_name AS same_merchant,
      h.transaction_status AS historical_status
      FROM candidates t JOIN tx h ON h.customer_id=t.customer_id
        AND h.tx_time<t.tx_time AND h.tx_time>=t.tx_time-INTERVAL '90 days'""")
    assert (
        con.execute(
            "SELECT count(*) FROM prior_pairs WHERE age_days<=0 OR age_days>90"
        ).fetchone()[0]
        == 0
    )
    con.execute("""CREATE TABLE behavior_features AS SELECT t.transaction_id,t.currency,
      t.tx_time>= (SELECT min(tx_time) FROM tx)+INTERVAL '7 days' AS complete_prior_7d,
      t.tx_time>= (SELECT min(tx_time) FROM tx)+INTERVAL '30 days' AS complete_prior_30d,
      t.tx_time>= (SELECT min(tx_time) FROM tx)+INTERVAL '90 days' AS complete_prior_90d,
      count(p.historical_id) FILTER(WHERE age_days<=7) AS customer_transaction_count_prior_7d,
      count(p.historical_id) FILTER(WHERE age_days<=30) AS customer_transaction_count_prior_30d,
      count(p.historical_id) AS customer_transaction_count_prior_90d,
      median(p.historical_amount) FILTER(WHERE age_days<=30 AND same_currency) AS median_amount_prior_30d,
      median(p.historical_amount) FILTER(WHERE same_currency) AS median_amount_prior_90d,
      count(p.historical_id) FILTER(WHERE same_channel) AS same_channel_count_prior_90d,
      count(p.historical_id) FILTER(WHERE same_type) AS same_transaction_type_count_prior_90d,
      CASE WHEN t.merchant_name IS NOT NULL THEN count(p.historical_id) FILTER(WHERE same_merchant)
        ELSE NULL END AS same_merchant_count_prior_90d,
      count(p.historical_id) FILTER(WHERE age_days<=30 AND historical_status='Declined') AS prior_declined_count_30d,
      count(p.historical_id) FILTER(WHERE age_days<=30 AND historical_status='Reversed') AS prior_reversed_count_30d
      FROM candidates t LEFT JOIN prior_pairs p USING(transaction_id)
      GROUP BY t.transaction_id,t.currency,t.tx_time,t.merchant_name""")
    specs = [
        ("customer_transaction_count_prior_7d", 7, "Activity frequency", "recommended"),
        (
            "customer_transaction_count_prior_30d",
            30,
            "Activity frequency",
            "recommended",
        ),
        (
            "customer_transaction_count_prior_90d",
            90,
            "Activity frequency",
            "recommended",
        ),
        (
            "median_amount_prior_30d",
            30,
            "Same-currency historical amount only",
            "recommended",
        ),
        (
            "median_amount_prior_90d",
            90,
            "Same-currency historical amount only",
            "recommended",
        ),
        (
            "same_channel_count_prior_90d",
            90,
            "Familiarity with recorded channel",
            "recommended",
        ),
        (
            "same_transaction_type_count_prior_90d",
            90,
            "Familiarity with recorded type",
            "recommended",
        ),
        (
            "same_merchant_count_prior_90d",
            90,
            "Exact observed merchant string; not verified merchant identity",
            "optional",
        ),
        (
            "prior_declined_count_30d",
            30,
            "Earlier events with current recorded status; status revisions unknown",
            "optional",
        ),
        (
            "prior_reversed_count_30d",
            30,
            "Earlier events with current recorded status; status revisions unknown",
            "optional",
        ),
    ]
    result, distributions = [], []
    for field, days, meaning, recommendation in specs:
        r = rows(
            con,
            f"""SELECT '{field}' AS feature,count(*) AS candidate_transactions,
          count({ident(field)}) AS computable_count,
          100.*count({ident(field)})/count(*) AS computable_pct,
          count_if(complete_prior_{days}d) AS complete_history_window_count,
          count(*) FILTER(WHERE complete_prior_{days}d AND {ident(field)} IS NOT NULL) AS computable_complete_window_count,
          count_if({ident(field)}=0) AS observed_zero_count
          FROM behavior_features""",
        )[0]
        r.update(
            business_interpretation=meaning,
            recommendation=recommendation,
            computability="Exact event-time range aggregate; count=0 is observed absence, not imputation",
            leakage_risk="Strictly prior events only; availability/revision times unknown. Status counts especially unsafe as frozen-time predictors.",
            classification="DERIVED FEATURE feasibility, not production/model feature",
        )
        result.append(r)
        # Amount medians are always stratified by currency, including fraud comparisons.
        distributions += rows(
            con,
            f"""SELECT '{field}' AS feature,b.currency,t.is_fraud,
          b.complete_prior_{days}d AS complete_history_window,count(*) AS candidates,
          count(b.{ident(field)}) AS observed,{stats("b." + ident(field))}
          FROM behavior_features b JOIN candidates t USING(transaction_id)
          GROUP BY 2,3,4 ORDER BY 2,3,4""",
        )
    save("behavioral_feature_feasibility.csv", result)
    save("fraud_prior_behavior_without_score.csv", distributions)
    export(
        con, "candidate_behavioral_context.parquet", "SELECT * FROM behavior_features"
    )
    log("6–7. Contexto estrictamente anterior; censura de 7/30/90 días explícita")


def service(con):
    con.execute("""CREATE TABLE service_pairs AS SELECT t.transaction_id,c.interaction_id,
      c.call_time,epoch(c.call_time-t.tx_time)/3600. AS delay_hours,
      CASE WHEN c.call_time<=t.tx_time+INTERVAL '24 hours' THEN '0_24h'
           WHEN c.call_time<=t.tx_time+INTERVAL '3 days' THEN '1_3d'
           WHEN c.call_time<=t.tx_time+INTERVAL '7 days' THEN '3_7d'
           ELSE '7_14d' END AS time_window
      FROM candidates t JOIN calls c ON t.customer_id=c.customer_id
       AND c.call_time>=t.tx_time AND c.call_time<=t.tx_time+INTERVAL '14 days'""")
    summaries, distributions = [], []
    for window, hours in [("0_24h", 24), ("1_3d", 72), ("3_7d", 168), ("7_14d", 336)]:
        summaries += rows(
            con,
            f"""SELECT '{window}' AS time_window,
          (SELECT count(*) FROM candidates) AS candidate_transactions,
          (SELECT count(*) FROM candidates WHERE tx_time>=(SELECT min(call_time) FROM calls)
            AND tx_time+INTERVAL '{hours} hours'<=(SELECT max(call_time) FROM calls)) AS fully_observed_window_transactions,
          count(DISTINCT p.transaction_id) AS transactions_with_interaction,
          100.*count(DISTINCT p.transaction_id)/(SELECT count(*) FROM candidates) AS transaction_coverage_pct,
          count(*) AS transaction_interaction_pairs,count(DISTINCT p.interaction_id) AS distinct_interactions,
          count(c.escalated_recorded) AS escalation_valid_pair_labels,
          count_if(c.escalated_recorded) AS escalated_pairs,
          100.*count_if(c.escalated_recorded)/nullif(count(c.escalated_recorded),0) AS escalation_pct_pairs,
          count(c.resolved_recorded) AS resolution_valid_pair_labels,
          count_if(c.resolved_recorded) AS resolved_pairs,
          100.*count_if(c.resolved_recorded)/nullif(count(c.resolved_recorded),0) AS resolution_pct_pairs
          FROM service_pairs p JOIN calls c USING(interaction_id) WHERE time_window='{window}'""",
        )
        for field in (
            "reason_category",
            "contact_reason",
            "interaction_type",
            "channel",
        ):
            distributions += rows(
                con,
                f"""SELECT '{window}' AS time_window,'{field}' AS field,
              c.{ident(field)} AS value,count(*) AS transaction_interaction_pairs,
              count(DISTINCT interaction_id) AS distinct_interactions,
              100.*count(*)/sum(count(*)) OVER() AS pct_pairs
              FROM service_pairs p JOIN calls c USING(interaction_id)
              WHERE time_window='{window}' GROUP BY 3 ORDER BY 3 NULLS LAST""",
            )
    save("service_interaction_proximity.csv", summaries)
    save("service_proximity_distributions.csv", distributions)
    log("8. Contactos posteriores: solo asociación temporal del mismo cliente")


def transcripts(con):
    con.execute("""CREATE TABLE relevant_interactions AS SELECT * FROM calls
      SEMI JOIN service_pairs USING(interaction_id)""")
    assert con.execute(
        "SELECT count(*)=count(DISTINCT interaction_id) FROM transcript_metadata"
    ).fetchone()[0]
    query(
        con,
        "transcript_feasibility.csv",
        """SELECT count(*) AS relevant_unique_interactions,
      count(m.interaction_id) AS interactions_with_transcript,
      100.*count(m.interaction_id)/nullif(count(*),0) AS transcript_available_rate_pct
      FROM relevant_interactions i LEFT JOIN transcript_metadata m USING(interaction_id)""",
    )
    metadata = []
    for field in (
        "detected_keywords",
        "mentioned_entities",
        "detected_intents",
        "main_topics",
    ):
        metadata += rows(
            con,
            f"""SELECT '{field}' AS field,'present_in_raw_not_in_original_curated_projection' AS schema_status,
          count(*) AS relevant_interactions,count(m.interaction_id) AS relevant_transcripts,
          count(*) FILTER(WHERE m.{field}_nonnull) AS nonnull_transcripts,
          count(*) FILTER(WHERE m.{field}_nonempty) AS nonempty_transcripts,
          100.*count(*) FILTER(WHERE m.{field}_nonempty)/nullif(count(m.interaction_id),0) AS nonempty_pct_transcripts,
          100.*count(*) FILTER(WHERE m.{field}_nonempty)/nullif(count(*),0) AS nonempty_pct_interactions
          FROM relevant_interactions i LEFT JOIN transcript_metadata m USING(interaction_id)""",
        )
    save("transcript_metadata_feasibility.csv", metadata)
    bias = []
    for field in ("reason_category", "channel", "interaction_type"):
        bias += rows(
            con,
            f"""SELECT '{field}' AS field,i.{ident(field)} AS value,
          m.interaction_id IS NOT NULL AS transcript_available,count(*) AS interactions,
          100.*count(*)/sum(count(*)) OVER(PARTITION BY i.{ident(field)}) AS pct_within_value
          FROM relevant_interactions i LEFT JOIN transcript_metadata m USING(interaction_id)
          GROUP BY 2,3 ORDER BY 2,3 NULLS LAST""",
        )
    save("transcript_selection_comparison.csv", bias)
    log(
        "9. Cobertura de transcripts y metadatos; no lectura/exposición de texto personal"
    )


def digital(con, context):
    cutoff = literal(context["feature_cutoff_inclusive"])
    # Reduce 15.6M events to identified candidate customers before range association.
    con.execute(f"""CREATE TABLE scoped_digital AS SELECT event_id,customer_id,
      event_date::TIMESTAMP AS event_time,event_type,event_category,channel,action,product_id,event_value
      FROM digital_events SEMI JOIN (SELECT DISTINCT customer_id FROM candidates) c USING(customer_id)
      WHERE customer_id IS NOT NULL AND event_date::DATE<=DATE {cutoff}""")
    con.execute("""CREATE TABLE digital_pairs AS SELECT t.transaction_id,d.event_id,d.event_time,
      epoch(d.event_time-t.tx_time)/3600. AS delta_hours
      FROM candidates t JOIN scoped_digital d ON t.customer_id=d.customer_id
      AND d.event_time>=t.tx_time-INTERVAL '24 hours' AND d.event_time<=t.tx_time+INTERVAL '24 hours'""")
    summaries, distributions = [], []
    for name, predicate, before, after in [
        ("before_30m", "delta_hours>=-.5 AND delta_hours<0", 0.5, 0),
        ("before_2h", "delta_hours>=-2 AND delta_hours<0", 2, 0),
        ("before_24h", "delta_hours>=-24 AND delta_hours<0", 24, 0),
        ("after_24h", "delta_hours>=0 AND delta_hours<=24", 0, 24),
    ]:
        summaries += rows(
            con,
            f"""SELECT '{name}' AS time_window,
          (SELECT count(*) FROM candidates) AS candidate_transactions,
          (SELECT count(*) FROM candidates WHERE tx_time-INTERVAL '{before} hours'>=
            (SELECT min(event_date::TIMESTAMP) FROM digital_events)
            AND tx_time+INTERVAL '{after} hours'<=LEAST(
             (SELECT max(event_date::TIMESTAMP) FROM digital_events),DATE {cutoff}+INTERVAL '1 day'-INTERVAL '1 microsecond'))
            AS fully_observed_window_transactions,
          count(DISTINCT p.transaction_id) AS transactions_with_digital_context,
          100.*count(DISTINCT p.transaction_id)/(SELECT count(*) FROM candidates) AS transaction_coverage_pct,
          count(*) AS transaction_event_pairs,count(DISTINCT event_id) AS distinct_identified_events,
          count(d.product_id) AS pairs_with_recorded_product_id,
          100.*count(d.product_id)/nullif(count(*),0) AS product_id_pct_pairs
          FROM digital_pairs p JOIN scoped_digital d USING(event_id) WHERE {predicate}""",
        )
        for field in ("event_type", "event_category", "channel", "action"):
            distributions += rows(
                con,
                f"""SELECT '{name}' AS time_window,'{field}' AS field,
              d.{ident(field)} AS value,count(*) AS event_pairs,
              100.*count(*)/sum(count(*)) OVER() AS pct_event_pairs
              FROM digital_pairs p JOIN scoped_digital d USING(event_id)
              WHERE {predicate} GROUP BY 3 ORDER BY 3 NULLS LAST""",
            )
    save("digital_context_feasibility.csv", summaries)
    save("digital_context_distributions.csv", distributions)
    query(
        con,
        "digital_event_value_availability.csv",
        """SELECT count(*) AS unique_nearby_identified_events,
      count(product_id) AS product_id_present,count(event_value) AS event_value_present,
      'event_value units and meaning not established; no monetary pooling' AS limitation
      FROM scoped_digital SEMI JOIN digital_pairs USING(event_id)""",
    )
    log(
        "10. Contexto digital identificado, ventanas anidadas no aditivas, sin identity stitching"
    )


def bundles(con):
    # Independent aggregates at pair grain, never join service events to digital events.
    con.execute("""CREATE TABLE pair_service AS SELECT p.complaint_id,p.transaction_id,
      count(s.interaction_id) AS retrospective_nearby_interaction_count_14d,
      count(m.interaction_id) AS retrospective_transcript_count_14d,
      count(s.interaction_id) FILTER(WHERE s.call_time<=c.complaint_time) AS interaction_count_observed_by_intake,
      count(m.interaction_id) FILTER(WHERE s.call_time<=c.complaint_time) AS transcripts_for_interactions_before_intake
      FROM candidate_pairs p JOIN cases c USING(complaint_id)
      LEFT JOIN service_pairs s USING(transaction_id)
      LEFT JOIN transcript_metadata m USING(interaction_id)
      GROUP BY p.complaint_id,p.transaction_id""")
    con.execute("""CREATE TABLE pair_digital AS SELECT p.complaint_id,p.transaction_id,
      count(d.event_id) AS retrospective_identified_events_24h,
      count(d.event_id) FILTER(WHERE d.event_time<=c.complaint_time) AS identified_events_observed_by_intake,
      count(d.event_id) FILTER(WHERE d.delta_hours<0) AS identified_events_before_transaction
      FROM candidate_pairs p JOIN cases c USING(complaint_id) LEFT JOIN digital_pairs d USING(transaction_id)
      GROUP BY p.complaint_id,p.transaction_id""")
    con.execute("""CREATE TABLE evidence_bundles AS SELECT
      'discovery_'||substr(sha256(c.complaint_id),1,20) AS case_id,c.complaint_id,c.customer_id,
      c.complaint_time AS complaint_creation_date,c.case_type,c.category,c.subcategory,
      c.claim_amount AS claimed_amount,c.currency AS claimed_currency,
      t.transaction_id AS candidate_transaction_id,t.tx_time AS candidate_transaction_date,
      t.amount AS candidate_amount,t.currency AS candidate_currency,
      t.transaction_status AS candidate_status,t.transaction_type AS candidate_type,t.channel AS candidate_channel,
      p.delta_hours AS time_difference_hours,p.before_or_at_complaint AS candidate_exists_by_intake,
      p.same_currency,p.amount_difference,p.relative_difference,
      CASE WHEN c.claim_amount IS NULL OR c.currency IS NULL THEN 'not_eligible'
        WHEN NOT p.same_currency THEN 'different_currency'
        WHEN p.amount_difference=0 THEN 'exact_candidate'
        ELSE 'nonexact_candidate_see_tolerance_flags' END AS amount_match_type,
      p.amount_difference<=1 AS within_1_currency_unit,p.relative_difference<=.01 AS within_1pct,
      p.relative_difference<=.05 AS within_5pct,
      'Unweighted inputs: absolute time delta, direction, currency equality, amount difference; no probability' AS candidate_rank_inputs,
      t.merchant_name IS NOT NULL AS merchant_available,t.fraud_recorded AS fraud_flag_recorded,
      t.fraud_score IS NOT NULL AS fraud_score_available,
      b.customer_transaction_count_prior_90d>0 AS prior_customer_activity_available,
      b.complete_prior_90d,s.interaction_count_observed_by_intake,
      s.transcripts_for_interactions_before_intake>0 AS transcript_for_prior_interaction_exists_in_extract,
      d.identified_events_observed_by_intake>0 AS identified_digital_context_observed_by_intake,
      s.retrospective_nearby_interaction_count_14d,s.retrospective_transcript_count_14d,
      d.retrospective_identified_events_24h,d.identified_events_before_transaction,
      'INFERRED RELATIONSHIP: same customer +/-30d; NOT verified dispute link' AS relationship_class,
      'Snapshot status/fraud and transcript creation availability unknown; not approved contemporaneous predictors' AS availability_warning,
      'Retrospective +/-30d discovery; future candidate rows never eligible for intake selection' AS population_scope
      FROM candidate_pairs p JOIN cases c USING(complaint_id) JOIN candidates t USING(transaction_id)
      JOIN behavior_features b USING(transaction_id)
      JOIN pair_service s USING(complaint_id,transaction_id)
      JOIN pair_digital d USING(complaint_id,transaction_id)""")
    assert con.execute(
        "SELECT count(*)=count(DISTINCT (complaint_id,candidate_transaction_id)) FROM evidence_bundles"
    ).fetchone()[0]
    assert (
        con.execute("SELECT count(*) FROM evidence_bundles").fetchone()[0]
        == con.execute("SELECT count(*) FROM candidate_pairs").fetchone()[0]
    )
    export(
        con,
        "case_evidence_bundles.parquet",
        "SELECT * FROM evidence_bundles ORDER BY complaint_id,candidate_transaction_id",
    )
    # Preserve zero-candidate complaints outside the pair-grain artifact.
    export(
        con,
        "case_register.parquet",
        """SELECT 'discovery_'||substr(sha256(c.complaint_id),1,20) AS case_id,
      c.complaint_id,c.customer_id,c.complaint_time,c.case_type,c.category,c.subcategory,
      x.temporal_count AS candidate_count_30d,x.prior_count AS prior_candidate_count_30d,
      'HEURISTIC discovery case, not observed operational case state' AS classification
      FROM cases c JOIN complaint_counts x USING(complaint_id) WHERE days=30""",
    )
    query(
        con,
        "evidence_bundle_summary.csv",
        """SELECT count(*) AS complaint_candidate_pairs,
      count(DISTINCT complaint_id) AS complaints_with_candidate,
      count(DISTINCT candidate_transaction_id) AS unique_candidate_transactions,
      count_if(candidate_exists_by_intake) AS pairs_not_after_intake,
      count_if(NOT candidate_exists_by_intake) AS future_pairs_retrospective_only,
      count_if(interaction_count_observed_by_intake>0) AS pairs_with_service_observed_by_intake,
      count_if(identified_digital_context_observed_by_intake) AS pairs_with_identified_digital_observed_by_intake
      FROM evidence_bundles""",
    )
    log("11. Bundles analíticos trazables y registro separado de casos sin candidato")


def archetypes(con):
    specs = [
        (
            "unique_prior_exact_candidate",
            "c.claim_amount IS NOT NULL AND c.currency IS NOT NULL AND n.prior_exact_count=1",
            "One exact amount+currency candidate before intake within 30d; not high-confidence truth",
            "Retrieve and ask confirmation",
            "Coincidence; missing linked verdict",
            "Customer/human confirmation; never auto-reimburse",
        ),
        (
            "unique_prior_temporal_candidate",
            "n.prior_count=1",
            "One same-customer transaction in prior 30d; amount may be absent or inconsistent with heuristic",
            "Show candidate and exact evidence",
            "Uniqueness is not match correctness",
            "Customer/authorized-human confirmation; preserve uncertainty",
        ),
        (
            "no_candidate_under_monetary_tolerance",
            "c.claim_amount IS NOT NULL AND c.currency IS NOT NULL AND n.prior_count>0 AND n.prior_relative_5pct_count=0",
            "Prior candidates exist but none meet exploratory same-currency <=5% rule",
            "Explain narrowing result and preserve original candidate list",
            "Tolerance is unapproved; no proof complaint is invalid",
            "Clarify amount/currency or human review; never automatic rejection",
        ),
        (
            "multiple_prior_candidates",
            "n.prior_count>1",
            "Multiple same-customer prior transactions in 30d",
            "Return bounded candidate list",
            "No true transaction label",
            "Clarify intake or human investigation",
        ),
        (
            "no_prior_candidate",
            "n.prior_count=0",
            "No same-customer transaction in prior 30d",
            "Record explicit empty retrieval",
            "Outside horizon, incorrect clues or absent data possible",
            "Clarify; human if unresolved",
        ),
        (
            "claimed_amount_missing",
            "c.claim_amount IS NULL",
            "Missing claim amount",
            "Prompt for amount/currency or transaction ID",
            "Missing does not imply invalid complaint",
            "Intake incomplete path",
        ),
        (
            "sparse_optional_evidence",
            "EXISTS (SELECT 1 FROM evidence_bundles e WHERE e.complaint_id=c.complaint_id AND e.candidate_exists_by_intake AND NOT e.merchant_available AND NOT e.fraud_score_available AND e.interaction_count_observed_by_intake=0)",
            "At least one prior candidate without merchant/score/nearby pre-intake service",
            "Show known and unknown evidence",
            "Optional absence is not suspiciousness",
            "Human review if required evidence absent",
        ),
        (
            "recorded_fraud_flag_present",
            "EXISTS (SELECT 1 FROM evidence_bundles e WHERE e.complaint_id=c.complaint_id AND e.candidate_exists_by_intake AND e.fraud_flag_recorded)",
            "Recorded True on a prior candidate",
            "Expose provenance-qualified flag",
            "Not verified fraud; flag availability unknown",
            "Human risk review, no automatic verdict",
        ),
        (
            "service_after_transaction_before_intake",
            "EXISTS (SELECT 1 FROM evidence_bundles e WHERE e.complaint_id=c.complaint_id AND e.candidate_exists_by_intake AND e.interaction_count_observed_by_intake>0)",
            "Same-customer contact temporally after candidate and by intake",
            "Retrieve associated service facts",
            "No explicit transaction reference",
            "Label temporal association in handoff",
        ),
    ]
    result = []
    for name, predicate, pattern, automated, uncertain, handling in specs:
        grouped = rows(
            con,
            f"""SELECT cohort,count(*) AS cohort_complaints,
          count_if({predicate}) AS population_size,100.*count_if({predicate})/count(*) AS pct_cohort
          FROM cases c JOIN complaint_counts n USING(complaint_id) JOIN membership USING(complaint_id)
          WHERE n.days=30 GROUP BY 1 ORDER BY 1""",
        )
        for r in grouped:
            if r["population_size"] > 0:
                r.update(
                    archetype=name,
                    representative_evidence_pattern=pattern,
                    automation=automated,
                    uncertainty=uncertain,
                    recommended_handling=handling,
                    classification="HEURISTIC overlapping archetypes; no individual demo selection",
                )
                result.append(r)
    save("case_archetypes.csv", result)
    log(
        "13. Arquetipos existentes, poblaciones agregadas; ningún cliente seleccionado para demo"
    )
