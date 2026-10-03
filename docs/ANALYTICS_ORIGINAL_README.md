# Banking Customer Service System · análisis inicial

El proyecto cuenta con inventario, profiling, EDA general, addendum transaccional,
discovery del workflow y definición/evaluación offline del MVP. No se implementó
un agente, API, frontend ni servicio productivo.

## Reproducir

Desde la raíz, con Python 3.12 o superior:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/run_notebooks.py
.venv/bin/python -m unittest discover -s tests -v
```

El ejecutor guarda ambos notebooks con sus salidas y se detiene ante errores.
En Linux impide ejecuciones simultáneas mediante un bloqueo de archivo. Para
reanudar solo el perfilado: `.venv/bin/python scripts/run_notebooks.py --only 01`.
Para una ejecución desacoplada de la terminal:

```sh
setsid --fork .venv/bin/python -u scripts/run_notebooks.py --only 01 > reports/profiling/execution.log 2>&1
```

El log, `execution_progress.json` y los notebooks guardados permiten revisar el avance.
Jupyter necesita abrir puertos locales para su kernel. Cada notebook también puede
ejecutarse de arriba abajo desde la raíz o desde `notebooks/`.

## Datos y trazabilidad

Los CSV originales se mantienen en `dataset/`, incluidos sus directorios particionados.
`data/raw/README.md` documenta esa capa raw lógica, sin copias ni movimientos.
`data/interim/` y `data/processed/` quedan reservados y vacíos.
DuckDB usa una base temporal comprimida en `.tmp/`, límite de memoria de 2 GB y hasta cuatro hilos;
puede necesitar espacio temporal en disco. Solo se materializa un dataset completo
a la vez; las tablas agregadas de IDs se conservan durante la comprobación de relaciones.
La base temporal se elimina al cerrar la conexión. Si una columna ya se comprobó
única y no nula, eso demuestra ausencia de filas duplicadas sin agrupar toda la tabla.

`src/config.py` centraliza rutas relativas al proyecto y fecha de corte;
`src/data_utils.py` contiene descubrimiento, lectura y hashes;
`src/profiling_utils.py` implementa métricas y validación de relaciones candidatas.

## Salidas

En `reports/profiling/`:

- `source_manifest.json`: archivos, bytes, encabezados y SHA-256.
- `files.csv`, `datasets.csv`: inventarios exactos por archivo y dataset.
- `inventory_columns.csv`: tipos físicos, nulos, cardinalidades, posibles IDs y fechas.
- `column_profiles.csv`: tipos candidatos, constantes, rangos, fechas y outliers.
- `duplicates.csv`: filas repetidas adicionales, excluyendo procedencia.
- `candidate_keys.csv`: unicidad, faltantes y repeticiones de IDs y claves candidatas.
- `relationships.csv`: cobertura de referencias y duplicados en el destino.
- `inventory.json`, `profiling.json`: resultados completos estructurados.
- `*_integrity.json`: comprobación de que los originales no cambiaron.
- `SUMMARY.md`: hallazgos y decisiones después de la ejecución.

Los resultados son conteos completos, no estimaciones por muestreo. Se conserva
el texto original para evitar pérdida de ceros iniciales o fechas inválidas.
Las celdas CSV vacías se interpretan como NULL. Las reglas de tipos, casi constantes
y outliers están documentadas en 01; no implican corrección de datos.
Las coincidencias de IDs no confirman por sí solas el significado de una relación.

Para recuperarse de interrupciones, 00 puede usar `inventory(reuse_verified=True)`:
solo reutiliza un inventario completo con integridad comprobada y vuelve a calcular
todos los hashes. Usar `False` fuerza el recálculo de métricas (también si se cambia
su implementación). 01 reutiliza nulos y cardinalidades de 00 bajo la misma comprobación;
si esos reportes no existen, los calcula. Los archivos `*.partial.csv` y
`execution_progress.json` son seguimiento de ejecución, no entregables definitivos.

## EDA: etapa 02

El notebook `notebooks/02_eda.ipynb` reutiliza el profiling existente y ejecuta
validaciones semánticas y temporales antes de los análisis descriptivos. Para ejecutarlo:

```bash
.venv/bin/python scripts/run_eda_notebook.py
```

Las consultas usan proyecciones DuckDB en disco (`.tmp/eda/`, ignorada por Git),
dos hilos y 1.5 GB de memoria. Los originales se verifican con SHA-256 al inicio
y al final. No se repiten los notebooks 00/01.

Resultados y metodología: [reports/eda/README.md](reports/eda/README.md).
Hallazgos: [reports/eda/EDA_FINDINGS.md](reports/eda/EDA_FINDINGS.md).
Figuras: `reports/figures/eda/`. `customer_360_eda.parquet` combina solamente
agregados por cliente y valida unicidad. El corte temporal y las limitaciones
de cobertura se documentan junto a las features.

## Discovery y cierre del MVP: etapas 02b–05

- `notebooks/02b_transaction_dispute_eda_addendum.ipynb`: validación orientada al caso de uso.
- `notebooks/03_dispute_case_workflow_discovery.ipynb`: candidatos, evidencia y diseño futuro de estados.
- `notebooks/04_mvp_use_case_definition.ipynb`: contrato formal congelado del MVP.
- `notebooks/05_baseline_and_eval_dataset.ipynb`: parser regex, datasets versionados y evaluación offline.

Los antiguos `04_use_case_definition.ipynb` y `05_baseline.ipynb` se conservan como
referencias de compatibilidad a los notebooks canónicos, sin análisis duplicado.

Para ejecutar únicamente 04/05, sin repetir profiling, EDA ni discovery:

```sh
.venv/bin/python scripts/run_mvp_and_eval.py
.venv/bin/python -m unittest discover -s tests -v
```

El MVP es **Transaction Dispute Intake & Investigation Copilot**, con decisión
**GO WITH CONSTRAINTS** y resultado observable futuro **HANDOFF_RECORDED**, no
DISPUTE_RESOLVED. Auth, ownership, política, acciones financieras y cierre no son
autoridad del LLM. El único componente aprendido propuesto es extracción estructurada;
no se ejecutó un LLM ni se entrenó un modelo.

Entregables:

- [Discovery](reports/DISPUTE_CASE_WORKFLOW_FINDINGS.md)
- [Definición del MVP](reports/MVP_USE_CASE_DEFINITION.md)
- [Contrato congelado](reports/FROZEN_MVP_CONTRACT.md)
- [Baseline y evaluación](reports/BASELINE_AND_EVALUATION_FINDINGS.md)
- `artifacts/mvp_definition/`: contratos y firmas de evidencia.
- `artifacts/evaluation/`: dataset JSONL, fixtures, predicciones, métricas y manifest.

Las utterances nuevas son **synthetic/team-generated**; no son reclamos observados.
Dev/test separa clientes/transacciones, no familias de templates ni periodos temporales.
Portugués es generado y requiere revisión lingüística. Los archivos congelados rechazan
cambios silenciosos: una modificación de dataset/contrato requiere nueva versión y revisión.
Las pruebas de retrieval usan tablas controladas, no complaint→transaction ground truth.
