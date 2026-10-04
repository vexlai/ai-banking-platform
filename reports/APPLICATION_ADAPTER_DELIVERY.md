# Fase 1 — Secure Application Adapter

## Arquitectura y resultado

FastAPI → adaptador tipado → **CaseService** → FixtureTools / SQLite.
El workflow completo está expuesto por HTTP sin LLM ni orchestrator legado.
Resultado terminal conservado: **HANDOFF_RECORDED**, paquete local pendiente de revisión.
No adjudicación, reembolso, fraude confirmado, cierre ni cola externa.

No se modificó src/cases/, contracts/disputes.py, el parser congelado ni sus fixtures.
Toda decisión de estados, selección, ownership, idempotencia, versión y handoff sigue en el núcleo.

## Archivos de esta entrega

- api/main.py: factory inyectable, wiring, opción de no montar legado y CORS acotado.
- api/routes/disputes.py: transporte, credencial opaca, delegación y errores seguros.
- api/dispute_fixture.py: composición local explícita desde fixtures development existentes.
- contracts/dispute_http.py: DTOs de comandos/versionado, proyección de caso y audit.
- tests/test_dispute_api.py: aceptación HTTP con rig existente y bloqueo de red.
- scripts/smoke_dispute_http.py: Uvicorn real, reinicio y verificación SQLite.
- scripts/verify_dispute_adapter_regressions.py: hashes y paridad congelada read-only.
- README, docs/SECURE_APPLICATION_ADAPTER.md, docs/DETERMINISTIC_CASE_RUNTIME.md,
  docs/IMPLEMENTATION_PLAN.md y CI: estado real, ejecución y pruebas.

AGENTS.md y el nuevo plan tenían cambios del usuario antes de esta tarea; no se deshicieron.

## Superficie y seguridad

POST /v1/disputes; POST /{case_id}/search, /confirm, /evidence y /handoff;
GET /{case_id}, /{case_id}/audit y /{case_id}/handoff bajo el mismo prefijo.
Los ocho endpoints delegan exclusivamente en métodos públicos de CaseService.

Bearer obligatorio, resuelto por el verificador inyectado; principal/scope/as_of no vienen
del body. API key compartida del scaffold no autentica clientes. Credenciales locales
efímeras/configuradas por servidor son **MOCKED**, no IAM externo. CaseService comprueba
expiración y scopes también en GET y replays. As_of usa reloj UTC real del servidor.

Expected_version e Idempotency-Key se transportan sin otra capa de idempotencia.
Mismo payload/clave/versión conserva respuesta histórica; GET sirve estado actual.
Create responde 201 en replay; no se añade efecto. Selección explícita sigue obligatoria
incluso con un candidato. Ownership se relee desde tools al confirmar y colectar.

Los fixtures A/C development se reutilizan sin modificar archivo fuente. El offset
temporal lo fija una anchor del servidor que debe conservarse entre reinicios.
Producto/ownership, tipo/canal/status adicionales están etiquetados como sintéticos,
no como nuevas observaciones bancarias. La evidencia conserva source_ref con anchor.

## Domain → HTTP

| Situación | HTTP |
|---|---:|
| AUTH_DENIED: ausente/inválido/expirado/scope | 401 |
| CASE_NOT_ACCESSIBLE: ajeno o inexistente indistinguibles | 404 |
| STALE_VERSION / IDEMPOTENCY_KEY_REUSED / INVALID_TRANSITION / TERMINAL_CASE | 409 |
| Input, pistas o selección inválidos | 422 |
| CLOCK_BEFORE_CASE / fallo SQLite / dependencia no disponible | 503 |
| Excepción inesperada / contrato interno inválido | 500 |

Sólo códigos allowlisted; sin echo de inputs, secretos, IDs ajenos ni stacktraces.
Los fallos de tools capturados por el núcleo conservan HTTP 200 con estado explícito
INSUFFICIENT_EVIDENCE y issue: éxito de persistir el fallo, **no éxito de investigación**.

