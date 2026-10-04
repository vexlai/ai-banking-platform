# Entrega 1: flujo determinístico persistente

Resultados de aceptación: [CASE_RUNTIME_DELIVERY.md](../reports/CASE_RUNTIME_DELIVERY.md).

## Alcance

Implementado como núcleo de aplicación Python, separado del chat legado:
intake → pistas sugeridas por regex → búsqueda confirmada → confirmación explícita
→ ownership → evidencia → política bloqueante → handoff local durable.

No hay llamadas LLM, adjudicación, reembolso, cierre automático ni cambios de raw.
La entrega original no agregó endpoints. La Fase 1 posterior integra /v1/disputes
directamente con este núcleo: [Secure Application Adapter](SECURE_APPLICATION_ADAPTER.md).
El chat/UI legado sigue separado y conserva sus limitaciones conocidas.
No exponer el chat legado a datos bancarios reales.

El puerto de autenticación es obligatorio e inyectado. El host debe verificar
firma/emisor, sesión y revocación antes de devolver Principal. El servicio comprueba
además expiración, scopes y aislamiento por customer en cada petición, incluidos
reintentos y lecturas. La demo y los tests usan IAM sintético explícito, no autenticación
productiva. Un Principal construido a partir del body/LLM NO sería una integración válida.

## Archivos

- contracts/disputes.py: contratos v1, extra fields prohibidos y fechas con timezone.
- src/cases/service.py: comandos y guards sin dependencia del modelo.
- src/cases/state_machine.py: mapa explícito de comandos permitidos por estado.
- src/cases/store.py: unidad transaccional SQLite.
- src/cases/tools.py: puerto de lectura y backend de fixtures controlados.
- tests/test_case_runtime.py: aceptación, persistencia y seguridad.
- scripts/demo_dispute_cases.py: tres escenarios sintéticos, repetibles y persistentes.

No se cambian los contratos antiguos ni el parser firmado. Las pistas del parser
son sugerencias no confiables; no se ejecutan como consultas automáticamente.
El adaptador futuro debe convertir la confirmación del usuario en Search/Selection:
un booleano generado por el LLM no constituye esa confirmación.
Los IDs bancarios explícitos se pasan al contrato Search sin depender de la gramática
de IDs pseudonimizados del baseline.

## Estados y transiciones

| Comando | Origen | Resultado y guard |
|---|---|---|
| create | ninguno | INTAKE_INCOMPLETE, principal válido y as_of del servidor |
| search | intake/no candidato/múltiples/espera/insuficiente | NO_CANDIDATE, MULTIPLE_CANDIDATES o AWAITING_CONFIRMATION; pistas confirmadas |
| confirm | espera/múltiples | OWNERSHIP_VERIFIED; selección explícita dentro del conjunto, relectura y product ownership |
| collect | ownership verificado | ASSESSMENT_READY; revalidación y evidencia con límites documentados |
| fallo de lectura/ownership | búsqueda/confirmación/colección | INSUFFICIENT_EVIDENCE; nunca éxito vacío ficticio |
| handoff | cualquier estado no terminal | HANDOFF_RECORDED; política externa y humano obligatorios |

Se comprimen estados transitorios del diseño 03: autenticación falla antes de crear
un caso; búsqueda y verificación se realizan dentro del comando; el policy gate
siempre bloquea decisiones automáticas. No existe RESOLVED/CLOSED.
ASSESSMENT_READY significa listo para investigación humana, no elegibilidad financiera.
Un único candidato NO se selecciona automáticamente.

## Recuperación y tiempo

Solo customer del principal; nunca IDs de identidad del texto. Búsqueda por pistas
en [as_of - lookback_days, as_of], 1–30 días; comparación exacta de Decimal + moneda.
ID explícito puede recuperar un registro más antiguo, pero nunca futuro ni ajeno;
las otras pistas proporcionadas también deben coincidir. Sin conversiones ni tolerancias.
Cantidad sin moneda requiere clarificación. Una moneda de tres letras sin registros
no se convierte ni se supone equivalente a otra.
Máximo 50 candidatos, con truncation explícita; truncado nunca se considera único.
Fecha simple se interpreta en UTC en este backend de fixtures, no como inferencia
de la zona horaria de datos bancarios. Un adaptador real deberá documentarla.

