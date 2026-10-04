"""Create canonical notebooks 04/05 and safe redirects from unexecuted placeholders."""
from pathlib import Path
import nbformat as nbf

ROOT=Path(__file__).resolve().parents[1]


def notebook(title,sections,setup):
    n=nbf.v4.new_notebook()
    n.metadata.kernelspec=dict(display_name="Python 3",language="python",name="python3")
    n.cells=[nbf.v4.new_markdown_cell("# "+title),nbf.v4.new_code_cell(setup)]
    for heading,explanation,code in sections:
        n.cells.append(nbf.v4.new_markdown_cell("## "+heading+"\n\n"+explanation))
        if code:
            n.cells.append(nbf.v4.new_code_cell(code))
    nbf.validate(n)
    return n


common="""from pathlib import Path
import sys, json
from collections import Counter
from IPython.display import display, Markdown
ROOT = Path.cwd()
if not (ROOT / "AGENTS.md").exists():
    ROOT = ROOT.parent
assert (ROOT / "AGENTS.md").exists()
assert sys.version_info >= (3, 12)
sys.path.insert(0, str(ROOT))
"""
headings=["Executive Decision","Problem Evidence","User Problem","Business Problem","Scope",
    "AI / Deterministic / Human Responsibility Matrix","Workflow","Data Contracts","Evidence Model",
    "Time Safety","Success Criteria","Demo Scenarios","Frozen MVP Contract"]
n04=notebook("MVP Use Case Definition",[(h,"Definición formal basada en discovery existente; no análisis nuevo.",
    f"display(Markdown(sections[{h!r}]))") for h in headings],
    common+"from src.mvp_definition import define\nsections = define()\nprint('Frozen MVP: GO WITH CONSTRAINTS; no runtime implemented')")
