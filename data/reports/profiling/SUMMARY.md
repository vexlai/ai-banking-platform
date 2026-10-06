# Inventory and ingestion: results

Completed scope: 00 and 01. No EDA, cleaning, imputation or modeling was performed.

## Key findings

- `customers.registration_branch_id`: 149,995 references without a match out of 150,000 non-null in `branches.branch_id`.
- `service_agents.assigned_branch_id`: 831 references without a match out of 833 non-null in `branches.branch_id`.
- `complaints.origin_interaction_id`: completely null (67,095 rows).
- `customers.last_updated`: 4,870 values after the 2026-09-28 cutoff; maximum 2027-06-15 19:35:27. Temporal clarification required.
- `products.last_updated`: 13,087 values after the 2026-09-28 cutoff; maximum 2027-06-15 02:26:58. Temporal clarification required.
- Extra duplicate rows within tables: 0. Non-convertible date values in evaluated columns: 0.
- 19 numeric columns contain possible IQR outliers; none were corrected or removed.

## Datasets

| Dataset | CSV files | Rows | Columns | Bytes | MiB |
| --- | --- | --- | --- | --- | --- |
| branches | 1 | 350 | 22 | 89529 | 0.09 |
| call_center_interactions | 1097 | 686296 | 21 | 139734950 | 133.26 |
| call_transcripts | 1097 | 171321 | 18 | 137235657 | 130.88 |
| campaign_sends | 1083 | 1746801 | 22 | 325976325 | 310.88 |
| complaints | 1097 | 67095 | 27 | 17990612 | 17.16 |
| customers | 1 | 150000 | 27 | 46897358 | 44.72 |
| daily_exchange_rates | 1 | 13164 | 7 | 778914 | 0.74 |
| digital_events | 1097 | 15620994 | 26 | 3757355051 | 3583.29 |
| marketing_campaigns | 1 | 200 | 13 | 32710 | 0.03 |
| products | 1 | 400000 | 17 | 68213646 | 65.05 |
| satisfaction_surveys | 1097 | 212759 | 20 | 46446098 | 44.29 |
| service_agents | 1 | 1200 | 18 | 237992 | 0.23 |
| transactions | 1097 | 4425008 | 22 | 808333639 | 770.89 |

Total: 7,671 files; 23,495,188 rows; 5,349,322,481 bytes.

## Verified candidate keys

They are unique and non-null in this delivery; this does not prove stability or business meaning.

| Dataset | Columns | Distinct values |
| --- | --- | --- |
| branches | branch_id | 350 |
| branches | branch_code | 350 |
| branches | address | 350 |
| branches | phone | 350 |
| branches | email | 350 |
| branches | latitude | 350 |
| branches | longitude | 350 |
| call_center_interactions | interaction_id | 686296 |
| call_transcripts | transcript_id | 171321 |
| call_transcripts | interaction_id | 171321 |
| campaign_sends | send_id | 1746801 |
| complaints | complaint_id | 67095 |
| customers | customer_id | 150000 |
| customers | document_number | 150000 |
| customers | registration_branch_id | 150000 |
| daily_exchange_rates | date + source_currency + target_currency | 13164 |
| digital_events | event_id | 15620994 |
| marketing_campaigns | campaign_id | 200 |
| marketing_campaigns | campaign_name | 200 |
| products | product_id | 400000 |
| satisfaction_surveys | survey_id | 212759 |
| satisfaction_surveys | interaction_id | 212759 |
| service_agents | agent_id | 1200 |
| transactions | transaction_id | 4425008 |

The complete list, including IDs that fail uniqueness, is in `candidate_keys.csv`.

Accidental uniqueness of addresses, phones, coordinates or external references does not make them recommended business keys. Prefer each entity's own IDs and check references against their targets.

## Duplicate rows

| Dataset | Extra duplicate rows |
| --- | --- |
| branches | 0 |
| call_center_interactions | 0 |
| call_transcripts | 0 |
| campaign_sends | 0 |
| complaints | 0 |
| customers | 0 |
| daily_exchange_rates | 0 |
| digital_events | 0 |
| marketing_campaigns | 0 |
| products | 0 |
| satisfaction_surveys | 0 |
| service_agents | 0 |
| transactions | 0 |

