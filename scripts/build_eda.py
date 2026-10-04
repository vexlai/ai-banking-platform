"""Build the executable EDA notebook; does not read or modify source datasets."""
from pathlib import Path
import nbformat

ROOT=Path(__file__).resolve().parents[1]
nb=nbformat.v4.new_notebook()
nb.metadata={"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python"}}
cells=[]
def md(s): cells.append(nbformat.v4.new_markdown_cell(s))
def code(s): cells.append(nbformat.v4.new_code_cell(s))
md("""# 02 — EDA confiable y preparación para customer journey discovery

Consultas exactas sobre los 13 datasets verificados en 00/01. Fuentes: reports/profiling/SUMMARY.md, inventory_columns.csv, datasets.csv y source_manifest.json. No se repite el profiling.

DuckDB mantiene proyecciones comprimidas en .tmp/eda, con firmas de las fuentes y validación de filas. pandas recibe solamente tablas agregadas; los 15,6 millones de eventos digitales no se materializan en pandas. Se preservan nulos y extremos. Las salidas completas se guardan en reports/eda y se muestran extractos legibles aquí. Etapa 03 queda pendiente.""")
code("""from pathlib import Path
import sys
root = Path.cwd().resolve()
if not (root / 'AGENTS.md').exists():
    root = root.parent
assert (root / 'AGENTS.md').exists()
sys.path.insert(0, str(root))
import pandas as pd
from IPython.display import display, Markdown, Image
from src.eda_core import OUT, FIG, start, finish
from src import eda_readiness as ready, eda_domains as domain, eda_outputs as output
def show(*names, limit=30):
    for name in names:
        display(Markdown('**' + name + '**'))
        display(pd.read_csv(OUT / name).head(limit))
con, context = start()
display(context)""")
md("""## 0. EDA Readiness & Semantic Validation

### 0.1 Transaction → Product → Customer
### 0.2 Transcript → Interaction
### 0.3 Survey → Interaction
### 0.4 Complaint → Product → Customer

Primero se comprueba unicidad de los destinos. Los totales distinguen referencias elegibles, enlazadas, huérfanas y coincidencia de propietario/agente. El porcentaje consistente usa referencias no nulas como denominador. Ejemplos de discrepancias contienen hashes truncados de los IDs. Ninguna discrepancia se corrige.""")
code("ready.semantic(con)\nshow('semantic_validation.csv','semantic_validation_examples.csv','branch_validation.csv')")
md("""### 0.5 Temporal consistency
### 0.6 Observation window

La fecha real de ejecución está en analysis_context.json. El horizonte observado se deriva de fechas de eventos; transcripts solo tiene process_date y se etiqueta como cobertura de proceso. customers/products.last_updated se excluyen.

process_date es una fecha de proceso con granularidad de día. Se comparan días antes/igual/después, y se informa diferencia nominal de horas contra medianoche: no equivale a latencia real. Los registros posteriores a un día se señalan como candidatos a llegada tardía, sin asumir error.

Las features usan el último día de proceso compartido y excluyen eventos/resultados posteriores. Fechas de cierre y conversión pueden extenderse más allá de la ventana primaria: se muestran por separado.""")
code("ready.temporal(con)\nshow('temporal_coverage.csv','temporal_delays.csv','lifecycle_windows.csv','dimension_date_windows.csv')")
md("""## 1. Dataset coverage over time

Se calculan registros diarios/mensuales, gaps internos y cambios de volumen al menos x2 o /2 frente al día observado anterior. Es una heurística descriptiva; los límites pueden ser días parciales. Se comprueba la relación entre sufijo del archivo, fecha de proceso y fecha del evento. Los gráficos mensuales se generan en la sección 14, después de las validaciones.""")
code("show('partition_day_check.csv','temporal_gaps.csv','abrupt_volume_changes.csv','coverage_monthly.csv')")
md("""## 2. Customer & product base

Edad referida al corte de observación, no a la fecha de ejecución. Geografía y segmentos describen atributos del snapshot, sin atribuirles vigencia histórica. Ingreso se presenta por país porque la moneda no está documentada. Balances/límites se segmentan por currency.

registration_branch_id no se utiliza para joins. Los productos se describen por tipo, estado, apertura, morosidad y última transacción; opening_branch_id fue revalidado en readiness.""")
code("domain.customers_products(con, context)\nshow('customer_numeric.csv','customer_income_by_country.csv','customer_categories.csv','product_categories.csv','product_money_by_currency.csv','product_numeric.csv','products_per_customer.csv','product_date_ranges.csv')")
md("""## 3. Transactions

Comparaciones globales en amount_usd; amount se resume únicamente por currency. Se incluyen medianas y p90/p95/p99, actividad por cliente/producto, categorías, merchants y cobertura de branch. El histograma logarítmico conserva todos los montos positivos/negativos; ceros/nulos se cuentan aparte porque no tienen logaritmo.""")
code("domain.transactions(con, context)\nshow('transaction_numeric.csv','transaction_amount_by_currency.csv','transactions_per_customer_id.csv','transactions_per_product_id.csv','transaction_categories.csv','transaction_merchant_coverage.csv','transaction_top_merchants.csv')")
md("""## 4. Digital behavior

IDENTIFIED DIGITAL EVENTS: customer_id IS NOT NULL.
ANONYMOUS DIGITAL EVENTS: customer_id IS NULL.

Distribuciones separadas por identificación; product_id se trata como cobertura secundaria. Las sesiones se agrupan por el session_id registrado; su intervalo observado no mide necesariamente la duración real. Se cuentan sesiones de múltiples clientes y mixtas antes de proponer su uso en journeys.""")
code("domain.digital(con, context)\nshow('digital_coverage.csv','digital_events_per_customer.csv','digital_identified_categories.csv','digital_anonymous_categories.csv','digital_sessions_numeric.csv','digital_sessions_quality.csv')")
md("""## 5. Service interactions

La tabla incluye llamadas entrantes/salientes, chat, email y video. Duración/espera en segundos con mediana y percentiles, más histogramas de la cola completa. Sentimientos negativos usan las categorías reales Negativo y Muy Negativo.""")
code("domain.service(con, context)\nshow('service_numeric.csv','service_per_customer.csv','service_categories.csv')")
md("""## 6. Transcript coverage & representativeness

La cobertura se calcula sobre todas las interacciones y también sobre llamadas entrantes/salientes. Se usa presencia real del transcript, no solo un flag. Comparaciones WITH/WITHOUT: duración, espera, sentimiento, motivo, canal, agente y mes. Diferencias observadas no prueban mecanismo causal de selección; semejanza no descarta sesgo.

Después se describen caracteres y palabras (separación por espacios). No se exporta texto ni se ejecutan modelos de lenguaje.""")
code("domain.transcripts(con)\nshow('transcript_coverage.csv','transcript_selection_numeric.csv','transcript_selection_categories.csv','transcript_selection_monthly.csv','transcript_text_lengths.csv')")
md("""## 7. Complaints

origin_interaction_id está completamente nulo en el profiling; no hay un join observado a la interacción de origen. Estado, prioridad, asignación y tiempos se analizan tal como se registran. Nulos de resolución/cierre se calculan por estado.

El estado snapshot no permite reconstruir qué estaba abierto en el corte. open_complaint_count queda NULL explícitamente; se ofrece no_observed_resolution_by_cutoff_count como otra variable, sin equipararla a abierto. Las resoluciones posteriores al corte no entran en las features.""")
code("domain.complaints(con, context)\nshow('complaint_conditional_nulls.csv','complaint_lifecycle.csv','complaint_resolution_by_status.csv','complaint_money_by_currency.csv','complaint_categories.csv')")
md("""## 8. Satisfaction

Se comparan interacciones con/sin survey antes de interpretar scores. CSAT, CES y NPS se mantienen separados; no se mezclan sus escalas. Preguntas se agrupan por texto y tipo de encuesta. Desgloses por motivo/canal/agente utilizan enlaces con cliente y agente coincidentes. avg_satisfaction/latest_satisfaction de las features usan CSAT y corte de fecha, sin afirmar representatividad de todas las llamadas.""")
code("domain.satisfaction(con, context)\nshow('survey_coverage.csv','survey_selection_numeric.csv','survey_selection_categories.csv','survey_scores_by_type.csv','survey_questions.csv','survey_scores_by_interaction.csv')")
md("""## 9. Campaigns

Se reportan flags marginales y funnel estricto sent → delivered → opened → clicked → converted. Se revisan violaciones entre pasos y la coherencia de had_conversion con conversion_date. Nulos sin conversión no son errores por sí mismos. La moneda de send_cost/conversion_value no está documentada; sus sumas no se interpretan como USD.""")
code("domain.campaigns(con, context)\nshow('campaign_dimension_summary.csv','campaign_funnel.csv','campaign_performance.csv','campaign_categories.csv')")
md("""## 10. Branch analysis

Relaciones no confiables de profiling: customers.registration_branch_id (149.995 sin match / 150.000 no nulas) y service_agents.assigned_branch_id (831 / 833). Se documentan y excluyen.

Se usan productos.opening_branch_id y transactions.branch_id tras validar referencias. Branch known y unknown se separan; geografía describe la sucursal, no domicilio del cliente.""")
code("domain.branches(con)\nshow('branch_validation.csv','branch_geography.csv','branch_relationship_limitations.csv')")
md("""## 11. Exchange rate consistency

Se inspeccionan pares source_currency/target_currency y se contrastan multiplicación y división en ambas direcciones, con la fecha calendario exacta. Tolerancia: max(0.02 USD, 1% de amount_usd). Se reporta cobertura de tasas; no se hace forward-fill. Un buen ajuste es evidencia empírica de compatibilidad, no una definición contractual de unidades. Si no hay ajuste claro, la dirección queda como hipótesis.""")
code("ready.exchange(con)\nshow('exchange_rate_pairs.csv','exchange_rate_validation.csv','exchange_rate_coverage.csv')")
md("""## 12. Customer-level analytical features

Agregados independientes por customer_id, unidos sobre el universo de clientes. No hay join evento-a-evento. Se validan unicidad/no nulos en cada tabla y COUNT(*) = COUNT(DISTINCT customer_id) final. La falta de observaciones en un dominio permanece NULL y se acompaña de un indicador; no se imputa.

Las features excluyen atributos snapshot ambiguos (segmento, saldos, score, income, estados). Fechas de eventos y resultados están limitadas al corte explícito; la disponibilidad histórica de revisiones sigue sin ser demostrable con este extracto.""")
code("output.customer360(con, context)\nshow('feature_cardinality.csv','feature_temporal_audit.csv','customer_feature_distributions.csv')")
md("""## 13. Preliminary cross-domain analysis

Cinco preguntas: actividad digital ↔ interacciones; transacciones ↔ reclamos; reclamos ↔ CSAT; espera ↔ CSAT; frecuencia de interacción ↔ CSAT. Se reportan Pearson, Pearson con log1p(x), Spearman y grupos por cuantiles, con n de clientes observados en ambos dominios. No hay interpretación causal ni correlaciones masivas.""")
code("show('cross_domain_associations.csv','cross_domain_groups.csv')")
md("""## 14. Outputs

Tablas completas y features Parquet en reports/eda/. Cuatro figuras en reports/figures/eda/: cobertura mensual, montos USD, duración/espera y cobertura temporal de selección.""")
code("""output.figures()
for name in ['monthly_coverage.png','amount_usd_distribution.png','service_duration_wait.png','selection_coverage.png']:
    display(Image(filename=str(FIG / name)))
output.findings(context)
finish(con, context)
show('key_eda_metrics.csv')""")
md("## EDA Findings & Implications for Customer Journey Discovery\n\n### Confirmed findings\n\nResultados demostrados y limitaciones específicas se generan desde los artefactos ejecutados.")
code("display(Markdown((OUT / 'EDA_FINDINGS.md').read_text()))")
md("""### Data limitations

Consultar el informe anterior: claves discordantes, cobertura parcial, fechas de proceso, snapshot de estados y atributos, monedas no documentadas y ausencia de enlaces de origen en complaints.

### Hypotheses

Las preguntas del informe se proponen para revisar en 03_dispute_case_workflow_discovery.ipynb. La ejecución termina aquí para revisión del EDA.""")
nb.cells=cells
nbformat.write(nb,ROOT/"notebooks/02_eda.ipynb")
