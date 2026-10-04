# Fase 1 — Secure Application Adapter

## Arquitectura IMPLEMENTED / TESTED

    Cliente HTTP → FastAPI / api/routes/disputes.py → CaseService
                                                     ├── FixtureTools
                                                     └── CaseStore / SQLite

La factory api/main.py:create_app(case_service, include_legacy=False) recibe el servicio.
Las rutas no acceden al store/SQL ni deciden transiciones, ownership, política o handoff.
api/dispute_fixture.py construye dependencias al arrancar; no atiende queries HTTP.
CaseService, contratos de dominio, tools y máquina de estados no se modificaron.

Las rutas chat/context/trace son **legacy scaffold**. ENABLE_LEGACY_API=false evita montarlas
e instanciar su orchestrator. La UI antigua no está conectada al nuevo flujo. No conectar
datos reales a rutas legadas. X-API-Key no identifica al cliente ni da acceso a disputas.

## Arranque local explícito

Python 3.12+; dependencias existentes en requirements.txt. Desde la raíz:

~~~bash
export USE_LLM=false
export USE_MOCKS=true
export ENABLE_LEGACY_API=false
export DISPUTE_FIXTURE_MODE=true
export DISPUTE_DEMO_TOKEN_A="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export DISPUTE_DEMO_TOKEN_B="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export DISPUTE_FIXTURE_ANCHOR="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
export DISPUTE_DB_PATH=.tmp/disputes/http.sqlite3
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --no-access-log
~~~

No imprimir/versionar secretos. Mantener **la misma anchor y base al reiniciar**.
Otro anchor cambia la evidencia sintética: usar otra base, sin borrar la anterior.
Sin DISPUTE_FIXTURE_MODE=true las rutas fallan cerrado (503 con Bearer); no hay
credenciales por defecto. Configuración habilitada pero incompleta falla al arrancar.
Health es liveness, no prueba IAM/serving operacional. CORS por defecto sólo permite
http://localhost:8501; configurar CORS_ALLOW_ORIGINS explícitamente. CORS no autentica.
Esta configuración es exclusivamente local, sin despliegue público/TLS en esta fase.

## Identidad y fixtures

Authorization: Bearer transporta una credencial opaca. La dependency la entrega a
CaseService; el resolver inyectado construye Principal. No se acepta Principal,
customer_id, scopes ni as_of_time desde el body. Texto/pistas no modifican identidad.
El demo compara dos secretos distintos (mínimo 32 caracteres) configurados por servidor.
Sus principales tienen scope read/write y clientes sintéticos distintos. CaseService
revalida expiración y scope en cada llamada, incluidos replay y GET.

Sesión local válida una hora desde arranque; reiniciar reconstituye sesiones. No hay
login, issuer firmado, revocación ni IAM productivo. El resolver se reemplazará en una
fase futura. AUTH_DENIED (401) agrupa invalidez/expiración/scope según el dominio actual.

Se reutilizan A_explicit_id y C_multiple del primer grupo **development** de
artifacts/evaluation/retrieval_fixtures.jsonl. El archivo congelado no se cambia.
Los timestamps se desplazan por diferencia entre anchor configurada y as_of de fixture.
Producto/ownership de producto y Purchase/App/Approved son **adiciones sintéticas de demo**,
no hechos bancarios inferidos. source_ref identifica fixture/grupo/ID/anchor.
No se usan fixtures held-out. El reloj de CaseService sigue siendo UTC real para
as_of y expiración; no se congela el reloj de autorización. Disponibilidad histórica unknown.

## Superficie HTTP y contratos

| Método | Ruta | Operación real |
|---|---|---|
| POST | /v1/disputes | create(Intake) |
| POST | /v1/disputes/{case_id}/search | search(Search) |
| POST | /v1/disputes/{case_id}/confirm | confirm(Selection) |
| POST | /v1/disputes/{case_id}/evidence | collect |
| POST | /v1/disputes/{case_id}/handoff | handoff |
| GET | /v1/disputes/{case_id} | get |
| GET | /v1/disputes/{case_id}/audit | audit autorizado |
| GET | /v1/disputes/{case_id}/handoff | get_handoff autorizado |

Todo POST exige Idempotency-Key (1–128 caracteres). Salvo create, exige expected_version
entero >=1; no booleano/string. Misma key+payload+versión devuelve resultado original,
aunque GET ya muestre otra versión. Otra carga con esa clave → 409. Create responde
201 también en replay: contrato estable sin consultas adicionales ni segunda idempotencia.
Una nueva clave tampoco duplica el handoff de un caso terminal.

CaseResponse proyecta explícitamente los campos públicos, no todo el store.
Clues regex son sugerencias no confiables; Search/Selection requieren confirmación
del usuario. Cantidades: string decimal, no float; moneda explícita. Handoff ausente:
null; caso inexistente/ajeno: mismo 404. EvidenceBundle mantiene referencias y limitaciones.