## Candidate relationships: value checks

Nulls and missing references are reported separately. Target uniqueness must be reviewed before joining. Semantics remain pending validation.

| Source | Target | Nulls | Orphans | Non-null match % | Target ID repeats |
| --- | --- | --- | --- | --- | --- |
| call_center_interactions.customer_id | customers.customer_id | 0 | 0 | 100.0000 | 0 |
| call_center_interactions.agent_id | service_agents.agent_id | 0 | 0 | 100.0000 | 0 |
| call_transcripts.interaction_id | call_center_interactions.interaction_id | 0 | 0 | 100.0000 | 0 |
| call_transcripts.customer_id | customers.customer_id | 0 | 0 | 100.0000 | 0 |
| call_transcripts.agent_id | service_agents.agent_id | 0 | 0 | 100.0000 | 0 |
| campaign_sends.campaign_id | marketing_campaigns.campaign_id | 0 | 0 | 100.0000 | 0 |
| campaign_sends.customer_id | customers.customer_id | 0 | 0 | 100.0000 | 0 |
| complaints.customer_id | customers.customer_id | 0 | 0 | 100.0000 | 0 |
| complaints.affected_product_id | products.product_id | 22525 | 0 | 100.0000 | 0 |
| complaints.related_branch_id | branches.branch_id | 47917 | 0 | 100.0000 | 0 |
| complaints.origin_interaction_id | call_center_interactions.interaction_id | 67095 | 0 | N/A | 0 |
| complaints.assigned_agent_id | service_agents.agent_id | 23115 | 0 | 100.0000 | 0 |
| customers.registration_branch_id | branches.branch_id | 0 | 149995 | 0.0033 | 0 |
| digital_events.customer_id | customers.customer_id | 3745446 | 0 | 100.0000 | 0 |
| digital_events.product_id | products.product_id | 14180656 | 0 | 100.0000 | 0 |
| products.customer_id | customers.customer_id | 0 | 0 | 100.0000 | 0 |
| products.opening_branch_id | branches.branch_id | 0 | 0 | 100.0000 | 0 |
| satisfaction_surveys.interaction_id | call_center_interactions.interaction_id | 0 | 0 | 100.0000 | 0 |
| satisfaction_surveys.customer_id | customers.customer_id | 0 | 0 | 100.0000 | 0 |
| satisfaction_surveys.agent_id | service_agents.agent_id | 0 | 0 | 100.0000 | 0 |
| service_agents.assigned_branch_id | branches.branch_id | 367 | 831 | 0.2401 | 0 |
| transactions.product_id | products.product_id | 0 | 0 | 100.0000 | 0 |
| transactions.customer_id | customers.customer_id | 0 | 0 | 100.0000 | 0 |
| transactions.branch_id | branches.branch_id | 3037076 | 0 | 100.0000 | 0 |

Additional pending hypothesis: relate `transactions.transaction_date` and `transactions.currency` to `daily_exchange_rates.date` and `source_currency`, fixing the required target currency. This composite link was not validated in this phase.

## Column quality

Fully null columns: 1. Constant among non-nulls: 7. Nearly constant: 2.

Highest missing percentage (up to 25 columns; full detail in `column_profiles.csv`):