Audit autorizado proyecta actor/provider, acción, estados, versión y recorded_at.
No se exponen hashes internos ni tabla global de rechazos. Evidence/guard results están
en el bundle/paquete; no se inventan columnas del audit. No chain-of-thought.
X-Request-ID es correlación HTTP transitoria; v1 no lo admite en audit durable.
Se devuelve Cache-Control: no-store. No se agregó auditoría HTTP duplicada.

## Validaciones locales

| Comprobación | Resultado |
|---|---|
| Suite completa previa, sin cambios | 73 passed |
| Tests nuevos API | 30 passed |
| Suite completa después de integración | 103 passed |
| Ruff lint / format de archivos afectados | PASS |
| HTTP real en loopback con Uvicorn | explicit / multiple / none → HANDOFF_RECORDED |
| Reinicio de Uvicorn + replay de toda la secuencia | mismos casos/handoffs |
| SQLite después de replay | 3 cases, 3 handoffs, 11 commands, 11 audit |
| Audit por caso | 5 / 3 / 3, sin duplicados |
| Accesos cruzados GET caso/audit/handoff, dos ejecuciones | 18/18 rechazados |
| SQLite integrity_check / foreign_key_check | ok / sin violaciones |
| Artefactos analíticos/contratos congelados del manifiesto | 232 hashes idénticos |
| Predicciones baseline | 384 idénticas |
| Fixtures retrieval | métricas idénticas en 132 fixtures |
| Raw | tamaños de 7.671 archivos sin cambio; sin rehash de contenido |

Tests incluyen llamadas no autorizadas de comandos, invalid/expired/scope, futuro,
moneda incorrecta, confirmación falsa, candidato ajeno, ownership cambiado, concurrencia,
versión obsoleta, replay tras reinicio, doble handoff, fallos de tools y persistencia,
malformed input y ausencia de configuración. Red bloqueada en tests in-process.
El smoke separado sí usa HTTP local; sus credenciales no se imprimen y su DB temporal
se elimina tras verificarla. No llamadas LLM, acceso raw desde API ni decisiones financieras.

### Entorno y discrepancia heredada

La primera ejecución con sólo el entorno runtime no pudo recolectar tres módulos analíticos:
faltaba DuckDB. Se repitió antes de cambiar código con dependencias analíticas ya instaladas:
73 passed. La ejecución completa final utilizó la misma combinación de dependencias.
En un entorno nuevo instalar requirements.txt y requirements-analytics.txt.

El verificador histórico scripts/verify_analytics_integration.py ya fallaba antes de editar:
faltan sus referencias antiguas a 03_customer_journey_discovery.ipynb,
04_use_case_definition.ipynb y 05_baseline.ipynb. También difieren de su manifiesto histórico
scripts/build_eda.py, scripts/build_mvp_and_eval.py, AGENTS.md y docs/ANALYTICS_ORIGINAL_README.md.
No se corrigió ni sobrescribió ese manifiesto. El verificador de esta entrega reporta las
discrepancias y comprueba separadamente el scope congelado. **No se afirma que el verificador
histórico completo o CI remoto estén verdes.** CI del adaptador fue añadida, no ejecutada remotamente.

## Límites y siguiente tarea

IMPLEMENTED: HTTP, DTOs, delegación, errores seguros y correlación transitoria.
TESTED: fixture workflow, safety de núcleo/HTTP, persistencia y replay local.
MOCKED/SYNTHETIC: credenciales/serving, aliases y contexto de demo.
NOT IMPLEMENTED: datos reales, IAM productivo, cola/política externa, LLM, UI, deployment.
NOT MEASURED: beneficio productivo, adversarial robustness de LLM y rendimiento bajo carga.

No blocker funcional para el adaptador de fixtures. La discrepancia del manifiesto histórico
es deuda preexistente documentada, no una regresión del baseline ni autorización para cambiarlo.
SQLite local/locks y secretos de demo no constituyen arquitectura productiva. Legacy queda
disponible por compatibilidad si no se desactiva: usar ENABLE_LEGACY_API=false para el MVP.

Siguiente tarea: **Fase 2 — Dataset-backed Banking Tools**. No implementada en esta entrega.
Reproducción completa: [SECURE_APPLICATION_ADAPTER.md](../docs/SECURE_APPLICATION_ADAPTER.md).
