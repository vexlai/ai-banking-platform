# Dataset-backed Banking Tools — Fase 2

## Arquitectura y contrato

FastAPI → CaseService → TransactionTools → FixtureTools o DatasetTools.
DatasetTools consulta DuckDB read-only; CaseStore conserva SQLite separado. No hay
SQL en rutas, endpoints nuevos, selección automática, LLM ni modificaciones al runtime.
Los métodos existentes son search, get, product_owner e history. Las respuestas son
SearchResult, Transaction y HistoricalContext existentes; errores operacionales son ToolFailure.

## Preparación reproducible desde la raíz

Python 3.12+. Instalar requirements.txt y requirements-dataset-tools.txt. Reutilizar la
caché analysis.duckdb generada por el EDA: no reconstruir analytics ni leer CSV por request.
Pasar su ubicación real mediante --source; no se autodetecta ni descarga.

~~~sh
python scripts/prepare_banking_serving.py \
  --source RUTA_RELATIVA_A_CACHE/analysis.duckdb \
  --output .tmp/banking_serving/transactions-v1.duckdb \
  --time-policy naive-as-utc-explicit-assumption
~~~

El comando sólo publica un archivo nuevo; rechaza sobrescritura. Valida firma de caché
contra profiling, formato temporal/decimal/moneda y campos obligatorios, PK, ownership
y orphans. No deduplica, imputa ni elimina outliers. Mantiene filas y merchant nulo.
Una preparación fallida conserva su archivo .building para inspección.
El admin configura el path de ATTACH READ_ONLY con escape SQL (DuckDB no parametriza
ese DDL); todos los valores de consultas bancarias sí utilizan parámetros.

Sólo se proyectan tres dominios: transactions (campos del contrato y provenance),
products (product_id/customer_id), customers (customer_id). PK e índice customer_id
evitan depender del scan de la caché analítica de strings sin índices. La proyección
local ocupa 900,214,784 bytes, no se versiona y no incluye PII textual de clientes.

## Configuración y ejecución

BANKING_TOOLS_BACKEND=fixture mantiene el arranque existente de Fase 1.
Para dataset, configurar en el entorno del servidor:

| Variable | Valor / responsabilidad |
|---|---|
| BANKING_TOOLS_BACKEND | dataset |
| BANKING_SERVING_PATH | .tmp/banking_serving/transactions-v1.duckdb |
| BANKING_TIME_POLICY | naive-as-utc-explicit-assumption |
| ENABLE_LEGACY_API | false, obligatorio |
| USE_LLM | false |
| DISPUTE_DATASET_DEMO_MODE | true, reconocimiento explícito de demo local |
| DISPUTE_DEMO_TOKEN_A / B | secretos distintos de al menos 32 caracteres |
| DISPUTE_DEMO_CUSTOMER_A / B | IDs distintos configurados por operador, nunca por frontend |
| DISPUTE_DB_PATH | .tmp/disputes/dataset-cases.sqlite3; distinto de serving |

~~~sh
uvicorn api.main:app --host 127.0.0.1 --port 8000
~~~

No publicar este adapter de identidad local como IAM real. Las credenciales expiran
una hora después de construir el verifier; usar tokens sólo del entorno privado.
Se conservan requests, headers y ejemplos de docs/SECURE_APPLICATION_ADAPTER.md.
Customer, principal y as_of_time no son inputs confiables del body. No hay fallback
silencioso a fixtures ante configuración errónea. Startup comprueba archivo, tablas
físicas, columnas/tipos, PK, índice y metadatos antes de atender requests.

## Semántica operacional

- Todas las búsquedas/get restringen customer_id y event_time <= as_of.
- Sin ID: ventana inclusiva [as_of-lookback_days, as_of], máximo 30 días.
- ID exacto: sin lookback obligatorio; ownership y cutoff siempre aplican.
- Clues permitidos son los del Search existente; igualdad reproducible, sin fuzzy.
- Monto usa Decimal y moneda explícita; CaseService rechaza monto sin moneda.
- Orden estable fecha/ID descendente; 50 candidatos y flag truncated mediante LIMIT 51.
- History: [candidate_time-30d, candidate_time), mismo cliente, mediana sólo en la
  moneda del candidato. Ventana incompleta se expresa con complete_window_observed=false.
- product_owner es lookup interno del puerto existente, sin endpoint público;
  CaseService lo utiliza después del acceso customer-scoped a la transacción.
- Un candidato, incluso único, requiere confirmación explícita. Provenance incluye
  hash de fuente, archivo relativo, ID y política temporal; el runtime agrega regla/as_of.
- Fraude, complaints y sus enlaces inválidos no forman parte de este serving.

## Límites temporales: no ocultarlos

Las fechas originales no tienen timezone. La opción explícita preserva wall-clock y
lo representa como UTC para interoperar con el contrato aware: es una suposición de
demo, NO evidencia de timezone bancario. No usar fuera de ese alcance sin validar TZ.
No existe available_at certificado: queda null. El cutoff de evento no certifica
disponibilidad de ingestión/revisión histórica. Products/customers son snapshots;
ownership es consistente en los datos observados, no una reconstrucción histórica.

Horizonte transaccional: 2023-06-17 06:01:30 a 2026-06-18 05:59:41 (wall-clock).
Con reloj real en octubre de 2026, búsquedas de los últimos 30 días retornan cero;
lookup por ID pasado sí funciona. No se desplazan datos ni se cambia el reloj runtime
en configuración operacional. El harness usa una factory de test separada para replay
histórico y credenciales controladas; nunca admite as_of proporcionado por HTTP.

## Validación

~~~sh
USE_LLM=false USE_MOCKS=true pytest tests -q
USE_LLM=false python scripts/smoke_dispute_http.py
USE_LLM=false python scripts/validate_dataset_tools.py \
  --serving .tmp/banking_serving/transactions-v1.duckdb
python scripts/verify_dispute_adapter_regressions.py
~~~

Los tests pequeños no necesitan datos del organizador. El harness real sí: prueba
0/1/N, ownership, moneda/cutoff, HTTP completo, reinicio, auditoría e idempotencia;
no selecciona clientes para demo ni crea complaint→transaction truth.
El benchmark es single-thread, proceso caliente, 50 clientes ordenados lexicalmente
con al menos dos operaciones en últimos 30 días observados; no es estimación productiva.
Los JSON de reports son regenerables. No incluyen credenciales ni IDs de clientes.
