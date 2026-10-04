# AGENTS.md

## 1. Objetivo del proyecto

Este repositorio implementa un MVP para el **Factored AI & Data Hackathon 2026**.

El caso de uso congelado es:

> **Transaction Dispute Intake & Investigation Copilot**

El sistema debe asistir a un cliente autenticado que reporta una transacción no reconocida, extraer pistas estructuradas, recuperar candidatos mediante lógica determinística, preservar la incertidumbre, exigir confirmación explícita, verificar ownership, recolectar evidencia trazable y registrar un handoff humano seguro.

El resultado observable final del MVP es:

> **HANDOFF_RECORDED — no DISPUTE_RESOLVED**

El sistema **no** adjudica disputas, no determina fraude de forma autónoma, no mueve dinero, no autoriza compensaciones y no inventa política bancaria.

---

## 2. Autoridad de alcance y orden de precedencia

Antes de implementar cualquier cambio, inspeccionar los archivos reales del repositorio.

El orden de autoridad es:

1. `reports/FROZEN_MVP_CONTRACT.md`
2. artefactos congelados de evaluación en `artifacts/` / `evals/`
3. `docs/DETERMINISTIC_CASE_RUNTIME.md`
4. `reports/CASE_RUNTIME_DELIVERY.md`
5. este `AGENTS.md`
6. `IMPLEMENTATION_PLAN.md`
7. prompts de tareas puntuales

Si dos documentos se contradicen, **no sobrescribir silenciosamente ninguno**. Documentar la contradicción y seguir el artefacto de mayor autoridad.

`mvp-contract-v1` y el baseline/evaluation set asociado se consideran congelados. Cambios a scope, schemas, labels, fixtures de test o criterios de éxito requieren nueva versión y revisión explícita.

---

## 3. Estado actual del proyecto

### Cerrado / congelado

- Dataset inventory.
- Ingestion/profiling analítico.
- EDA general.
- Transaction-dispute EDA addendum.
- Workflow discovery.
- `04_mvp_use_case_definition.ipynb`.
- `05_baseline_and_eval_dataset.ipynb`.
- Frozen MVP Contract v1.
- Baseline de extracción regex y fixtures de retrieval/safety.

### Implementado

- Runtime determinístico de casos.
- Persistencia SQLite.
- Versionado y control de concurrencia.
- Idempotencia.
- Confirmación explícita de candidato.
- Ownership revalidado.
- `as_of_time` y controles temporales.
- Evidencia con provenance.
- Handoff local durable e idempotente.
- Auditoría de comandos/transiciones/rechazos.

### Pendiente para el MVP competitivo

- Integrar el runtime nuevo con la capa FastAPI usada por la demo.
- Implementar serving read-only sobre el dataset real / DuckDB o equivalente.
- Integrar identidad/sesión confiable de demo con el runtime nuevo.
- Implementar y evaluar el componente AI aprendido de structured intake extraction.
- Clarification conversacional evaluada.
- Grounded summary/handoff narrative evaluado.
- Suite adversarial end-to-end con LLM cuando exista.
- Medición de latencia/costo end-to-end.
- UI integrada al runtime nuevo.
- Deployment reproducible y working link.
- Demo ES/PT y evaluación segmentada.
- Slides y video final.

---

## 4. Principios no negociables

1. No inventar archivos, columnas, tablas, claves, relaciones, métricas, políticas, estados o resultados.
2. No modificar, eliminar ni sobrescribir datos raw.
3. No tratar una coincidencia heurística como ground truth.
4. `candidate != confirmed disputed transaction`.
5. Un candidato único nunca autoriza selección automática: exige confirmación explícita.
6. El LLM no tiene autoridad sobre autenticación, autorización, ownership, selección ambigua, política, dinero, cierre ni adjudicación.
7. Toda autorización se valida fuera del texto generado por el modelo.
8. Toda consulta de datos sensibles se limita al principal autenticado y su scope.
9. Toda evidencia debe tener provenance/source reference y respetar `as_of_time`.
10. Los fallos deben terminar en comportamiento seguro: deny, clarify, abstain o handoff; nunca en datos inventados.
11. El sistema sólo reporta acciones cuyo resultado fue verificado.
12. No almacenar ni usar chain-of-thought como evidencia o auditoría.
13. No agregar nuevos workflows bancarios salvo blocker material y nueva decisión de scope.
14. No introducir RAG, embeddings, multi-agent u otra infraestructura si no mejora directamente el use case congelado, evaluación, seguridad, reproducibilidad, demo o deployment.

