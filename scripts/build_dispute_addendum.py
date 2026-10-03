"""Build only the addendum notebook; never replace the general EDA."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
nb.metadata.kernelspec = dict(display_name="Python 3", language="python", name="python3")
cells = []


def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))


def code(text):
    cells.append(nbf.v4.new_code_cell(text))


md("""# Transaction Investigation & Dispute — EDA Addendum

Pregunta: ¿hay suficiente señal, cobertura y calidad para justificar discovery?

Este notebook complementa, sin reemplazar, 02_eda.ipynb y reports/eda/EDA_FINDINGS.md.
No construye journeys, matching, modelos, thresholds, agentes ni una arquitectura.
Los resultados completos y denominadores se exportan a artifacts/eda_transaction_dispute/.
Las tablas pequeñas usan pandas solo para presentación; los cálculos completos usan DuckDB.
No se consultan fuentes externas, no se imputan datos ni se eliminan extremos.
""")
code("""from pathlib import Path
import sys
from contextlib import ExitStack
import pandas as pd
from IPython.display import display, Markdown

ROOT = Path.cwd()
if not (ROOT / "AGENTS.md").exists():
    ROOT = ROOT.parent
assert (ROOT / "AGENTS.md").exists()
assert sys.version_info >= (3, 12)
sys.path.insert(0, str(ROOT))
from src.dispute_eda import (ART, sources, fraud_label, fraud_scores, taxonomy,
    claimed_amount, transaction_evidence, geography, status_evidence, outcomes, label_distributions)
from src.dispute_reporting import build_report, validate_artifacts

def show(name, limit=30):
    # Strings preserve codes such as 00 and explicit NULL display.
    frame = pd.read_csv(ART / name, dtype=str, keep_default_na=False)
    display(frame.head(limit))
    if len(frame) > limit:
        print(f"Shown {limit}/{len(frame)} aggregate rows; full table: {name}")

resources = ExitStack()
con, context = resources.enter_context(sources())
display(context)
show("population_cutoff_audit.csv")
""")
md("""## 1. Transaction fraud label

Población principal: extracto completo. fraud_rate = True / labels booleanas válidas.
Se exporta también el subconjunto cuya fecha de transacción no supera el cutoff heredado;
esto no prueba disponibilidad histórica de la etiqueta. Las siete dimensiones retienen NULLs.
""")
code("""fraud_label(con, context)
show("fraud_label_summary.csv")
for dimension in ("transaction_status", "transaction_type", "transaction_category",
                  "channel", "transaction_country", "currency", "merchant_category"):
    show(f"fraud_by_{dimension}.csv")
""")
md("""## 2. fraud_score vs is_fraud

Cuantiles exactos sobre scores numéricos finitos; NULL/invalid fuera del denominador
numérico, pero contados explícitamente. Buckets fijados por el pedido, sin optimización.
Comparar asociación no equivale a evaluar un modelo ni autorizar un threshold.
""")
code("""fraud_scores(con)
show("fraud_score_by_label_state.csv")
show("fraud_score_buckets.csv")
for dimension in ("transaction_status", "channel", "transaction_type"):
    show(f"fraud_score_by_{dimension}.csv")
""")
md("""## 3. Complaint taxonomy

Tablas con denominador total de complaints y cobertura de monto dentro de cada combinación.
Se anotan únicamente categorías observadas, sin definir un cohort ni inferir subtipos ausentes.
""")
code("""taxonomy(con)
show("complaint_case_category.csv")
show("complaint_category_subcategory.csv")
show("complaint_taxonomy.csv", 50)
show("requested_themes_taxonomy_evidence.csv")
""")
md("""## 4. claimed_amount usability

Cobertura sobre todas las filas de cada grupo; distribuciones monetarias separadas por
currency. p99/p99.9 describen colas, no justifican borrar extremos. Transactions y Fees
son una vista exploratoria de categorías reales, no un cohort aprobado ni matching.
""")
code("""claimed_amount(con)
show("complaint_claimed_amount_coverage.csv", 60)
show("claimed_amount_checks_overall.csv")
show("claimed_amount_by_currency.csv")
show("claimed_amount_upper_tail_by_currency.csv")
show("potential_transaction_taxonomy_amount.csv", 50)
""")
md("""## 5. Transaction evidence coverage

valid_count significa presente y compatible con una prueba básica explícita de tipo/rango;
no significa verdad de negocio. NULL y no-nulos inválidos se reportan por separado.
Las 21 columnas se evalúan también por canal, tipo y estado. Unicidad se valida sin joins.
""")
code("""transaction_evidence(con)
show("transaction_identifier_check.csv")
show("transaction_evidence_coverage.csv", 21)
""")
md("""## 6. Transaction geography viability

Cobertura de país, ciudad, coordenadas individuales y pares. Rangos físicos no validan
correspondencia con una ubicación real. No geocoding, corrección ni features de anomalía.
""")
code("""geography(con)
show("transaction_geography_coverage.csv", 60)
""")
md("""## 7. transaction_status evidence

Se reutilizan las tablas de fraude/score por estado de secciones 1–2.
Los códigos se conservan como strings: exclusividad observada no demuestra significado.
Los dos porcentajes condicionales muestran denominadores explícitos.
""")
code("""status_evidence(con)
show("status_by_transaction_type.csv", 50)
show("status_by_channel.csv", 50)
show("status_by_response_code.csv")
show("response_code_associations.csv")
""")
md("""## 8. Complaint outcome observability

NULL condicionado al lifecycle; resolución no implica cliente correcto ni compensación
implica fraude. La cobertura se exporta por estado/tipo/categoría tanto global como en
la vista exploratoria Transactions/Fees. No se muestran textos crudos de clientes.
""")
code("""outcomes(con, context)
frame = pd.read_csv(ART / "complaint_outcome_coverage.csv", dtype=str, keep_default_na=False)
display(frame[(frame.dimension == "overall") | ((frame.dimension == "status") &
              frame.field.isin(["resolution", "resolution_date", "closing_date"]))])
show("complaint_resolution_days_by_status.csv")
show("complaint_outcome_cutoff_audit.csv")
""")
md("""## 9. Potential labels — NOT YET APPROVED FOR MODELING

Distribución sobre todas las filas, incluidos NULLs. Bins de compensación describen el signo,
no crean labels de fraude. La recomendación posterior depende de semántica, timing y linkage,
no solamente completitud.
""")
code("""label_distributions(con)
show("potential_label_coverage.csv")
show("potential_label_distributions.csv", 60)
""")
md("""## 10. Decision matrix & reproducible report

Separación de hechos observados, métricas derivadas, hipótesis e interpretaciones.
Las relaciones ya validadas se reutilizan de los resultados del EDA, sin repetirlo.
HIGH/MEDIUM/LOW/UNUSABLE califican disponibilidad y confiabilidad para el uso descrito.
""")
code("""report = build_report(context)
validate_artifacts()
show("potential_labels_assessment.csv")
show("transaction_dispute_evidence_matrix.csv")
resources.close()
print((ART / "integrity.json").read_text())
""")
md("""## Findings & implications for Transaction Dispute Discovery

El reporte siguiente responde las seis preguntas requeridas y es también el entregable Markdown.
La decisión permite únicamente discutir la etapa posterior: no la implementa ni la inicia.
""")
code("display(Markdown(report))")
nb.cells = cells
nbf.validate(nb)
nbf.write(nb, ROOT / "notebooks/02b_transaction_dispute_eda_addendum.ipynb")
print("Built notebooks/02b_transaction_dispute_eda_addendum.ipynb")
