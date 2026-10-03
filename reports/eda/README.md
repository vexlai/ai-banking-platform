# EDA — etapa 02

El notebook notebooks/02_eda.ipynb es la entrada revisable. Ejecutar desde la raíz:

    .venv/bin/python scripts/run_eda_notebook.py

Para regenerar únicamente su estructura/código:

    .venv/bin/python scripts/build_eda.py

Regenerar elimina las salidas del notebook; no se necesita para una reejecución normal.

## Fuentes y rendimiento

- Se reutilizan los resultados de reports/profiling. No se ejecutan 00 ni 01.
- El manifiesto SHA-256 se verifica al inicio y al final. source_integrity.json documenta la comprobación final.
- DuckDB usa dos hilos, 1.5 GB de memoria y proyecciones comprimidas en .tmp/eda/analysis.duckdb. La caché excluye PII/texto sin utilidad para este análisis; se invalida con cambios de fuentes o columnas.
- Los CSV se leen con esquema VARCHAR explícito y validación estricta. No hay sampling, imputación, descarte de filas ni eliminación de outliers.
- Las salidas pandas/matplotlib son agregados pequeños. Las tablas de eventos permanecen en DuckDB.

## Decisiones de interpretación

- Readiness precede al análisis descriptivo. Coincidencia de FK y coherencia de cliente/agente son comprobaciones distintas.
- Cada dominio tiene su ventana de fechas de evento; transcripts solo tiene fecha de proceso. Los hitos posteriores de reclamos/campañas se informan por separado.
- process_date tiene granularidad diaria. Las diferencias en horas contra medianoche son nominales y no deben interpretarse como latencia técnica.
- Las features usan el último día de proceso compartido, inclusive. Excluyen resultados fechados después del corte y atributos snapshot de vigencia desconocida.
- open_complaint_count queda NULL: no se reconstruye un estado histórico desde status sin fecha de vigencia. Se conserva un conteo distinto de reclamos sin resolución observada al corte.
- CSAT, NPS y CES no se mezclan. avg_satisfaction/latest_satisfaction usan solo CSAT. Los promedios describen respuestas observadas.
- Los NULL tras joins de agregados indican ausencia de observaciones en el dominio. No se reemplazan por cero; se añaden indicadores de presencia.
- Los enlaces de reclamo a producto no permiten atribuir propiedad cuando customer_id discrepa; los conteos por affected_product_id describen referencias declaradas.
- Los montos globales transaccionales usan amount_usd. amount, saldos y límites se segmentan por moneda. Moneda de income/costos/valor de conversión no documentada.
- FX: contraste de ambas direcciones/fórmulas, fecha exacta y tolerancia max(0.02 USD, 1%). El ajuste empírico no confirma por sí solo las unidades contractuales.
- Las asociaciones por cliente son descriptivas, condicionadas a tener observaciones en ambos dominios y sin inferencia causal.

## Resultados principales

- semantic_validation.csv y semantic_validation_examples.csv: consistencia y ejemplos seudonimizados.
- temporal_coverage.csv, temporal_delays.csv, lifecycle_windows.csv: horizontes y coherencia temporal.
- coverage_daily/monthly.csv, partition_day_check.csv, temporal_gaps.csv, abrupt_volume_changes.csv: cobertura y particiones.
- transcript_coverage.csv, survey_coverage.csv y *_selection_*: denominadores y representatividad.
- *_customer_features.parquet, customer_360_eda.parquet y feature_cardinality.csv: agregados, joins y validación de una fila por cliente.
- cross_domain_associations.csv y cross_domain_groups.csv: asociaciones interpretables.
- key_eda_metrics.csv: índice de métricas con fuente.
- EDA_FINDINGS.md: hallazgos confirmados, limitaciones e hipótesis para revisar antes de 03.
- reports/figures/eda/: cuatro figuras enfocadas en cobertura, colas financieras, duración/espera y selección.

execution.log registra etapas; notebook_execution.log registra celdas. Un resultado intermedio no prueba finalización: comprobar el notebook sin errores y source_integrity.json de la ejecución final.

No se implementa ni ejecuta el notebook 03.