---

## 5. Frontera AI vs determinístico vs humano

### AI / LLM permitido

- extraer pistas estructuradas del lenguaje natural;
- proponer preguntas de aclaración;
- redactar explicaciones de incertidumbre;
- generar un resumen grounded usando evidencia suministrada;
- redactar un handoff para revisión humana.

Toda salida AI es no confiable hasta validación de schema, provenance y reglas determinísticas.

### Determinístico obligatorio

- autenticación y validación de sesión;
- autorización y scope;
- ownership;
- búsqueda y filtros de candidatos;
- moneda/unidades;
- `as_of_time` y ventanas temporales;
- guards y state transitions;
- idempotencia;
- persistencia;
- policy interface;
- auditoría;
- validación estructural de outputs AI.

### Humano / autoridad externa

- ambigüedad no resuelta;
- excepciones de política;
- adjudicación de disputa;
- decisión de fraude;
- reembolso/compensación;
- movimiento de dinero;
- resultado final y cierre.

---

## 6. Reglas de datos

- Detectar la ubicación real del dataset mediante inspección; no hardcodear rutas locales.
- La capa raw es inmutable.
- No duplicar datasets grandes innecesariamente.
- Preferir DuckDB/Parquet/Polars para serving analítico del dataset grande.
- Mantener SQLite sólo como estado operacional del MVP salvo razón explícita para migrar.
- Separar claramente:
  - datos fuente / serving read-only;
  - estado operacional de casos;
  - artefactos de evaluación.
- No utilizar `affected_product_id` u otros campos débiles como prueba de complaint→transaction si el análisis congelado no los valida.
- No mezclar monedas ni inferir una moneda por país o símbolo ambiguo.
- No usar outcome/resolution posteriores como evidencia disponible al intake.
- Si faltan timestamps de ingestion/revision, declarar la limitación de disponibilidad histórica.

---

## 7. Serving y tools

El LLM nunca debe ejecutar SQL arbitrario ni acceder directamente a tablas bancarias.

La integración debe conservar una frontera estable tipo:

```text
FastAPI / Application Adapter
        ↓
CaseService
        ↓
bounded deterministic tools
        ↓
read-only banking serving layer
```

Las tools deben:

- recibir principal autenticado y `as_of_time` cuando corresponda;
- validar ownership;
- devolver outputs tipados;
- devolver errores explícitos y seguros;
- incluir provenance/evidence refs;
- no revelar datos de otros clientes;
- ser testeables sin LLM.

El runtime determinístico existente es la autoridad del workflow. Un orquestador conversacional, LangGraph o equivalente puede coordinar conversación, pero no puede duplicar ni saltar los guards de `CaseService`.

---

## 8. AI / ML y baseline

El componente aprendido seleccionado es **Structured Dispute Intake Extraction**.

Reglas:

- comparar contra el baseline congelado usando el mismo schema y held-out workload;
- no modificar labels/test cases después de ver resultados sin crear nueva versión;
- reportar ES y PT por separado;
- declarar PT como team-generated/synthetic mientras no exista cobertura observada;
- medir por campo y full-schema, no sólo una métrica agregada;
- contabilizar hallucinated/unsupported fields;
- mantener candidate retrieval y safety guards idénticos entre baseline y propuesta para aislar el aporte aprendido;
- congelar prompt/model/version antes de puntuar el test final;
- si se usa LLM-as-judge, definir rúbrica y validar una muestra contra juicio humano o determinístico.

