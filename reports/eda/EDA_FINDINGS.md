# EDA Findings & Implications for Customer Journey Discovery

## Confirmed findings

Ejecutado: 2026-10-01T00:43:28.375308-05:00. Corte de features: 2026-06-17 inclusive; edad referida a ese día.

### Coherencia semántica

| validation | total | eligible | consistent | inconsistent | orphan | consistent_pct |
| --- | --- | --- | --- | --- | --- | --- |
| transaction_product_customer | 4425008 | 4425008 | 4425008 | 0 | 0 | 100.0 |
| transcript_customer | 171321 | 171321 | 171321 | 0 | 0 | 100.0 |
| transcript_agent | 171321 | 171321 | 171321 | 0 | 0 | 100.0 |
| survey_customer | 212759 | 212759 | 212759 | 0 | 0 | 100.0 |
| survey_agent | 212759 | 212759 | 212759 | 0 | 0 | 100.0 |
| complaint_product_customer | 67095 | 44570 | 0 | 44570 | 0 | 0.0 |

Los IDs coincidentes no prueban coherencia de propietario/agente; las discrepancias anteriores se conservan y los ejemplos están seudonimizados en semantic_validation_examples.csv.

La relación affected_product_id de reclamos describe una referencia declarada; con propietario discordante no permite atribuir ese producto al cliente del reclamo.

### Horizonte observado

| dataset | basis | min_timestamp | max_timestamp | active_days | days_without_records |
| --- | --- | --- | --- | --- | --- |
| transactions | transaction_date | 2023-06-17 06:01:30 | 2026-06-18 05:59:41 | 1098 | 0 |
| digital_events | event_date | 2023-06-17 06:02:03 | 2026-06-18 06:04:05 | 1098 | 0 |
| call_center_interactions | interaction_date | 2023-06-17 08:03:26 | 2026-06-18 07:58:13 | 1098 | 0 |
| call_transcripts | process_date only; no independent event timestamp | 2023-06-17 00:00:00 | 2026-06-17 00:00:00 | 1097 | 0 |
| complaints | creation_date | 2023-06-17 08:07:05 | 2026-06-18 07:56:52 | 1098 | 0 |
| satisfaction_surveys | survey_date | 2023-06-17 09:29:20 | 2026-06-19 06:54:58 | 1099 | 0 |
| campaign_sends | send_date | 2023-07-01 06:00:42 | 2026-06-18 05:59:53 | 1084 | 0 |

Fechas posteriores de resolución/cierre/conversión se reportan en lifecycle_windows.csv. Las fechas nominales de proceso se comparan por día; sus horas calculadas contra medianoche no prueban latencia real.

### Clientes y transacciones

| variable | valid | median | p90 | p99 |
| --- | --- | --- | --- | --- |
| age | 150000 | 52.0 | 77.0 | 83.0 |
| credit_score | 127508 | 631.0 | 761.0 | 850.0 |

| variable | category | records | pct |
| --- | --- | --- | --- |
| country | México | 74907 | 49.938 |
| country | Colombia | 45251 | 30.167333333333332 |
| country | Argentina | 29842 | 19.894666666666666 |
| segment | Basic | 89756 | 59.83733333333333 |
| segment | Plus | 37547 | 25.031333333333333 |
| segment | Premium | 15207 | 10.138 |
| segment | Student | 7490 | 4.993333333333333 |

| variable | valid | minimum | median | p90 | p95 | p99 | maximum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| amount_usd | 1887552 | 5.0 | 466.69 | 5113.063000000009 | 7554.503499999999 | 9506.714899999999 | 9999.96 |
| fraud_score | 3539851 | 0.0 | 15.01 | 27.02 | 28.52 | 29.72 | 99.99 |

| currency | transactions | amount_usd_observed | amount_usd_coverage_pct |
| --- | --- | --- | --- |
| USD | 2437979 | 0 | 0.0 |
| ARS | 792585 | 752544 | 94.94804973599047 |
| COP | 1194444 | 1135008 | 95.02396093914825 |

Los resúmenes de amount_usd describen exclusivamente valores observados. Las transacciones USD tienen amount_usd nulo en este extracto; amount se mantiene separado por moneda y no se rellena automáticamente amount_usd. Las features incluyen conteo y porcentaje monetario observado por cliente.

