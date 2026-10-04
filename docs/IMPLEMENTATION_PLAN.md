# IMPLEMENTATION_PLAN.md

## 1. Propósito

Este plan parte del estado actual del repositorio y del **Frozen MVP Contract v1**.

No reabre discovery, EDA, definición del caso de uso ni baseline ya cerrados.

### MVP

> **Transaction Dispute Intake & Investigation Copilot**

Resultado final observable:

> **HANDOFF_RECORDED**

El sistema ayuda a recibir, investigar, estructurar y preparar una disputa transaccional para revisión humana.

### Fuera de alcance

El MVP **no realiza**:

- adjudicación autónoma de disputas;
- determinación definitiva de fraude;
- compensaciones;
- movimientos de dinero;
- reversos;
- cierre autónomo de casos;
- decisiones financieras irreversibles.

La autoridad final permanece fuera del componente generativo.

---

# 2. Principios de arquitectura

El MVP mantiene una separación explícita entre:

```text
Code / Guards
     ↓
Deterministic authority

Database / Tools
     ↓
Verified facts

AI
     ↓
Extraction + clarification + narrative

Human
     ↓
Final authority
```

## Reglas invariantes

Los componentes de IA no pueden modificar ni decidir:

- identidad del cliente;
- autorización;
- ownership;
- `as_of_time`;
- cross-customer access;
- idempotencia;
- confirmación de transacción;
- state transitions críticas;
- ejecución del handoff;
- operaciones financieras.

El usuario debe confirmar explícitamente una transacción candidata cuando corresponda.

No se permite SQL arbitrario generado por modelos.

---

# 3. Estado actual

## DONE / FROZEN

- Dataset inventory.
- Ingestion/profiling.
- EDA general.
- Transaction-dispute EDA.
- Workflow discovery.
- `04_mvp_use_case_definition.ipynb`.
- Frozen MVP Contract v1.
- `05_baseline_and_eval_dataset.ipynb`.
- 384 utterances ES/PT.
- Baseline regex congelado.
- Controlled retrieval fixtures.
- Safety fixtures offline.
- Deterministic case runtime.
- SQLite persistence/versioning.
- Idempotency.
- Explicit candidate confirmation.
- Ownership guards.
- `as_of` guards.
- Durable/idempotent local handoff.
- Runtime audit.
- FastAPI → `CaseService`.
- Secure application adapter.
- Dataset-backed `TransactionTools`.

## CURRENT POSITION

```text
Phase 1 — Foundation & Secure Runtime      ✅ DONE
Phase 2 — Identity & AI Intake             ← NEXT
Phase 3 — Investigation Intelligence
Phase 4 — Safety, Evaluation & Observability
Phase 5 — Demo Productization
Phase 6 — Submission
```

---

# 4. Phase 1 — Foundation & Secure Runtime ✅

## Objetivo

Construir un runtime determinístico, seguro y reproducible que exponga el workflow mediante API y consulte datos transaccionales reales de manera read-only.

Esta fase consolida las antiguas:

- Freeze preservation.
- Secure Application Adapter.
- Dataset-backed Banking Tools.

---

## 4.1 Frozen artifacts

Mantener como read-only lógico:

- `04_mvp_use_case_definition.ipynb`;
- `05_baseline_and_eval_dataset.ipynb`;
- `mvp-contract-v1`;
- evaluation fixtures;
- baseline artifacts.

Registrar:

- hashes;
- versiones;
- configuración;
- datasets utilizados.

No modificar discovery/baseline para hacer funcionar features posteriores.

---

## 4.2 Secure Application Adapter

Arquitectura:

```text
FastAPI
   ↓
CaseService
   ↓
Domain/runtime
```

Endpoints principales:

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

Requisitos:

- no bypass de `CaseService`;
- HTTP error mapping seguro;
- principal/session context;
- idempotency key;
- expected version;
- request/correlation ID;
- audit y handoff protegidos por scope.

---

## 4.3 Dataset-backed TransactionTools

Arquitectura:

```text
CaseService
      ↓
TransactionTools
      │
      ├── FixtureTransactionTools
      │
      └── DuckDBTransactionTools
                    ↓
             Parquet / Dataset
```

Capacidades:

- transaction search;
- exact transaction lookup;
- ownership lookup;
- product lookup;
- strictly-prior history;
- `as_of_time`;
- bounded queries;
- parameterized queries;
- truncation reporting;
- missingness reporting.

### Definition of Done

- API funciona end-to-end;
- runtime usa `CaseService`;
- persistence/idempotency funcionando;
- Dataset TransactionTools read-only;
- mismo contrato fixture/dataset;
- cero cross-customer leakage;
- no SQL generado por IA;
- journeys reproducibles;
- tests contractuales compartidos.

### Estado

> ✅ COMPLETADA