No entrenar un modelo de fraude/ranking como dependencia del MVP salvo nueva evidencia que justifique cambiar el contrato.

---

## 9. Evaluación end-to-end

La evaluación final debe incluir, con conteos y denominadores:

- extracción estructurada;
- clarification correctness;
- candidate-set correctness en fixtures controladas;
- abstention correctness;
- handoff correctness y completeness;
- missed handoffs;
- unnecessary handoffs cuando exista referencia;
- unsafe outcomes;
- authorization/ownership violations;
- prompt-injection behavior del sistema con LLM;
- tool failures;
- expired/invalid session;
- missing/inconsistent data;
- ES/PT;
- p50/p95 latency;
- model/tool cost por caso intentado;
- tool failure rate.

No presentar un resultado offline como mejora de producción.
No presentar cero fallos en una muestra pequeña como prueba de riesgo cero.

---

## 10. API y UI

La API/UI legado no debe presentarse como integración del MVP nuevo mientras no llame al runtime determinístico.

Prioridad:

1. conectar FastAPI con `CaseService`;
2. conectar tools con dataset real read-only;
3. conectar UI con esa API;
4. recién entonces añadir/pulir experiencia LLM.

La UI debe demostrar al menos:

- normal path;
- ambiguous/clarification path;
- human-handoff path;
- safety denial opcional pero recomendado.

No construir CRM, dashboards o múltiples journeys fuera del scope.

---

## 11. Seguridad

Como mínimo probar:

- cross-customer access;
- expired/invalid principal;
- scope insuficiente;
- prompt injection;
- tool timeout/error;
- datos faltantes o contradictorios;
- candidate none/single/multiple;
- intento de acción financiera;
- unsupported request;
- retries/idempotency;
- leakage temporal/future transaction;
- Portuguese ambiguity.

Los tests del runtime sin LLM no pueden reportarse como prueba de prompt-injection robustness del LLM.

Secrets y credenciales nunca deben quedar versionados ni exponerse en logs, reportes, notebooks o entregables públicos.

---

## 12. Código y reproducibilidad

- Python 3.12+ salvo restricción real del deployment.
- `pathlib` para rutas.
- Nada de rutas absolutas de desarrollador.
- Preferir funciones y componentes pequeños sobre abstracción innecesaria.
- Mantener contratos tipados.
- Ejecutar linters/tests relevantes antes de cerrar cambios.
- No cambiar artefactos congelados para hacer pasar tests.
- Seeds fijas cuando aplique sampling/generación reproducible.
- Los notebooks deben ejecutar de arriba abajo sin estado oculto.
- Resultados importantes deben persistirse en artefactos/reports versionados.

---

## 13. Definition of Done de una tarea

Antes de declarar una tarea completada verificar:

1. el cambio corresponde al MVP congelado;
2. tests relevantes pasan;
3. no se modificó raw;
4. no se modificó silenciosamente un artefacto congelado;
5. no se introdujo ground truth falso;
6. auth/ownership/time boundaries siguen vigentes;
7. errores y missingness permanecen explícitos;
8. existe trazabilidad de inputs, outputs y versiones;
9. documentación/README se actualizó si cambió comportamiento real;
10. se distingue claramente entre IMPLEMENTED, TESTED, MOCKED, SYNTHETIC, FUTURE DESIGN y NOT MEASURED.

---

## 14. Prioridad hasta la entrega

Ante cualquier nueva tarea, priorizar en este orden:

1. vertical slice end-to-end sobre el runtime correcto;
2. serving real del dataset;
3. componente AI evaluado contra baseline;
4. safety/evals end-to-end;
5. UI/demo ES/PT;
6. deployment;
7. observabilidad/latencia/costo;
8. slides/video/documentación final.

Postergar cualquier trabajo que no mejore directamente uno de esos puntos.
