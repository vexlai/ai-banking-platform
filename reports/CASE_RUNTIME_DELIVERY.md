# Entrega 1 — núcleo determinístico persistente

Validación local: 2026-10-03. Resultado: PASS para el alcance offline definido.
No es certificación de seguridad productiva ni de adjudicación bancaria.

## Flujo implementado

Principal externo verificado → intake → pistas regex no confiables → búsqueda
confirmada → ramificación sin/uno/múltiples candidatos → selección explícita
→ ownership transaction/product/customer → evidencia y contexto histórico
→ política automática bloqueada → HANDOFF_RECORDED.

Las rutas sin candidato, ambiguas o con evidencia insuficiente también permiten
registrar un handoff, sin fabricar una transacción ni hechos verificados.
La selección por cliente no constituye ground truth complaint→transaction.

SQLite persiste caso, auditoría, respuesta idempotente y handoff en una sola
transacción. Las mutaciones exigen versión esperada. Repetir un comando idéntico
no duplica efectos; otra carga con la misma clave se rechaza. La inicialización
del esquema también se revierte si la versión existente no es compatible.
Una nueva base se crea con permisos 0600; no se cambian permisos de bases existentes.

## Evidencia de verificación

| Comprobación | Resultado |
|---|---|
| Pruebas del núcleo con bloqueo de conexiones de red | 37 aprobadas |
| Regresiones existentes API/guardrails/orchestrator/policy, LLM desactivado | 19 aprobadas |
| Total de la ejecución final | 56 aprobadas |
| Lint y formato del código nuevo | aprobados |
| Demo explícita/ambigua/sin candidato | 3 HANDOFF_RECORDED |
| Reejecución de demo y recuperación de SQLite | mismos IDs; sin duplicados |
| Auditoría de los tres casos de demo | 5 / 3 / 3 eventos, sin crecimiento por replay |
| Archivos analíticos importados | 279 SHA256 idénticos al origen |
| Predicciones del baseline congelado | 384 idénticas |
| Fixtures de retrieval congelados | métricas idénticas en 132 fixtures |

Las pruebas cubren expiración/scope/credencial inválida, aislamiento entre clientes,
límites de tiempo y moneda, confirmación explícita, ownership revalidado, cambios
de registro, contexto estrictamente anterior, truncation explícita, errores de tools,
concurrencia, reinicio, rollback, idempotencia, rechazos auditados y schema incompatible.
El texto de prompt injection no tiene autoridad sobre identidad ni acciones.
Esto NO evalúa resistencia de un LLM a inyecciones: no hay modelo en este flujo.

Los 3 golden cases del scaffold también pasaron como smoke tests; sus métricas
de grounding basadas en marcadores no son validación factual del nuevo sistema.
La CI remota no fue ejecutada en esta sesión; se actualizó para incorporar el núcleo.

## Límites de esta entrega

- Backend de transacciones y autenticación: fixtures sintéticos explícitos.
- Verificación de issuer/firma/revocación: responsabilidad del host IAM aún no integrado.
- API/UI legado: no conectado al núcleo nuevo; conserva sus restricciones conocidas.
- Handoff: LOCAL_PENDING_HUMAN_REVIEW, no aceptación por cola externa ni resolución.
- Política: EXTERNAL_POLICY_REQUIRED; no decisión financiera, reembolso, fraude ni cierre.
- Datos reales: no conectados a tools; no se volvió a ejecutar profiling/EDA/discovery.
- Ingestion/revision histórica: no certificada; se preserva esta limitación en la evidencia.
- Auditoría append-only en la aplicación, no almacenamiento WORM ante un administrador.
- Pruebas sintéticas: no demuestran precisión de matching ni beneficios en producción.

No se modificaron raw ni artefactos congelados. La verificación final de raw fue
por tamaños (7.671 archivos), no por un nuevo hash completo del contenido.

## Reproducción

Desde la raíz de ai-banking-platform:

    .venv/bin/python -m pytest tests/test_case_runtime.py -q
    .venv/bin/python scripts/demo_dispute_cases.py

La demo conserva su base en .tmp/disputes/demo.sqlite3, ignorada por Git.
Para comenzar otra demo usar --db con un archivo nuevo, sin borrar la anterior.
Dependencias mínimas fijadas en requirements-case-runtime.txt.
Contratos, estados y límites completos: docs/DETERMINISTIC_CASE_RUNTIME.md.

El siguiente incremento es un adaptador de aplicación seguro con IAM y serving
read-only, manteniendo estos guards. La integración de extracción/summary LLM
debe evaluarse después contra el benchmark congelado.