---

# 5. Phase 2 — Identity & AI Intake

## Objetivo

Construir una entrada confiable al workflow combinando:

1. identidad autoritativa;
2. extracción estructurada basada en AI/ML;
3. validación determinística.

Arquitectura:

```text
                Request
                   │
          ┌────────┴────────┐
          ↓                 ↓
 Trusted Identity      User Utterance
          │                 │
          │                 ▼
          │          Learned Extractor
          │                 │
          │                 ▼
          │         Structured Intake
          │                 │
          └────────┬────────┘
                   ▼
        Deterministic Validation
                   │
                   ▼
              CaseService
```

---

## 5.1 Trusted Demo Identity

La identidad nunca se obtiene del contenido escrito por el usuario.

Implementar un adapter de identidad confiable mediante:

- token firmado;
- principal;
- issuer;
- audience;
- expiration;
- scopes;
- customer mapping;
- demo IAM adapter.

El modelo jamás debe poder cambiar:

```text
customer_id
principal
scope
ownership
```

### Tests mínimos

- valid token;
- expired token;
- invalid signature;
- invalid audience;
- insufficient scope;
- cross-customer access.

---

## 5.2 Learned Structured Intake Extraction

Objetivo:

Transformar lenguaje natural en una representación estructurada del reclamo.

Ejemplo:

```text
"Me aparece un cargo de aproximadamente
80 dólares en Amazon de la semana pasada."
```

↓

```json
{
  "merchant": "Amazon",
  "amount": 80,
  "currency": "USD",
  "transaction_date": null,
  "should_clarify": true
}
```

El output debe utilizar schema validado.

Requisitos:

- modelo/provider definido;
- prompt versionado;
- schema versionado;
- structured output;
- validación Pydantic/equivalente;
- no incluir identidad autoritativa;
- no incluir labels del evaluation set;
- configuración congelada antes del test final.

---

## 5.3 Baseline vs Learned

Comparar contra el baseline congelado utilizando exactamente el mismo held-out workload.

### Métricas

- full-schema exact match;
- per-field precision;
- per-field recall;
- per-field F1;
- per-field exact match;
- schema validity;
- hallucinated-field rate;
- missing-required-clue exact match;
- `should_clarify` accuracy;
- p50 latency;
- p95 latency;
- cost/case.

Reportar por separado:

```text
ES
PT
Overall
```

El dataset PT debe identificarse explícitamente como team-generated cuando corresponda.

---

## 5.4 Experimentos opcionales

Solamente después de establecer el baseline del learned extractor pueden evaluarse modelos especializados de decisión.

Ejemplo:

```text
Structured Intake
       ↓
Decision Model
       ↓
SEARCH / CLARIFY / HANDOFF
```

Cualquier modelo adicional debe demostrar una mejora medible antes de incorporarse al runtime principal.

No debe convertirse en autoridad del workflow.

---

## Definition of Done

- trusted identity funcionando;
- identity/ownership separados del lenguaje del usuario;
- learned extractor integrado;
- output estructurado validado;
- baseline vs learned ejecutado;
- métricas ES/PT disponibles;
- latency/cost registrado;
- error analysis disponible;
- safety guards originales preservados.

---

# 6. Phase 3 — Investigation Intelligence

## Objetivo

Añadir inteligencia conversacional al proceso de investigación sin entregar autoridad al modelo.

Agrupa:

- controlled clarification;
- candidate handling;
- EvidenceBundle;
- grounded summary;
- handoff narrative.

Arquitectura:

```text
Structured Intake
       ↓
Transaction Search
       ↓
Candidate Transactions
       ↓
Need clarification?
       │
   ┌───┴────┐
   ↓        ↓
  YES       NO
   │        │
Clarify     │
   │        │
   └───┬────┘
       ↓
User Confirmation
       ↓
EvidenceBundle
       ↓
Grounded Summary
       ↓
HANDOFF_RECORDED
```

---

## 6.1 Controlled Clarification

Preguntar únicamente información necesaria y permitida.

Reglas:

- no inventar moneda;
- no inventar fecha crítica;
- no inferir atributos importantes sin confirmación;
- no seleccionar transacción automáticamente;
- número máximo de turnos;
- abstain/handoff cuando la incertidumbre no pueda resolverse.

Casos mínimos:

- missing amount;
- missing date;
- missing currency;
- missing merchant;
- multiple candidates;
- contradictory clues;
- no candidate;
- ES ambiguity;
- PT ambiguity.

---

## 6.2 Candidate Confirmation

Una recomendación o ranking puede ayudar al usuario, pero:

> **ranking ≠ authority**

Flujo:

```text
Candidates
    ↓
Optional relevance ranking
    ↓
Presentation
    ↓
USER CONFIRMATION
    ↓
Selected transaction
```