| variable | category | records | pct |
| --- | --- | --- | --- |
| transaction_type | Purchase | 1083406 | 24.48370714810007 |
| transaction_type | Withdrawal | 964673 | 21.800480360713472 |
| transaction_type | Transfer | 896438 | 20.258449250261243 |
| transaction_type | Payment | 738964 | 16.699721220842992 |
| transaction_type | Deposit | 609409 | 13.771929903855542 |
| transaction_type | Adjustment | 132118 | 2.9857121162266824 |
| channel | POS | 1548161 | 34.986626012879526 |
| channel | ATM | 1328334 | 30.0187931863626 |
| channel | Web | 663445 | 14.993080238499005 |
| channel | App | 663414 | 14.992379674793808 |
| channel | Branch | 132495 | 2.9942318748350285 |
| channel | Transfer | 89159 | 2.0148890126300336 |
| transaction_status | Approved | 4070681 | 91.99262464610233 |
| transaction_status | Declined | 221234 | 4.999629379201123 |
| transaction_status | Pending | 88343 | 1.9964483680029506 |
| transaction_status | Reversed | 44750 | 1.0112976066935924 |

Ingreso se presenta por país sin asumir moneda ni equivalencia internacional. Balances y límites se segmentan por moneda. Las categorías y altas por mes se encuentran en los CSV de cada dominio.

### Digital

| events | identified | anonymous | anonymous_pct | identified_customers | product_known_pct |
| --- | --- | --- | --- | --- | --- |
| 15620994 | 11875548 | 3745446 | 23.97700171960888 | 149997 | 9.220527195644529 |

| sessions | singleton_sessions | multi_customer_sessions | anonymous_only_sessions | mixed_identity_sessions |
| --- | --- | --- | --- | --- |
| 1837415 | 0 | 0 | 367044 | 498785 |

La duración de sesión es el intervalo entre el primer y último evento observado; un evento único implica intervalo cero, no duración real cero.

### Transcripts y surveys

| n_interactions | n_interactions_with_transcript | interaction_coverage_pct | n_calls | n_calls_with_transcript | call_coverage_pct |
| --- | --- | --- | --- | --- | --- |
| 686296 | 171321 | 24.96313544010165 | 583250 | 145577 | 24.95962280325761 |

| n_interactions | n_interactions_with_survey | interaction_coverage_pct | n_calls | n_calls_with_survey | call_coverage_pct |
| --- | --- | --- | --- | --- | --- |
| 686296 | 212759 | 31.001054938393928 | 583250 | 180908 | 31.017231033004716 |

| survey_type | valid | minimum | median | maximum |
| --- | --- | --- | --- | --- |
| CSAT | 127856 | 1.0 | 3.0 | 4.0 |
| NPS | 63668 | 2.0 | 6.0 | 7.0 |
| CES | 21235 | 1.0 | 3.0 | 4.0 |

Las tablas *_selection_numeric/categories/monthly.csv comparan ambos grupos. Diferencias descriptivas sugieren selección; semejanza en estas variables no demuestra ausencia de sesgo. CSAT, CES y NPS se mantienen separados; las features de satisfacción usan solo CSAT.

### Reclamos

| status | records | resolution_null_pct | closing_null_pct | origin_interaction_null |
| --- | --- | --- | --- | --- |
| Closed | 2609 | 5.366040628593331 | 4.906094288999617 | 2609 |
| Escalated | 3321 | 100.0 | 100.0 | 3321 |
| In Process | 26823 | 100.0 | 100.0 | 26823 |
| Open | 20125 | 100.0 | 100.0 | 20125 |
| Rejected | 705 | 100.0 | 100.0 | 705 |
| Resolved | 13512 | 4.677323860272351 | 100.0 | 13512 |

Los nulos se evalúan por estado. Los agregados temporales de resolución usan únicamente fechas <= corte; open_complaint_count queda NULL porque un estado snapshot no reconstruye el estado histórico. Se proporciona no_observed_resolution_by_cutoff_count como observación distinta, no como equivalencia a abierto.

### Campañas

| sent | delivered | opened | clicked | converted | strict_full_funnel | converted_without_clicked | converted_missing_date | nonconverted_with_date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1746801 | 1642044 | 487309 | 97793 | 9799 | 9799 | 0 | 0 | 0 |

