# Integración analítica — runtime sin cambios

## Procedencia y alcance

Se importaron notebooks, código, tests, informes y artefactos existentes desde
BankingCustomerServiceSystem, conservando el origen intacto. No se importó código
de assignment. No se copiaron .git, entornos ni cachés; no se creó ningún commit.
artifacts/integration/analytics_import_manifest.json registra commits, rutas y SHA256.
Los informes históricos describen su etapa analítica, no el runtime actual.

Autoridad: reports/FROZEN_MVP_CONTRACT.md, MVP_USE_CASE_DEFINITION.md,
DISPUTE_CASE_WORKFLOW_FINDINGS.md y BASELINE_AND_EVALUATION_FINDINGS.md.
Los notebooks canónicos 00–05 conservan outputs; los nombres antiguos 04/05
son referencias de compatibilidad. El README analítico original está en
docs/ANALYTICS_ORIGINAL_README.md; sus enlaces se interpretan desde la raíz original.

## Estructura conservadora

Se mantienen src/*.py analíticos y src/evaluation/ porque no colisionan con
orchestrator, tools, policy ni telemetry. Moverlos a src/analytics alteraría imports
y rutas firmadas sin necesidad. No reformatear el parser ni métricas congelados.
requirements-analytics.txt mantiene dependencias analíticas separadas del runtime.
Python mínimo 3.12. Los tests analíticos son adicionales; el runtime no los importa.

## Datos sin duplicación

dataset es un enlace local ignorado por Git al dataset original. Los 7.671 CSV
no se movieron ni copiaron. La caché DuckDB de aproximadamente 1,4 GB no se copió.
En otra máquina provisionar un mount de solo lectura o un enlace local llamado
dataset al directorio de datos. La ruta es configuración local, no código versionado.
Un symlink no impone permisos de solo lectura: usar un mount read-only cuando se
requiera aislamiento efectivo. No borrar el origen mientras el enlace dependa de él.
Docker excluye datos, notebooks, artefactos y reports del contexto de construcción.

No se necesita raw ni caché para verificar el baseline. Reejecutar EDA puede
reconstruir cachés y es costoso; no se realizó en la migración. No compartir una
caché DuckDB escribible entre repositorios.

## Verificación sin repetir EDA

Desde la raíz, en un entorno Python 3.12+ con requirements-analytics.txt instalado:

```sh
python scripts/verify_analytics_integration.py
python -m unittest discover -s tests -p 'test_intake_evaluation.py'
python -m unittest discover -s tests -p 'test_profiling.py'
python -m unittest discover -s tests -p 'test_dispute_addendum.py'
python -m unittest discover -s tests -p 'test_dispute_workflow.py'
```

El verificador compara SHA256, splits, 384 predicciones y métricas de 132 fixtures
contra outputs existentes, sin reescribirlos. Valida estructura de notebooks,
no los vuelve a ejecutar. Con raw disponible verifica tamaños, no recalcula hashes
de su contenido. --source ../BankingCustomerServiceSystem verifica también el origen.
El entorno instalado del origen puede usarse para esta auditoría inicial, pero no
es dependencia permanente: instalar requirements-analytics.txt en un entorno propio.

## Congelación y siguiente etapa

artifacts/evaluation se conserva byte a byte. Sus commits y fechas son históricos;
no cambiarlos para aparentar una evaluación nueva. Casos synthetic/team-generated,
sin ground truth complaint→transaction. No retocar el parser tras mirar test.
Las firmas de importación son la referencia inicial: cualquier evolución posterior
debe versionarse y documentarse, no ocultarse alterando ese historial.

Siguiente etapa NO implementada aquí: contratos MVP, principal autenticado externo,
casos persistentes, selección explícita, ownership/as_of, idempotencia, auditoría,
handoff registrado; después extracción y summary LLM evaluados contra el baseline.
Sin adjudicación automática ni autoridad de fraud_score.

Brechas actuales: API key no autoriza al cliente; tools aceptan customer_id del
modelo; state machine por turno; handoff y trazas sin persistencia durable.
Las evals antiguas son smoke tests, no validación de grounding semántico.

## Resultado de validación de la migración (2026-10-03)

- 279 archivos importados idénticos por SHA256 al origen.
- Parser: 384 predicciones idénticas al baseline congelado.
- Retrieval: métricas idénticas en 132 fixtures controlados.
- 17 pruebas unitarias analíticas aprobadas (10 intake, 2 profiling con fixtures
  pequeños, 3 addendum con fixtures, 2 discovery con fixtures).
- Notebooks validados estructuralmente; no ejecutados de nuevo.
- 7.671 raw comprobados por tamaño/mtime durante importación; no se recalculó
  su contenido SHA256 ni se repitió profiling/EDA sobre datos reales.
- Proyecto origen sin cambios Git; implementación del runtime sin cambios.
- Sin llamadas LLM, sin instalación de dependencias ni acciones financieras.

Se utilizó Python 3.12 del entorno analítico original para las comprobaciones.
Las pruebas de FastAPI/runtime y la CI remota no se ejecutaron en esta migración;
ese entorno no tiene sus dependencias. No se afirma validación del runtime.
La CI nueva separa suites analíticas de runtime y mantiene modelos desactivados.
