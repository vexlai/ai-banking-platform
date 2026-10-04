# IMPLEMENTATION_PLAN.md 

## 1. Propósito

Este plan parte del estado real del repositorio y del **Frozen MVP Contract v1**. No reabre discovery ni baseline ya cerrados.

MVP:

> **Transaction Dispute Intake & Investigation Copilot**

Resultado final observable:

> **HANDOFF_RECORDED**

No incluye adjudicación, fraude definitivo, compensación, money movement ni cierre autónomo.

---

## 2. Estado actual

### DONE / FROZEN

- [x] Dataset inventory.
- [x] Ingestion/profiling analítico.
- [x] EDA general.
- [x] Transaction-dispute EDA addendum.
- [x] Workflow discovery.
- [x] `04_mvp_use_case_definition.ipynb`.
- [x] Frozen MVP Contract v1.
- [x] `05_baseline_and_eval_dataset.ipynb`.
- [x] 384 utterances authored ES/PT con split agrupado.
- [x] Baseline regex congelado.
- [x] 132 controlled retrieval fixtures.
- [x] Safety-contract fixtures offline.
- [x] Runtime determinístico de casos.
- [x] SQLite persistence/versioning/idempotency.
- [x] Explicit candidate confirmation.
- [x] Ownership/as_of/evidence guards.
- [x] Handoff local durable/idempotente.
- [x] Auditoría de runtime.

### CURRENT GAP

FastAPI ya integra el runtime nuevo mediante /v1/disputes, separado del API/orchestrator/UI legado. La demo HTTP sigue usando fixtures sintéticos y credenciales locales explícitas; no usa serving bancario real ni IAM productivo. Ver reports/APPLICATION_ADAPTER_DELIVERY.md.

---

## 3. Gate 0 — Freeze preservation

Antes de cualquier feature:

- [ ] marcar 04, 05 y `mvp-contract-v1` como read-only lógico;
- [ ] documentar hashes/versiones de eval artifacts usados por CI;
- [ ] impedir overwrite silencioso de baseline/test fixtures;
- [x] actualizar README para distinguir claramente legacy scaffold vs current MVP runtime.

**DoD:** ninguna tarea posterior necesita modificar discovery/baseline para funcionar.

---

## 4. Fase 1 — Secure Application Adapter

### Objetivo

Conectar FastAPI al runtime determinístico nuevo sin duplicar su business logic.

### Tareas

- [x] crear endpoints de casos/disputes que deleguen en `CaseService`;
- [x] mapear errores del dominio a respuestas HTTP seguras;
- [x] exigir principal/session context;
- [x] transportar idempotency key y expected version; generar request_id HTTP (v1 no admite persistirlo en audit);
- [x] exponer estado/audit/handoff sólo dentro del scope autorizado;
- [x] mantener `/health` y compatibilidad de demo cuando sea útil;
- [x] no enrutar el nuevo workflow por el orchestrator legado.

### Endpoints conceptuales

```text
POST /v1/disputes
POST /v1/disputes/{case_id}/search
POST /v1/disputes/{case_id}/confirm
POST /v1/disputes/{case_id}/evidence
POST /v1/disputes/{case_id}/handoff
GET  /v1/disputes/{case_id}
GET  /v1/disputes/{case_id}/audit
GET  /v1/disputes/{case_id}/handoff
```

Rutas implementadas; detalles y ejemplos en docs/SECURE_APPLICATION_ADAPTER.md.

### DoD

- [x] API tests cubren happy/ambiguous/no-candidate/unauthorized/idempotent replay.
- [x] No existe bypass de `CaseService`.
- [x] El flujo nuevo puede ejecutarse completamente vía HTTP usando fixtures.

Validado: 30 tests nuevos API, 103 tests totales; Uvicorn real + reinicio/replay sin duplicados.
Contratos/baseline/fixtures congelados preservados. El verificador histórico de importación
tiene discrepancias preexistentes documentadas; no se afirma CI remoto completo verde.

---

## 5. Fase 2 — Dataset-backed Banking Tools

### Objetivo

Reemplazar fixtures de transacciones por serving read-only sobre el dataset real sin cambiar el contrato del runtime.

### Arquitectura

```text
CaseService
   ↓
TransactionTools interface
   ├── FixtureTransactionTools
   └── DuckDBTransactionTools / equivalent
               ↓
         Parquet / curated dataset
```

### Tareas

- [ ] inspeccionar ubicación y formatos reales;
- [ ] definir queries bounded y parameterized;
- [ ] implementar transaction search;
- [ ] implementar exact transaction lookup;
- [ ] implementar ownership/product lookup;
- [ ] implementar strictly-prior history;
- [ ] preservar `as_of_time`;
- [ ] reportar truncation/missingness;
- [ ] validar performance básica;
- [ ] añadir contract tests compartidos entre fixture y dataset implementation.