Los flags marginales y el funnel estricto se muestran por separado. NULL de fecha sin conversión no se clasifica como defecto. Moneda de conversion_value/send_cost no documentada: sumas en unidades originales, sin equipararlas a USD.

### Tipos de cambio

| currency | pair_direction | operation | matched | eligible_amounts | within_tolerance_pct | median_relative_error |
| --- | --- | --- | --- | --- | --- | --- |
| ARS | USD_to_currency | multiply | 792338 | 752317 | 0.0 | 122568.51628722929 |
| COP | USD_to_currency | multiply | 1194084 | 1134663 | 0.0 | 15986382.761916429 |
| ARS | currency_to_USD | multiply | 792338 | 752317 | 51.52149958062891 | 0.009735171246819344 |
| COP | currency_to_USD | multiply | 1194084 | 1134663 | 47.67882622417405 | 0.011988410494455159 |
| ARS | USD_to_currency | divide | 792338 | 752317 | 50.05802075454895 | 0.009984819767181317 |
| COP | USD_to_currency | divide | 1194084 | 1134663 | 47.4330263699442 | 0.010484445544214105 |
| ARS | currency_to_USD | divide | 792338 | 752317 | 0.0 | 122420.64650518577 |
| COP | currency_to_USD | divide | 1194084 | 1134663 | 0.0 | 16000042.104537986 |

Se contrastan ambas direcciones y fórmulas usando día calendario exacto, tolerancia max(0.02 USD, 1% de amount_usd). El ajuste empírico es evidencia de compatibilidad, no confirmación contractual de las unidades. No se corrigen montos ni se usan tasas de otro día.

### Asociaciones preliminares

| x | y | paired_customers | pearson_raw | spearman |
| --- | --- | --- | --- | --- |
| digital_event_count | interaction_count | 148436 | -0.0026958719886130016 | -0.002132703710436149 |
| transaction_count | complaint_count | 48806 | 0.006512509478587778 | 0.0022807940322665224 |
| complaint_count | avg_satisfaction | 31079 | 0.005953249288842751 | 0.005298072283931816 |
| median_wait_time | avg_satisfaction | 84728 | 0.0032376902282737676 | 0.0023181048480742936 |
| interaction_count | avg_satisfaction | 86087 | -0.0018535410339412057 | -0.013125350347184745 |

Solo clientes con ambas observaciones; ausencia de dominio permanece NULL. Estas asociaciones no son causales y pueden reflejar exposición, selección o claves incoherentes.

## Data limitations

- registration_branch_id y assigned_branch_id: relaciones no confiables según profiling; excluidas de joins geográficos.
- Reclamos sin origin_interaction_id; no existe enlace observado al contacto que los originó.
- Digital anónimo y product_id escaso; sesiones multi-cliente, si aparecen, requieren revisión antes de enlazar secuencias.
- Transcripts y encuestas tienen cobertura parcial; interacciones incluyen llamadas, chat, email y video.
- last_updated ambiguo; atributos de snapshot (saldo, segmento, income, score y estado) no entran en customer_360.
- No hay timestamps de disponibilidad/revisiones: features son agregados EDA a corte, no certificación de point-in-time para modelos.
- Meses/días extremos pueden ser parciales; cambios x2 o /2 son alertas de volumen, no errores automáticos.
- No se exporta texto personal; lengths/word counts son aproximaciones por caracteres/tokens de espacio.

## Hypotheses

- Explicar la discordancia reclamo-producto antes de interpretar propiedad y recorridos entre esos dominios.
- Investigar continuidad entre eventos anónimos e identificados dentro de sesiones mixtas, sin atribuirlos automáticamente en esta etapa.
- Investigar el calendario de proceso frente a eventos que cruzan medianoche; confirmar zona horaria y fecha operativa.
- Evaluar actividad digital y frecuencia de atención controlando exposición y selección.
- Examinar espera y CSAT dentro de canales/motivos comparables y con enlaces semánticamente válidos.
- Confirmar dirección/unidades FX y semántica de sesión con responsables de los datos.
- Determinar cómo representar reclamos sin interacción de origen, manteniendo enlaces hipotéticos separados.

Se detiene la etapa 02. No se ejecutan journeys, modelado, embeddings ni LLMs.