Está prohibida la auto-confirmación de una transacción.

---

## 6.3 EvidenceBundle

Toda afirmación factual utilizada para handoff debe provenir de evidencia allowlisted.

Ejemplo conceptual:

```json
{
  "selected_transaction": {},
  "verified_customer_facts": {},
  "transaction_history": [],
  "user_claims": [],
  "unknowns": [],
  "evidence_refs": []
}
```

---

## 6.4 Grounded Summary

El modelo puede generar narrativa solamente sobre el `EvidenceBundle`.

Debe mantener:

- evidence refs;
- unknowns;
- unresolved questions;
- distinction entre user claim y verified fact.

El resumen generado nunca sustituye al paquete determinístico.

Si el modelo falla:

```text
EvidenceBundle
       ↓
Deterministic handoff
       ↓
HANDOFF_RECORDED
```

debe continuar funcionando.

---

## Definition of Done

- clarification evaluada;
- ambiguity handling correcto;
- explicit candidate confirmation preservada;
- EvidenceBundle construido;
- factual claims grounded;
- unknowns preservados;
- grounded handoff funcionando;
- handoff funciona incluso sin LLM.

---

# 7. Phase 4 — Safety, Evaluation & Observability

## Objetivo

Evaluar el sistema como una unidad y producir evidencia cuantitativa reproducible.

Esta fase consolida:

- adversarial testing;
- evaluation harness;
- observability.

---

## 7.1 Safety / Adversarial Suite

Casos mínimos:

- cross-customer access;
- expired authentication;
- invalid authentication;
- prompt injection;
- system prompt extraction;
- secret extraction;
- malformed model output;
- model timeout;
- tool timeout;
- tool error;
- no candidate;
- multiple candidates;
- contradictory user claims;
- future transaction leakage;
- unauthorized financial action;
- out-of-scope workflow;
- Portuguese ambiguity.

---

## 7.2 Evaluation Harness

Una ejecución reproducible debe generar:

```text
reports/evaluation/
├── component_metrics.*
├── system_metrics.*
├── safety_metrics.*
├── operational_metrics.*
├── language_breakdown.*
└── error_analysis.*
```

### Métricas

#### Component

- baseline vs learned;
- extraction accuracy;
- clarification accuracy;
- grounding accuracy.

#### System

- successful path distribution;
- clarification rate;
- handoff rate;
- unnecessary handoff rate;
- missed handoff rate.

#### Safety

- unsafe outcomes;
- auth violations;
- ownership violations;
- future-data leakage;
- unauthorized action attempts.

#### Operational

- p50 latency;
- p95 latency;
- cost/case;
- token usage;
- tool failure rate;
- model failure rate.

---

## 7.3 Observability

Registrar:

- correlation ID;
- request ID;
- principal reference no sensible;
- case ID;
- state transitions;
- tool invocation;
- tool status;
- retries;
- model version;
- prompt version;
- latency;
- token estimates;
- cost estimates;
- handoff reason;
- audit refs.

Un journey completo debe poder reconstruirse sin:

- chain-of-thought;
- secrets;
- PII innecesaria.

---

## Definition of Done

- adversarial suite automatizada;
- critical cases con expected behavior;
- evaluation reproducible;
- resultados persistidos;
- ES/PT breakdown;
- latency/cost medidos;
- observability suficiente para reconstruir journeys;
- runtime-only safety diferenciada de AI-integrated safety.

---

# 8. Phase 5 — Demo Productization

## Objetivo

Convertir el MVP técnico en una demo clara, reproducible y compartible.

Agrupa:

- customer UI;
- investigator UI;
- deployment;
- smoke testing.

---

## 8.1 Customer View

Mostrar:

- authenticated session;
- chat/input;
- clarification;
- transaction candidates;
- confirmation;
- case status;
- safe errors.

---

## 8.2 Human Investigator View

Mostrar:

- user request;
- selected transaction;
- candidates;
- verified facts;
- user claims;
- evidence refs;
- actions;
- guards;
- unresolved questions;
- escalation reason;
- handoff receipt.

---

## 8.3 Deployment

Requisitos:

- reproducible Docker/build;
- secrets por environment/secret manager;
- CORS restringido;
- health endpoint;
- readiness endpoint;
- persistent demo state cuando aplique;
- backend URL;
- frontend URL;
- E2E smoke test.

---

## Journeys mínimos

### Journey A — Normal

```text
Complaint
   ↓
Extraction
   ↓
Transaction found
   ↓
Confirmation
   ↓
Evidence
   ↓
Handoff
```

### Journey B — Ambiguous

```text
Complaint
   ↓
Extraction
   ↓
Multiple candidates
   ↓
Clarification
   ↓
Confirmation
   ↓
Handoff
```

### Journey C — Safe fallback