sections=[
    ("1. Evaluation Strategy",
     "Baseline: trusted fixture request → regex extraction → offline deterministic retrieval checks → static wording. "
     "Proposed learned system preserves schema, guards and fixtures; only extraction/clarification/summary differ. "
     "Auth and policy are future external dependencies, not implemented services.",""),
    ("2. Learned Component — Structured Dispute Intake Extraction",
     "Eight fields; unknown clues NULL, intent unknown. Dates can be symbolic relative hints; never invent as_of. "
     "No fraud/ranking learned dependency. No LLM execution.",
     "from src.evaluation.baseline_intake_parser import FIELDS, extract, schema_valid\nprint(FIELDS)"),
    ("3. Deterministic Baseline",
     "Regex/keywords, decimal parsing and calendar validation. Explicit contradictions remain unknown. "
     "No inference of currency from dollar sign or customer country; v1 fixture-ID grammar is limited.",
     """demo = extract('No reconozco 12,50 USD del 2026-06-10.')
display(demo)
assert schema_valid(demo)"""),
    ("4. Versioned Evaluation Dataset",
     "Reuse only known transaction attributes from 03 Parquet, not inferred complaint links. IDs become fixture aliases. "
     "Gold values are authored independently of parser predictions. Frozen files reject silent replacement.",
     """from src.evaluation.dataset import generate, OUT
cases, fixtures = generate()
display({"cases": len(cases), "source_types": dict(Counter(c["source_type"] for c in cases)),
         "languages": dict(Counter(c["language"] for c in cases))})"""),
    ("5. Case Generation & Provenance",
     "All new utterances are synthetic/team-generated, even when attributes are observed-derived. "
     "No sensitive source text is copied; human ES/PT annotation review remains pending. "
     "Cases cover explicit IDs, amount, currency, merchant, absolute/relative dates, contradictions, missing clues and unsupported requests.",
     'display(dict(Counter(c["scenario"] for c in cases)))'),
    ("6. Development / Held-out Test",
     "Group split by source customer and transaction fingerprint; all language/paraphrase variants stay together. "
     "12 groups → 6 development and 6 test. Not a temporal holdout. Shared scenario families limit generalization claims.",
     """dev = {c["group_id"] for c in cases if c["split"] == "development"}
test = {c["group_id"] for c in cases if c["split"] == "test"}
assert dev.isdisjoint(test)
display({"groups_dev":len(dev),"groups_test":len(test),"split_counts":dict(Counter(c["split"] for c in cases))})"""),
    ("7. Structured Extraction Metrics",
     "Per-field exact match, precision/recall/F1 and null correctness; full-schema EM, schema validity, hallucination "
     "on unknown slots/predicted slots, missing clues and clarification accuracy. Wrong values are both FP and FN. "
     "Undefined denominators remain NULL. Expected missing fields and required search clues are separate.",""),
    ("8. Controlled Retrieval Fixtures",
     "A–H plus invalid/expired auth and exact as_of boundary. Table rows and expected sets are authored fixtures, "
     "not complaint-derived labels; never report observed complaint-to-transaction recall.",
     'display(dict(Counter(f["fixture_type"] for f in fixtures)))'),
    ("9. Retrieval Metrics",
     "Exact candidate set, explicit-ID correctness, missing/extra candidates, future/ownership/unauthorized exposure, "
     "zero-candidate correctness and ambiguity preservation. The offline reference function is not a production tool.",""),
    ("10. Handoff Quality Rubric",
     "Check required sections, structured claims against cited evidence, and valid references. Section presence is "
     "not semantic completeness; prose requires human review. No LLM judge.",
     "from src.evaluation.metrics import HANDOFF_FIELDS\nprint(HANDOFF_FIELDS)"),
    ("11. Safety Test Cases",
     "Expected deny/clarify/abstain/handoff behavior. Auth, ownership and temporal fixture boundaries are measurable now; "
     "prompt-injection runtime defenses, orchestration, policy and closure remain contract-only.",
     """safety = [json.loads(line) for line in (OUT / "safety_fixtures.jsonl").read_text().splitlines()]
display([{"scenario":s["scenario"],"expected":s["expected_behavior"]} for s in safety])"""),
    ("12. Language Coverage",
     "Spanish and Portuguese test sets remain separate. Source transcripts are labeled es only; Portuguese utterances "
     "are explicitly generated, not observed Portuguese behavior. No linguistic generalization claim.",
     'display(dict(Counter((c["split"],c["language"]) for c in cases)))'),
    ("13. Baseline Implementation",
     "src/evaluation/baseline_intake_parser.py is the text-only baseline. Unit tests cover ambiguity, invalid dates, "
     "unknown currency, schema and controlled retrieval guards. No service, auth implementation or state engine is built.",""),
    ("14. Baseline Results",
     "Freeze dataset/code signatures before scoring. Run once on both splits; do not tune after test results. "
     "Keep failures visible. No external model calls. Local parser latency is not end-to-end latency.",
     """from src.evaluation.run_baseline import run, report
results = run()
display({k:{"n":v["cases"],"full_schema_EM":v["full_schema_exact_match"],
            "schema_valid":v["schema_valid_rate"],"clarify_accuracy":v["should_clarify_accuracy"],
            "hallucinated_fields":v["hallucinated_fields"]}
         for k,v in results["extraction"].items()})
display(results["retrieval"])
display(results["parser_latency_ms"])
findings = report(results)
display(Markdown(findings))"""),
    ("15. Evaluation Contract for the Future LLM",
     "Input: user_utterance only. Output: validated eight-field schema, no extra keys. "
     "Unknowns NULL; relative dates symbolic; expected labels never passed to model. "
     "Freeze model/prompt/version before test and compare against the same deterministic guards.",
     'display(json.loads((OUT / "future_llm_evaluation_contract.json").read_text()))'),
]
n05=notebook("Baseline and Evaluation Dataset",sections,common)
for name,n in [("04_mvp_use_case_definition.ipynb",n04),("05_baseline_and_eval_dataset.ipynb",n05)]:
    nbf.write(n,ROOT/"notebooks"/name)
print("Created canonical 04/05; retained safe legacy references.")
