"""Build the new, separately named stage-03 notebook; leave existing notebooks intact."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
nb.metadata.kernelspec = dict(display_name="Python 3",language="python",name="python3")
cells = [nbf.v4.new_markdown_cell("""# Dispute Case Workflow Discovery

¿Qué workflow stateful y auditable soportan realmente los datos?

Etapa posterior al EDA/addendum: no rehace profiling y no implementa agentes, modelos, APIs,
políticas, UI ni acciones financieras. Las relaciones complaint–transaction son **candidatas**.
Las cohortes, reglas y arquetipos son HEURISTIC; el diseño de estados es FUTURE DESIGN.
Todos los porcentajes indican denominador; monedas separadas; nulos y ventanas censuradas visibles.
""")]
cells.append(nbf.v4.new_code_cell("""from pathlib import Path
from contextlib import ExitStack
import sys
import pandas as pd
from IPython.display import display, Markdown

ROOT = Path.cwd()
if not (ROOT / "AGENTS.md").exists():
    ROOT = ROOT.parent
assert (ROOT / "AGENTS.md").exists()
assert sys.version_info >= (3, 12)
sys.path.insert(0, str(ROOT))
from src.dispute_workflow_data import ART, sources, cohorts, retrieval, temporal_direction
from src.dispute_workflow_context import (characteristics, behavior, service, transcripts,
    digital, bundles, archetypes)
from src.dispute_workflow_design import future_design, validate, report

def show(name, limit=24):
    # Read only aggregate CSVs; string dtype preserves leading-zero response codes.
    frame = pd.read_csv(ART / name, dtype=str, keep_default_na=False)
    display(frame.head(limit))
    if len(frame) > limit:
        print(f"Displayed {limit}/{len(frame)} aggregate rows. Full table: {name}")

resources = ExitStack()
con, context = resources.enter_context(sources())
display({k:v for k,v in context.items() if k != "protected_artifacts_sha256"})
show("population_cutoff_audit.csv")
"""))
sections = [
    ("1. Candidate dispute cohorts",
     "A/B/C usan exclusivamente valores observados. B está contenida en A; no sumar cohortes. "
     "Las coberturas de resolución y estados son retrospectivas, no evidencia de intake.",
     """cohorts(con, context)
show("candidate_dispute_cohorts.csv")
show("candidate_cohort_definitions.csv")
show("cohort_overlap.csv")
show("candidate_cohort_distributions.csv", 60)
show("retrieval_population.csv")"""),
    ("2. Customer transaction search space",
     "customer_id es el único enlace de búsqueda. Ventanas simétricas de ±24*n horas inclusivas. "
     "La censura en extremos queda contada; cero candidatos no es un NULL.",
     """retrieval(con, context)
show("complaint_transaction_window_summary.csv")"""),
    ("3. Claimed amount + currency narrowing",
     "Comparaciones DECIMAL exactas dentro de moneda; tolerancias 1 unidad, 1% y 5% explícitas. "
     "Las relativas usan abs(claimed_amount) y no son elegibles en cero. Un candidato único no es un match verdadero.",
     """show("amount_currency_candidate_matching.csv", 45)
show("candidate_rules_common_eligibility.csv", 20)"""),
    ("4. Temporal directionality",
     "Día calendario y timestamp son ejes diferentes. Bins contiguos sin huecos; proximidad no causalidad. "
     "Transacciones posteriores al reclamo son retrospectivas e inadmisibles al intake.",
     """temporal_direction(con)
show("temporal_candidate_distribution.csv", 40)"""),
    ("5. Candidate transaction attributes",
     "Comparar poblaciones deduplicadas: todas al cutoff; historia del mismo cliente antes de su último "
     "reclamo de interés; candidatos únicos ±30d. La historia agregada de comparación no es feature as-of por reclamo.",
     """characteristics(con)
show("candidate_transaction_characteristics.csv", 40)"""),
    ("6. Behavioral context feasibility",
     "Solo timestamps estrictamente anteriores; misma moneda para medianas. Se conserva NULL sin historia monetaria "
     "o sin merchant. Contadores cero describen ausencia observada. Revisiones/availability desconocidas impiden certificar PIT productivo.",
     """behavior(con)