```text
Complaint
   ↓
Insufficient / unsafe condition
   ↓
Abstain
   ↓
Human handoff
```

---

## Definition of Done

- customer UI integrada;
- human UI integrada;
- backend deployed;
- frontend deployed;
- three journeys reproducibles;
- safe fallback;
- smoke E2E verde;
- README reproduce ejecución local.

---

# 9. Phase 6 — Submission

## Objetivo

Convertir la implementación en una historia clara y demostrable para el hackathon.

---

## 9.1 GitHub

Repositorio público sanitizado.

No incluir:

- datasets restringidos;
- PII;
- credentials;
- secrets;
- private endpoints.

README debe explicar:

1. Problem.
2. Data evidence.
3. Architecture.
4. Safety boundary.
5. AI components.
6. Evaluation.
7. Demo.
8. Limitations.
9. Local setup.

---

## 9.2 Evidence Pack

Incluir:

- baseline results;
- learned results;
- system metrics;
- safety metrics;
- ES/PT breakdown;
- latency;
- cost;
- error analysis;
- architecture diagram.

---

## 9.3 Slides

Objetivo:

**4–6 slides.**

### Slide 1 — Problem

Transaction dispute investigation requiere conectar lenguaje ambiguo del cliente con evidencia transaccional confiable.

### Slide 2 — Data Discovery

Hallazgo crítico:

> No existe complaint → transaction ground truth directamente disponible.

Explicar cómo esto condicionó el diseño del MVP.

### Slide 3 — Architecture

Mostrar:

```text
Deterministic Runtime
        +
Trusted Data
        +
AI Assistance
        +
Human Authority
```

### Slide 4 — Evaluation

Mostrar:

```text
Baseline
   vs
Learned AI
```

más safety/system metrics.

### Slide 5 — Demo / Impact

Mostrar journey y `HANDOFF_RECORDED`.

### Slide 6 — Production Path

Limitaciones y siguiente evolución.

---

## 9.4 Video

Duración máxima:

> ≤ 3 minutos

Secuencia recomendada:

```text
Problem
   ↓
Architecture
   ↓
Live journey
   ↓
Metrics
   ↓
Human handoff
```

---

# 10. Priorización desde el estado actual

```text
DONE
────────────────────────────────────────
P0  Foundation & Secure Runtime          ✅


NOW
────────────────────────────────────────
P0  Trusted Demo Identity
P0  Learned Structured Extraction
P0  Baseline vs Learned


NEXT
────────────────────────────────────────
P0  Controlled Clarification
P0  EvidenceBundle
P0  Grounded Handoff
P0  Safety / E2E Evaluation


DELIVERY
────────────────────────────────────────
P1  Observability polish
P1  Demo UI
P1  Deployment
P1  Slides / README / Video


OPTIONAL
────────────────────────────────────────
P2  Specialized decision models
P2  Candidate ranking experiments
P3  RAG
P3  Vector search
P3  Multi-agent architecture
P3  New workflows
```

---

# 11. Definition of Done del MVP

El MVP está terminado cuando existe:

### Foundation

- [x] frozen MVP contract;
- [x] frozen baseline;
- [x] deterministic runtime;
- [x] persistence;
- [x] idempotency;
- [x] audit;
- [x] FastAPI adapter;
- [x] Dataset-backed TransactionTools.

### Identity & Intake

- [ ] trusted demo IAM;
- [ ] learned extractor;
- [ ] structured schema validation;
- [ ] baseline vs learned evaluation;
- [ ] ES/PT metrics.

### Investigation

- [ ] controlled clarification;
- [ ] explicit candidate confirmation;
- [ ] EvidenceBundle;
- [ ] grounded summary;
- [ ] deterministic handoff fallback.

### Evaluation

- [ ] adversarial suite;
- [ ] E2E evaluation;
- [ ] safety metrics;
- [ ] operational metrics;
- [ ] latency/cost;
- [ ] observability.

### Product

- [ ] integrated UI;
- [ ] deployment;
- [ ] three stable demo journeys.

### Submission

- [ ] sanitized repository;
- [ ] README;
- [ ] evidence pack;
- [ ] 4–6 slides;
- [ ] video ≤ 3 minutes.

---

# 12. Próximo paso

El siguiente workstream es:

> **Phase 2 — Identity & AI Intake**

Orden recomendado:

```text
1. Trusted Demo Identity
        ↓
2. Learned Structured Extractor
        ↓
3. Baseline vs Learned Evaluation
        ↓
4. Error Analysis
        ↓
5. Freeze winning configuration
```

Una vez cerrada esta fase:

```text
Identity & AI Intake
        ↓
Investigation Intelligence
```

No añadir nuevos componentes de arquitectura hasta obtener primero una comparación reproducible del componente aprendido contra el baseline congelado.