### Ejemplo

~~~bash
curl -sS http://127.0.0.1:8000/v1/disputes \
  -H "Authorization: Bearer $DISPUTE_DEMO_TOKEN_A" \
  -H 'Idempotency-Key: demo-create' -H 'Content-Type: application/json' \
  -d '{"user_utterance":"No reconozco un cargo","language":"es"}'
~~~

Tomar case_id y version de cada respuesta. Cada request siguiente conserva Bearer y
Content-Type, con una clave nueva por comando:

~~~text
POST /v1/disputes/{case_id}/search    Idempotency-Key: demo-search
{"expected_version":1,"query":{"confirmed":true,"transaction_id":"TX-F9A2973A6963"}}

POST /v1/disputes/{case_id}/confirm   Idempotency-Key: demo-confirm
{"expected_version":2,"selection":{"confirmed":true,"transaction_id":"TX-F9A2973A6963"}}

POST /v1/disputes/{case_id}/evidence  Idempotency-Key: demo-evidence
{"expected_version":3}

POST /v1/disputes/{case_id}/handoff   Idempotency-Key: demo-handoff
{"expected_version":4}
~~~

ID del ejemplo: primera fixture development. El smoke lo obtiene desde el archivo.
Un candidato queda AWAITING_CONFIRMATION, selection=null. Para múltiples buscar sólo
confirmed=true; para ninguno usar transaction_id="missing". Ninguna rama adjudica.

## Errores y auditoría

| Dominio/frontera | HTTP | Decisión |
|---|---:|---|
| AUTH_DENIED | 401 | Bearer challenge; sin detalles de identidad |
| CASE_NOT_ACCESSIBLE | 404 | Inexistente y ajeno indistinguibles |
| STALE_VERSION / IDEMPOTENCY_KEY_REUSED | 409 | Guard del runtime |
| INVALID_TRANSITION / TERMINAL_CASE | 409 | No modificar la máquina |
| Confirmación/pistas/selección inválidas | 422 | Código allowlisted, sin datos ajenos |
| Body/header inválido | 422 | INVALID_REQUEST; sin echo de input |
| CLOCK_BEFORE_CASE / SQLite / dependencia | 503 | No anunciar persistencia exitosa |
| Fallo inesperado / output inválido | 500 | INTERNAL_ERROR; sin secretos/stacktrace |

Tool failure capturado por dominio devuelve **200 con INSUFFICIENT_EVIDENCE e issue**:
se persistió correctamente ese estado seguro; no es éxito de investigación ni búsqueda vacía.

Respuestas: Cache-Control: no-store y X-Request-ID generado por servidor. Es correlación
HTTP **transitoria**, no fingerprint idempotente ni audit durable. El núcleo v1 no acepta
request_id: no se migró su esquema ni se inventa soporte. Audit autorizado muestra
actor/provider, comando, origen/destino, versión y recorded_at; omite secuencia interna,
hashes y rechazos globales. Guards/evidence refs se consultan en caso/handoff; no se
fabrican columnas de audit. Rechazos del runtime siguen auditados allí; errores previos
de validación HTTP no crean una segunda auditoría durable. Telemetría completa pendiente.

HANDOFF_RECORDED = LOCAL_PENDING_HUMAN_REVIEW; no cola externa, resolución,
reembolso, cierre ni fraude confirmado.

## Validación y límites

~~~bash
USE_LLM=false .venv/bin/python -m pytest tests/test_dispute_api.py tests/test_case_runtime.py -q
USE_LLM=false .venv/bin/python scripts/smoke_dispute_http.py
.venv/bin/python scripts/verify_dispute_adapter_regressions.py
~~~

El smoke inicia Uvicorn en loopback con secretos efímeros; valida tres flujos, acceso
cruzado, replay y reinicio. Verifica SQLite en el script de prueba (no en API) y elimina
sólo su base temporal. Esperado: 3 cases, 3 handoffs, 11 commands/audit tras reinicio.
Tests HTTP/core bloquean red; el smoke es la prueba separada de HTTP real.
Toda la suite requiere además requirements-analytics.txt; usa fixtures pequeñas,
no vuelve a ejecutar profiling/EDA del dataset.

Sin LLM/RAG, datos reales, UI nueva, cola humana o política externa. No es certificación
de riesgo cero ni robustez de un LLM. El manifiesto histórico de importación tiene
discrepancias previas de nombres/notebooks/scripts: no se repara silenciosamente.
El verificador de esta fase comprueba hashes/paridad del scope congelado y reporta
las discrepancias heredadas, sin afirmar PASS histórico completo.

Siguiente: **Fase 2 — Dataset-backed Banking Tools**, no implementada aquí.