| Dataset | Column | Nulls | % |
| --- | --- | --- | --- |
| complaints | origin_interaction_id | 67095 | 100.00 |
| campaign_sends | conversion_date | 1737002 | 99.44 |
| campaign_sends | conversion_value | 1737002 | 99.44 |
| complaints | closing_date | 64614 | 96.30 |
| complaints | resolution_satisfaction | 64611 | 96.30 |
| digital_events | event_value | 14826484 | 94.91 |
| digital_events | utm_campaign | 14782077 | 94.63 |
| digital_events | utm_source | 14781949 | 94.63 |
| digital_events | utm_medium | 14781860 | 94.63 |
| campaign_sends | click_date | 1649008 | 94.40 |
| campaign_sends | click_count | 1649008 | 94.40 |
| campaign_sends | failure_reason | 1647204 | 94.30 |
| digital_events | referrer | 14573469 | 93.29 |
| complaints | compensation_granted | 62454 | 93.08 |
| digital_events | product_id | 14180656 | 90.78 |
| satisfaction_surveys | question_3_response | 172656 | 81.15 |
| satisfaction_surveys | question_3_text | 172615 | 81.13 |
| transactions | longitude | 3567715 | 80.63 |
| transactions | latitude | 3567680 | 80.63 |
| complaints | resolution | 51785 | 77.18 |
| complaints | resolution_date | 51746 | 77.12 |
| complaints | resolution_days | 51732 | 77.10 |
| transactions | merchant_category | 3396215 | 76.75 |
| transactions | merchant_name | 3395774 | 76.74 |
| campaign_sends | open_device | 1308424 | 74.90 |

Missing values may depend on optional fields; no business defects are assumed without evidence.

## Dates

| Dataset | Column | Invalid | After cutoff | Minimum | Maximum |
| --- | --- | --- | --- | --- | --- |
| branches | branch_opening_date | 0 | 0 | 1990-01-03 00:00:00 | 2023-05-11 00:00:00 |
| call_center_interactions | interaction_date | 0 | 0 | 2023-06-17 08:03:26 | 2026-06-18 07:58:13 |
| call_center_interactions | process_date | 0 | 0 | 2023-06-17 00:00:00 | 2026-06-17 00:00:00 |
| call_transcripts | process_date | 0 | 0 | 2023-06-17 00:00:00 | 2026-06-17 00:00:00 |
| campaign_sends | send_date | 0 | 0 | 2023-07-01 06:00:42 | 2026-06-18 05:59:53 |
| campaign_sends | process_date | 0 | 0 | 2023-07-01 00:00:00 | 2026-06-17 00:00:00 |
| campaign_sends | open_date | 0 | 0 | 2023-07-01 07:44:22 | 2026-06-25 03:30:02 |
| campaign_sends | click_date | 0 | 0 | 2023-07-01 21:57:26 | 2026-06-24 23:51:59 |
| campaign_sends | conversion_date | 0 | 0 | 2023-07-03 12:56:27 | 2026-06-26 08:26:49 |
| complaints | creation_date | 0 | 0 | 2023-06-17 08:07:05 | 2026-06-18 07:56:52 |
| complaints | process_date | 0 | 0 | 2023-06-17 00:00:00 | 2026-06-17 00:00:00 |
| complaints | assignment_date | 0 | 0 | 2023-06-17 22:26:12 | 2026-06-19 03:56:52 |
| complaints | first_response_date | 0 | 0 | 2023-06-18 03:37:40 | 2026-06-20 22:42:19 |
| complaints | resolution_date | 0 | 0 | 2023-06-20 07:10:42 | 2026-07-18 06:07:57 |
| complaints | closing_date | 0 | 0 | 2023-06-26 11:38:44 | 2026-07-18 22:15:16 |
| customers | date_of_birth | 0 | 0 | 1942-07-07 00:00:00 | 2005-06-21 00:00:00 |
| customers | registration_date | 0 | 0 | 2018-06-18 01:21:11 | 2026-06-17 23:53:29 |
| customers | last_updated | 0 | 4870 | 2018-06-18 15:09:31 | 2027-06-15 19:35:27 |
| daily_exchange_rates | date | 0 | 0 | 2023-06-17 00:00:00 | 2026-06-17 00:00:00 |
| digital_events | event_date | 0 | 0 | 2023-06-17 06:02:03 | 2026-06-18 06:04:05 |
| digital_events | process_date | 0 | 0 | 2023-06-17 00:00:00 | 2026-06-17 00:00:00 |
| marketing_campaigns | start_date | 0 | 0 | 2023-07-01 00:00:00 | 2026-06-14 00:00:00 |
| marketing_campaigns | end_date | 0 | 0 | 2023-08-11 00:00:00 | 2026-08-20 00:00:00 |
| products | opening_date | 0 | 0 | 2018-06-18 00:00:00 | 2026-06-17 00:00:00 |
| products | expiration_date | 0 | 61568 | 2021-06-17 00:00:00 | 2031-06-16 00:00:00 |
| products | last_transaction_date | 0 | 0 | 2018-06-21 17:07:15 | 2026-06-17 23:17:43 |
| products | last_updated | 0 | 13087 | 2018-06-20 05:21:54 | 2027-06-15 02:26:58 |
| satisfaction_surveys | survey_date | 0 | 0 | 2023-06-17 09:29:20 | 2026-06-19 06:54:58 |
| satisfaction_surveys | process_date | 0 | 0 | 2023-06-17 00:00:00 | 2026-06-17 00:00:00 |
| service_agents | hire_date | 0 | 0 | 2013-06-20 00:00:00 | 2026-03-17 00:00:00 |
| transactions | transaction_date | 0 | 0 | 2023-06-17 06:01:30 | 2026-06-18 05:59:41 |
| transactions | process_date | 0 | 0 | 2023-06-17 00:00:00 | 2026-06-17 00:00:00 |