### DoD

- [ ] mismos contratos y guards para fixtures y dataset;
- [ ] cero cross-customer leakage en tests;
- [ ] no SQL arbitrario desde LLM/API;
- [ ] tres journeys reproducibles usando datos del dataset o fixtures explícitamente etiquetados cuando no sea posible.

---

## 6. Fase 3 — Trusted Demo Identity / IAM Adapter

### Objetivo

Cumplir identidad confiable sin fingir que `customer_id` escrito por el usuario autentica al cliente.

### Tareas

- [ ] implementar adapter de principal de prueba firmado o mecanismo equivalente;
- [ ] expiración;
- [ ] scope;
- [ ] issuer/audience según mecanismo elegido;
- [ ] revocación o limitación documentada;
- [ ] customer mapping fuera del LLM;
- [ ] registrar rechazos sin filtrar existencia de recursos.

### DoD

- [ ] valid/expired/invalid/cross-customer tests;
- [ ] identidad del texto nunca cambia autoridad;
- [ ] limitaciones de IAM demo documentadas.

---

## 7. Fase 4 — Learned Structured Intake Extraction

### Objetivo

Implementar el componente AI/ML requerido y compararlo con el baseline congelado.

### Tareas

- [ ] seleccionar modelo/provider;
- [ ] prompt/schema versionado;
- [ ] output estructurado y validado;
- [ ] no incluir labels ni principal autoritativo en prompt;
- [ ] congelar configuración antes del test final;
- [ ] correr dev y luego test una sola vez por versión evaluada;
- [ ] medir ES/PT por separado;
- [ ] persistir outputs, latency y cost;
- [ ] error analysis.

### Métricas

- full-schema exact match;
- per-field precision/recall/F1/EM;
- schema validity;
- hallucinated-field rate;
- missing-required-clue exact match;
- should-clarify accuracy;
- p50/p95 latency;
- cost/case.

### DoD

- [ ] comparación baseline vs learned sobre mismo held-out workload;
- [ ] safety guards sin cambios;
- [ ] resultados y limitaciones reproducibles;
- [ ] PT identificado explícitamente como team-generated.

---

## 8. Fase 5 — Controlled Clarification

### Objetivo

Usar AI para redactar/interpretar aclaraciones sin ceder autoridad del workflow.

### Reglas

- preguntar sólo datos útiles y permitidos;
- no inferir moneda/fecha crítica sin confirmación;
- no auto-seleccionar por unicidad;
- máximo de turnos definido por contrato versionado;
- al agotar aclaración, abstain/handoff;
- salida estructurada además de texto.

### DoD

- [ ] casos missing amount/date/currency/merchant;
- [ ] multiple candidates;
- [ ] contradictory clues;
- [ ] no candidate;
- [ ] ES/PT;
- [ ] clarification correctness evaluada con referencias.

---

## 9. Fase 6 — Grounded Summary & Handoff Narrative

### Objetivo

Generar texto útil al humano sin convertirlo en autoridad.

### Tareas

- [ ] construir contexto sólo desde EvidenceBundle allowlisted;
- [ ] requerir evidence refs para factual claims;
- [ ] mantener unknowns/unresolved questions;
- [ ] validar claims estructurados determinísticamente;
- [ ] conservar paquete determinístico incluso si el LLM falla.

### DoD

- [ ] handoff completo sin LLM sigue funcionando;
- [ ] resumen no introduce datos sin evidencia;
- [ ] quality rubric y muestra revisada humanamente.

---

## 10. Fase 7 — End-to-End Safety / Adversarial Suite

### Casos mínimos

- [ ] cross-customer access;
- [ ] expired/invalid auth;
- [ ] prompt injection;
- [ ] request de revelar system prompt/secrets;
- [ ] tool timeout/error;
- [ ] malformed model output;
- [ ] no candidate;
- [ ] multiple candidates;
- [ ] contradictory user claims;
- [ ] future transaction leakage;
- [ ] unauthorized financial action;
- [ ] out-of-scope workflow;
- [ ] Portuguese ambiguity.

### Métricas

- unsafe outcomes con n y denominador;
- missed handoffs;
- unnecessary handoffs;
- auth/ownership violations;
- recovery/fallback correctness.

### DoD

- [ ] ningún caso crítico carece de expected behavior;
- [ ] resultados automatizados persistidos;
- [ ] se distingue runtime-only safety de LLM-integrated safety.

---

## 11. Fase 8 — Evaluation Harness consolidado

### Objetivo

Tener una sola ejecución reproducible que produzca el evidence pack del hackathon.

### Salidas