Ownership transaction→customer y product→customer se revalida al confirmar y reunir
evidencia. Cambios de registro entre búsqueda/confirmación/colección requieren
revisión; no se reparan ni se reemplaza el registro silenciosamente.
as_of_time se fija al crear el caso; el reloj actual controla expiración de identidad.
event_time <= as_of; si available_at existe también debe ser <= as_of.
Contexto de 30 días usa timestamps estrictamente anteriores a la transacción,
mediana dentro de su moneda y flag de ventana observada completa.
Si se conoce available_at, también debe ser anterior al timestamp objetivo.
Sin timestamps de ingestion/revision no hay certificación point-in-time completa.
Status es evidencia snapshot; fraud_score e is_fraud no controlan ninguna transición.

## Persistencia, auditoría e idempotencia

SQLite con foreign keys, synchronous=FULL y BEGIN IMMEDIATE. Caso, evento de auditoría,
respuesta idempotente y paquete de handoff se guardan en la misma transacción.
Toda mutación exige expected version; el segundo escritor de una versión obsoleta
es rechazado. Claves idempotentes están aisladas por emisor, sujeto y cliente;
repetir el mismo comando devuelve su respuesta original sin duplicar efectos,
incluso después de reiniciar. Reutilizar clave con otro payload se rechaza.
El replay devuelve la respuesta histórica del comando; get devuelve el estado actual.

Auditoría de comandos exitosos: actor, provider, estados, versión, tiempo y hashes.
Rechazos de dominio/contrato al entrar al servicio se registran aparte, sin tokens,
texto ni IDs recibidos de quien pide acceso. Fallos de disco se propagan y revierten
el comando; no se anuncia éxito. El host deberá monitorizar esos fallos operativos.
Triggers impiden update/delete de auditoría: no es WORM ni protección ante un administrador
con acceso directo al archivo. Control de permisos, retención y cifrado son tareas del host.

El handoff incluye petición no confiable, referencia de identidad, selección/candidatos,
evidencia y referencias, ausencias, preguntas, guards y as_of. LOCAL_PENDING_HUMAN_REVIEW
significa paquete local persistido, NO aceptación por una cola externa ni resolución.
El texto original puede contener inyección: debe mostrarse como dato, nunca ejecutarse.

## Ejecutar sin modelo

En la raíz del repositorio, Python 3.12+:

    python -m venv .venv
    .venv/bin/python -m pip install -r requirements-case-runtime.txt
    .venv/bin/python -m pytest tests/test_case_runtime.py -q
    .venv/bin/python scripts/demo_dispute_cases.py

La demo guarda SQLite en .tmp/disputes/demo.sqlite3 (ignorado por Git).
Una segunda ejecución reutiliza los comandos y no duplica casos/handoffs.
No apunta a raw, a la caché DuckDB ni a customers reales.
requirements.txt mantiene el entorno más amplio para las regresiones del scaffold.

## Decisiones y límites pendientes

El puerto TransactionTools permite sustituir fixtures por consultas read-only sin
dar autoridad al LLM. Esa conexión NO está implementada aquí: falta mapear tipos,
timezone, disponibilidad y procedencia de los datos reales.
Los tools deben ser lecturas locales acotadas; no hacer llamadas de red dentro de
la transacción SQLite. Para un despliegue concurrente/distribuido, usar transacciones
y outbox en un store apropiado sin mantener locks mientras se llama a servicios externos.
No existe revisión humana operativa ni envío de notificaciones todavía.
No incorporar múltiples runtimes, RAG, embeddings o agentes para validar este núcleo.
El siguiente incremento es integrar IAM/serving y un adaptador de aplicación seguro;
la extracción/resumen LLM se evaluará después contra el benchmark congelado.