Reproducible cutoff: 2026-09-28. A future expiration or campaign-end date may be legitimate.

## Possible outliers

| Dataset | Column | Minimum | Maximum | Outside 1.5×IQR |
| --- | --- | --- | --- | --- |
| branches | latitude | -34.6907666 | 25.7817721 | 125 |
| call_center_interactions | duration_seconds | 30.0 | 1204.0 | 8612 |
| call_center_interactions | wait_time_seconds | 0.0 | 424.0 | 1669 |
| call_center_interactions | sentiment_score | -1.0 | 1.0 | 17229 |
| call_transcripts | duration_seconds | 30.0 | 1151.0 | 2186 |
| campaign_sends | send_cost | 0.0001 | 0.3 | 28930 |
| customers | credit_score | 422.0 | 850.0 | 2 |
| customers | estimated_monthly_income | 5100.28 | 111895075.15 | 12231 |
| daily_exchange_rates | exchange_rate | 0.000245 | 4079.944006 | 3291 |
| daily_exchange_rates | buy_rate | 0.000241 | 4057.98057 | 3291 |
| daily_exchange_rates | sell_rate | 0.000246 | 4138.591967 | 3291 |
| products | current_balance | 0.0 | 881511545.61 | 67020 |
| products | credit_limit | 1000.33 | 599984205.95 | 22004 |
| products | days_past_due | 0.0 | 180.0 | 18765 |
| satisfaction_surveys | main_score | 1.0 | 7.0 | 37718 |
| transactions | amount | 5.0 | 39999828.48 | 606168 |
| transactions | amount_usd | 5.0 | 9999.96 | 230582 |
| transactions | fraud_score | 0.0 | 99.99 | 1841 |
| transactions | latitude | -35.6036984 | 5.7109985 | 170800 |

These are profiling signals, not proven errors. Mixed currencies and scales can produce them; no value was removed.

## Technical decisions and limits

- Python 3.12, DuckDB for full data and pandas only for small summaries.
- Strict VARCHAR reads preserve IDs and leading zeros. Types are candidates verified by conversion, not changes to the source.
- Empty CSV values are read as NULL; whitespace is recorded without normalization.
- All headers are verified; Hive partitions are not added as columns.
- Exact counts and quartiles; no sampling was used.
- Nearly constant: dominant frequency ≥99% of non-null values.
- Only one composite key is explicitly tested: date, source currency and target currency in exchange rates.
- ID coverage does not validate customer/product/agent consistency or cross-table timing.
- No business dictionary exists to confirm all valid ranges or required fields.
- Originals remain in their initial locations, treated as immutable raw.

## Source integrity

`inventory_integrity.json`: `{
  "files_verified": 7671,
  "sha256_unchanged": true
}`

`profiling_integrity.json`: `{
  "files_verified": 7671,
  "sha256_unchanged": true
}`

