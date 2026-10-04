# Fase 2 — Dataset-backed Banking Tools

## Resultado

**PASS para serving local/demo, con límites temporales explícitos.** El mismo runtime
determinístico funciona con datos reales y fixtures sin cambios a CaseService,
state machine, contratos de dominio ni artefactos congelados. No es autorización
para producción, adjudicación, fraude ni reembolso. Outcome: HANDOFF_RECORDED.

## Fuente y arquitectura

Reutilizada la caché DuckDB del EDA, no CSV por request. SHA-256 de fuente:
bd6d87c315103fa6d4e771b52dae2df69a382d7e223378a6464ecb1adecf2b8d.

FastAPI → CaseService → TransactionTools → DatasetTools → DuckDB read-only.
SQLite sigue dedicado a casos/comandos/audit/handoff. FixtureTools permanece como
default. La configuración dataset es explícita y exige deshabilitar rutas legadas.

La caché analítica tenía strings y no índices; se creó una proyección operacional
nueva, ordenada por cliente/fecha e indexada, sin mutar la caché. Tamaño:
900,214,784 bytes. No se duplicaron los otros diez dominios ni se versionó el archivo.

| Tabla | Filas | Campos operacionales |
|---|---:|---|
| transactions | 4,425,008 | ID, customer/product, timestamp, Decimal amount, currency, type, channel, status, merchant, provenance, available_at desconocido |
| products | 400,000 | product_id, customer_id |
| customers | 150,000 | customer_id |

No se incluyen complaints, textos personales, coordenadas ni scores de fraude.

## Archivos

- src/cases/dataset_tools.py: implementación del puerto existente.
- scripts/prepare_banking_serving.py: proyección validada, publicación sin overwrite.
- api/dispute_configuration.py: selección fixture/dataset; api/main.py cambia sólo composición.
- api/dispute_fixture.py: reutiliza el verifier local existente; no IAM nuevo.
- tests/test_dataset_tools.py: paridad contractual y configuración.
- scripts/validate_dataset_tools.py: benchmark y Uvicorn real, restart y SQLite.
- requirements-dataset-tools.txt, CI, README y plan: instalación y estado de entrega.
- docs/DATASET_BACKED_TOOLS.md: instrucciones completas y semántica.
- reports/dataset_tool_validation.json y dataset_tool_benchmark.json: evidencia reproducible.

## Contrato, seguridad y tiempos

search/get/history restringen cliente mediante parámetros. product_owner conserva
su firma interna existente y es llamado tras lookup autorizado por CaseService.
ID ajeno devuelve la misma ausencia que un ID inexistente. Se mantienen controles
de principal, confirmation, ownership, version, idempotency y acceso a audit/handoff.

Búsqueda: ventana inclusiva [as_of-lookback, as_of], lookback <=30 días; ID exacto
puede ser más antiguo. Comparaciones exactas según Search, sin scoring/fuzzy ni
conversión de moneda. Amount sin currency se rechaza en el guard vigente del runtime.
Orden fecha/ID descendente, máximo 50 y flag de truncamiento. Nunca selección automática.

History estrictamente anterior al candidato, últimos 30 días; mediana Decimal en
misma moneda. Se conserva precisión de medias de los dos valores centrales y se
declara complete_window_observed=false al inicio de observación.

Provenance: hash de cache, archivo relativo, transaction ID y time-policy. El runtime
conserva as_of, reglas, guards y auditoría. SQL bancario parametrizado; nombres de
columnas pertenecen a una allowlist estática. DuckDB se abre read_only con acceso
externo deshabilitado. No acceso SQL desde FastAPI ni frontend.

**Limitación temporal:** fuente sin timezone; naive-as-utc-explicit-assumption es
aceptación expresa de demo, no confirmación de UTC bancario. Horizonte wall-clock:
2023-06-17 06:01:30 → 2026-06-18 05:59:41. Sin ingestion/revision timestamps certificados,
available_at queda null. No prometer disponibilidad histórica certificada ni ownership
histórico: products/customers son snapshots. No se usan process_date/last_updated
como sustitutos. Para producción se requiere resolver estas semánticas.

## Calidad de datos