show("behavioral_feature_feasibility.csv")"""),
    ("7. Fraud signal feasibility — without fraud_score",
     "Clases gravemente desbalanceadas. Comparaciones descriptivas por moneda y completitud de historia; "
     "sin significancia predictiva, modelo ni threshold. status también requiere revisión de disponibilidad histórica.",
     """show("fraud_signal_without_score.csv", 40)
show("fraud_amount_without_score_by_currency.csv")
show("fraud_prior_behavior_without_score.csv", 30)"""),
    ("8. Service interaction proximity",
     "Ventanas posteriores disjuntas [0,24h], (24,72h], (72,168h], (168,336h]. "
     "Mismo cliente y cercanía temporal no prueban referencia a la transacción. Denominadores de pares y contactos únicos separados.",
     """service(con)
show("service_interaction_proximity.csv")
show("service_proximity_distributions.csv", 30)"""),
    ("9. Transcript availability",
     "La disponibilidad usa interacciones únicas, no pares repetidos. Metadatos excluidos de la caché se "
     "recuperan como flags de presencia desde raw, sin exponer su contenido. []/{} no cuentan como contenido.",
     """transcripts(con)
show("transcript_feasibility.csv")
show("transcript_metadata_feasibility.csv")
show("transcript_selection_comparison.csv", 40)"""),
    ("10. Identified digital context",
     "Se excluyen eventos anónimos sin identity stitching. Ventanas before anidadas, no aditivas; "
     "after es retrospectiva. product_id y event_value no se interpretan como enlace causal ni importe de transacción.",
     """digital(con, context)
show("digital_context_feasibility.csv")
show("digital_event_value_availability.csv")
show("digital_context_distributions.csv", 25)"""),
    ("11. Derived evidence bundles",
     "Grano complaint/candidate_transaction, sin campo de match verdadero. Agregados independientes evitan "
     "multiplicación de eventos. Conteos hasta intake y retrospectivos separados. case_register conserva casos sin candidato. "
     "Los Parquet con IDs no se muestran ni se usan para seleccionar clientes demo.",
     """bundles(con)
show("evidence_bundle_summary.csv")"""),
    ("12. Transparent candidate narrowing — no learned ranking",
     "Reglas individuales y combinaciones, sin pesos ni probabilidades. La tabla common_eligibility mantiene "
     "la misma población al comparar reglas; antes del reclamo se evalúa también por separado.",
     """show("candidate_rule_comparison.csv", 40)
show("candidate_rules_common_eligibility.csv", 40)"""),
    ("13. Observed case archetypes",
     "Arquetipos heurísticos solapados. Se exportan únicamente los existentes, con población y manejo sugerido. "
     "No se usa el nombre high-confidence para una coincidencia sin ground truth.",
     """archetypes(con)
show("case_archetypes.csv", 30)"""),
    ("14. Workflow responsibility matrix",
     "FUTURE DESIGN: dueños propuestos y riesgos, no capacidades ya implementadas o evaluadas. "
     "ML no es dependencia aprobada; LLM no controla autenticación, ownership, política o dinero.",
     """future_design()
show("workflow_responsibility_matrix.csv")"""),
    ("15. Proposed case state machine",
     "Solo especificación CSV/JSON. La falta de política/autoridad obliga revisión humana. HANDOFF_RECORDED "
     "es distinto de RESOLVED/CLOSED; cada transición define evidencia, guardas y ruta de fallo.",
     """show("proposed_case_state_machine.csv", 30)"""),
    ("16. MVP recommendation and validation",
     "Comparar inquiry, investigation, intake+handoff y adjudicación autónoma. "
     "El informe distingue hechos, hipótesis y diseño futuro y responde las diez preguntas de cierre.",
     """show("mvp_scope_assessment.csv")
validate(con)
findings = report(context)
resources.close()
print((ART / "integrity.json").read_text())
display(Markdown(findings))"""),
]
for title, explanation, code in sections:
    cells += [nbf.v4.new_markdown_cell("## "+title+"\n\n"+explanation),nbf.v4.new_code_cell(code)]
nb.cells = cells
nbf.validate(nb)
nbf.write(nb,ROOT/"notebooks/03_dispute_case_workflow_discovery.ipynb")
print("Created stage-03 dispute case workflow discovery notebook")