```text
reports/evaluation/
├── component_metrics.*
├── system_metrics.*
├── safety_metrics.*
├── operational_metrics.*
├── language_breakdown.*
└── error_analysis.*
```

### Debe reportar

- baseline vs learned component;
- system path distribution;
- clarification/handoff correctness;
- unsafe outcomes;
- p50/p95 end-to-end latency;
- cost per attempted case;
- tool failure rate;
- ES/PT breakdown;
- sample sizes y limitaciones.

### Nota

`safe automated resolution` puede ser **not defined / not applicable** si el MVP deliberadamente termina en handoff y no resuelve disputas. No inflar containment como resolución.

---

## 12. Fase 9 — Observability

### Tareas

- [ ] correlation/request ID;
- [ ] principal ref no sensible;
- [ ] state transitions;
- [ ] tool name/result status;
- [ ] retries;
- [ ] model/prompt version;
- [ ] latency;
- [ ] token/cost estimates;
- [ ] handoff reason;
- [ ] audit refs.

### DoD

Un journey completo puede reconstruirse sin chain-of-thought y sin exponer secretos/PII innecesarios.

---

## 13. Fase 10 — Demo UI integrada

### Objetivo

La UI debe llamar a la API que usa el runtime nuevo; no al scaffold legado.

### Customer view

- session state;
- chat/input;
- clarification;
- candidate confirmation;
- safe status/error UX.

### Human view

- user request;
- candidates / selected transaction;
- verified facts;
- evidence refs;
- actions/guards;
- unresolved questions;
- escalation reason;
- handoff receipt.

### DoD

- [ ] normal path;
- [ ] ambiguous path;
- [ ] no-candidate/handoff;
- [ ] safety denial;
- [ ] ES/PT examples.

---

## 14. Fase 11 — Deployment

### Tareas

- [ ] Docker/build reproducible;
- [ ] secrets sólo por environment/secret manager;
- [ ] CORS no wildcard en deployment público si expone rutas sensibles;
- [ ] health/readiness;
- [ ] persistent demo state cuando aplique;
- [ ] working backend + UI URL;
- [ ] smoke E2E post-deploy;
- [ ] capacity/limitations documentadas.

### DoD

- [ ] working link público/compartible;
- [ ] tres journeys estables;
- [ ] safe fallback ante model/tool outage;
- [ ] README reproduce setup local.

---

## 15. Fase 12 — Submission Evidence Pack

### GitHub

- [ ] repo público sanitizado;
- [ ] sin datasets restringidos ni credenciales;
- [ ] README corto con arquitectura, setup, demo, evals y limitaciones.

### Slides 4–6

1. Problem + data evidence.
2. Critical discovery: no complaint→transaction ground truth.
3. Architecture and AI/deterministic/human boundary.
4. Baseline vs learned + safety/e2e metrics.
5. Demo + production path / limitations.

### Video ≤ 3 min

- problema;
- one normal/ambiguous/handoff sequence;
- architectural judgment;
- measured result;
- safe human handoff.

---

## 16. Priorización crítica

Orden recomendado desde hoy:

```text
P0  FastAPI → CaseService vertical slice
P0  Dataset-backed TransactionTools
P0  Trusted demo identity
P0  Learned extractor vs frozen baseline
P0  E2E safety/evaluation
P1  Clarification + grounded summary
P1  UI integration
P1  Deployment
P1  Latency/cost/observability polish
P1  Slides/video/README
P2  External queue/policy integration beyond demo
P3  RAG/vector search/multi-agent/new workflows
```

---

## 17. Definition of Done del MVP

- [x] use case y scope congelados;
- [x] baseline y held-out artifacts congelados;
- [x] deterministic case runtime;
- [x] persistence/audit/idempotency/handoff local;
- [x] runtime expuesto por API segura (fixtures locales; no IAM productivo);
- [ ] real-dataset read-only tools;
- [ ] trusted demo IAM adapter;
- [ ] learned component evaluado contra baseline;
- [ ] clarification behavior evaluado;
- [ ] grounded handoff narrative evaluado;
- [ ] adversarial/e2e safety suite;
- [ ] latency/cost end-to-end;
- [ ] UI integrada;
- [ ] ES/PT demo y resultados separados;
- [ ] deployment working link;
- [ ] repo sanitizado/reproducible;
- [ ] slides 4–6;
- [ ] video ≤3 min.

---

## 18. Próximo paso

La siguiente tarea ya **no** es `04` ni `05`.

La siguiente tarea recomendada es:

> **Fase 2 — Dataset-backed Banking Tools: serving real read-only detrás de TransactionTools, preservando los guards de CaseService.**

La Fase 1 quedó cerrada para el alcance de fixtures. El siguiente workstream es:

> **Implementar `Dataset-backed TransactionTools` contra el dataset real read-only con contract tests compartidos.**