Preparación: cero violaciones transaction→product→customer, cero productos huérfanos,
cero fechas/montos/monedas incompatibles; PK exigidas en las tres tablas, sin
deduplicación ni pérdida de filas. Campos obligatorios de serving sin nulos/vacíos.
Merchant nulo se conserva; channel/type/status son requeridos por el contrato real,
por lo que una fuente incompatible falla en preparación en vez de imputarse.
Los outliers se preservan. Errores de schema/config fallan antes de requests.

## Tests y regresiones

- Baseline previo: **103 PASS**. Suite completa posterior: **115 PASS** (55.55 s).
- Nuevos tests: **12 PASS**, incluyendo paridad fixture/dataset, scope, temporalidad,
  bordes, precisión, moneda, SQL injection, truncamiento, optional merchant, startup,
  lectura read-only, PK y flujo HTTP por el mismo CaseService.
- Los 30 tests HTTP preexistentes forman parte de la suite completa.
- Uvicorn/HTTP fixture: happy/multiple/none, restart y 18 denegaciones cross-customer;
  replay dejó 3 casos, 3 handoffs, 11 comandos, 11 eventos de audit.
- Uvicorn/HTTP dataset: reloj real y replay histórico controlado, cada uno con reinicio;
  confirm/evidence/handoff y replay sin duplicados. Por modo: 3 casos, 3 handoffs,
  11 comandos y 11 eventos de audit. Caso/audit/handoff ajenos denegados.
- Dataset get: ID propio, ajeno, posterior al cutoff y currency mismatch comprobados.
- Planner: customer Index Scan verificado, no sólo supuesto pushdown.
- Ruff check/format y revisión de diff; no cambios en core, notebooks ni outputs frozen.

El verificador congelado confirma 232 outputs protegidos, 384 predicciones baseline
y 132 resultados retrieval idénticos. El harness además compara hashes de los 122
archivos presentes en artifacts/notebooks antes/después. Fuente cache: SHA antes y
después de preparación igual; serving: SHA antes/después de serving igual. Raw:
7,671 archivos con tamaños/mtime sin cambios; no se rehasharon contenidos raw completos.

**Deuda heredada, no ocultada:** verify_analytics_integration.py no pasa íntegramente
por manifiesto histórico desactualizado (tres placeholders de notebooks ausentes y
cuatro archivos previamente cambiados). Era así antes de esta fase. No se reparó ni
se modificaron outputs para lograr verde; CI analytics-integrity conserva esa deuda.
La suite runtime/API y verificación separada de outputs congelados sí pasan.

## Demostración 0/1/N y latencia

La selección para pruebas es reproducible: primeros clientes por ID ordenado con al
menos dos transacciones en últimos 30 días observados, no IDs elegidos manualmente
ni enlaces desde complaints. Un ID propio produce 1; un ID inexistente produce 0;
búsqueda sin más clues produce N en replay histórico. Un candidato requiere confirmación.

Con el reloj operacional real (octubre 2026), ese mismo lookup histórico por ID funciona,
pero búsqueda últimos 30 días devuelve 0: es comportamiento correcto. N se demuestra
mediante factory de test con reloj histórico controlado, no mediante input HTTP ni
cambio al runtime/fechas. No se presenta ese replay como evidencia contemporánea.

Benchmark **local/offline**, proceso caliente, concurrencia 1: 250 llamadas (50 por
operación), clientes ordenados lexicalmente, sin startup. p50/p95 por operación se
publican en dataset_tool_benchmark.json; no son SLO productivo ni latencia HTTP end-to-end.

## Límites y próximo paso

Sin LLM, nueva lógica de retrieval, IAM productivo, cola externa ni acciones financieras.
Credenciales locales explícitas sólo para demo; no seleccionar clientes reales desde
inputs libres. Una conexión DuckDB serializa acceso mediante lock: no se ensayó carga
concurrente productiva. La preparación requiere disco para la proyección indexada.
El startup valida formato/keys/schema, no reescanea millones de filas por arranque;
utilizar únicamente proyecciones producidas por el preparador validado.

Sin blocker funcional nuevo para el alcance local explícito. Se mantienen como límites
timezone, snapshots y disponibilidad histórica; la deuda del manifiesto analítico
impide afirmar que todo el pipeline CI histórico esté verde.

Próxima tarea: **Fase 3 — Trusted Demo Identity / IAM Adapter**, no implementada aquí.
