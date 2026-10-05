# Distribución privada de datos del MVP

## Qué se entrega

Dos paquetes independientes, fuera de Git, generados desde bases existentes sin repetir EDA:

| Paquete | Contenido | Uso |
|---|---|---|
| banking-serving-v1.zip | transactions-v1.duckdb + manifest.json | API dataset-backed; transactions/products/customers y metadatos |
| banking-analytics-v1.zip | analysis.duckdb + manifest.json | Caché analítica proyectada existente, no todos los campos raw |

Cada ZIP tiene un archivo externo `.zip.sha256`. El manifiesto contiene versión de
DuckDB, tamaños, SHA-256 de la base, conteos de tablas y clasificación privada.
No contiene raw, credenciales, tokens, SQLite de casos ni FAISS. La caché analítica
puede contener IDs y rutas históricas de procedencia: no está certificada como anónima.
Compartir únicamente con miembros autorizados y según las reglas del organizador.

Los paquetes no están cifrados por este script. Usar almacenamiento privado con ACL
del equipo, cifrado en reposo/tránsito y enlaces con expiración. Comunicar el checksum
por un canal confiable: un hash dentro del mismo paquete no autentica al remitente.
No subir `.env`, `.tmp` completo ni bases SQLite operacionales. No se ha realizado
ninguna subida automática ni configurado un proveedor de almacenamiento.

## Remitente: exportar sin reingesta

Python 3.12+, dependencias del proyecto y requirements-dataset-tools.txt.
Detener escritores de las bases antes de exportar; el exportador rechaza WAL,
mantiene conexión read-only durante copia y comprueba hash original antes/después.
No sobrescribe paquetes; una falla conserva `.building` para inspección.

```sh
python scripts/package_banking_data.py build --kind serving \
  --source .tmp/banking_serving/transactions-v1.duckdb \
  --output .tmp/distribution/banking-serving-v1.zip

python scripts/package_banking_data.py build --kind analytics \
  --source RUTA_A_CACHE/analysis.duckdb \
  --output .tmp/distribution/banking-analytics-v1.zip
```

Subir solamente los dos ZIP y sus archivos SHA-256. Para desarrollo de API basta serving.
Si falta serving, el constructor existente es `scripts/prepare_banking_serving.py`,
documentado en [DATASET_BACKED_TOOLS.md](DATASET_BACKED_TOOLS.md).

## Receptor: descargar, verificar e instalar

Clonar el código compatible y descargar los paquetes autorizados a `data/downloads/`.
No colocar bases derivadas en `data/raw/`: esa carpeta es para originales inmutables.
Sustituir SHA256_RECIBIDO por los 64 caracteres recibidos del remitente.
Verificar/importar sólo usa la biblioteca estándar de Python; no descarga dependencias.

```sh
python scripts/package_banking_data.py install \
  --bundle data/downloads/banking-serving-v1.zip \
  --sha256 SHA256_RECIBIDO \
  --destination data/serving
```

La carpeta destino debe ser nueva. Se valida el ZIP completo y la base interna antes
de publicar; no se extraen rutas arbitrarias. La base queda con permisos 0400 y la
carpeta 0700. Usar el mismo usuario para ejecutar la API; permisos locales no reemplazan IAM.
Para revisar sin extraer, usar `verify` con `--bundle` y `--sha256`.

Opcional para análisis:

```sh
python scripts/package_banking_data.py install \
  --bundle data/downloads/banking-analytics-v1.zip \
  --sha256 SHA256_ANALYTICS_RECIBIDO \
  --destination data/analytics
```

Consultar `data/analytics/analysis.duckdb` con `duckdb.connect(..., read_only=True)`.
No significa que todos los notebooks puedan reejecutarse sin raw: algunos verifican
el manifiesto original, usan rutas `dataset/` o escriben en su propia caché `.tmp/eda`.
La distribución no altera esas convenciones ni garantiza reconstrucción desde cero.

## Arrancar el runtime actual

Instalar requirements.txt, requirements-dataset-tools.txt y requirements-identity-intake.txt
en un entorno propio; no depender del entorno del proyecto analítico de otro desarrollador.
Configurar:

```sh
export BANKING_TOOLS_BACKEND=dataset
export BANKING_SERVING_PATH=data/serving/transactions-v1.duckdb
export BANKING_TIME_POLICY=naive-as-utc-explicit-assumption
export DISPUTE_DATASET_DEMO_MODE=true
export ENABLE_LEGACY_API=false
export DISPUTE_DB_PATH=.tmp/disputes/local.sqlite3
export DISPUTE_IDENTITY_BACKEND=jwt
export INTAKE_EXTRACTOR=baseline
export USE_LLM=false
```

Provisionar secretos/emisor/audiencia y tokens localmente siguiendo
[IDENTITY_AI_INTAKE.md](IDENTITY_AI_INTAKE.md); nunca copiar tokens del remitente.
Después: `uvicorn api.main:app --host 127.0.0.1 --port 8000`.
El startup valida schema/PK/índice/metadatos usando DatasetTools. El estado se escribe
en SQLite separado; DuckDB se abre read-only. No se requieren OpenAI ni FAISS.

## Sobre la propuesta «raw → src.data.ingest → docker compose»

No es el flujo implementado: `src.data.ingest` no existe, FAISS no es parte del MVP,
y `docker-compose.yml`/Dockerfile actuales corresponden al scaffold legado. No instalan
todas las dependencias nuevas ni montan serving read-only/SQLite durable con identidad
JWT configurada. Por eso `docker compose up -d` no valida este flujo dataset-backed.
No se modificó Docker en esta entrega. La integración Compose del runtime actual es
un siguiente cambio acotado, no una razón para crear embeddings ni rehacer EDA.

## Verificaciones

`pytest tests/test_data_distribution.py -q`: checksum incorrecto, corrupción interna,
miembro de archivo inesperado/traversal, permisos privados y negativa a sobrescribir.
La copia real debe verificarse además con `verify`; usar el SHA externo confiable.
Los conteos no se recalculan como profiling: son inventario mínimo de tablas empaquetadas.
