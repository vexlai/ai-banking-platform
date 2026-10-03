# AGENTS.md

## Objetivo del proyecto

Este proyecto corresponde a un hackathon de datos bancarios.

El objetivo inicial es entender, perfilar y analizar los datasets disponibles antes de definir casos de uso de IA, construir agentes o implementar modelos.

No asumir conclusiones de negocio antes de analizar los datos reales.

---

## Principios de trabajo

1. No inventar nombres de archivos, tablas, columnas, relaciones, claves o métricas.
2. Inspeccionar siempre los datasets reales antes de implementar lógica específica.
3. No modificar, sobrescribir ni eliminar los datasets originales.
4. Mantener trazabilidad entre datos originales, datos intermedios y datos procesados.
5. No aplicar limpieza agresiva sin evidencia.
6. No eliminar outliers automáticamente.
7. No imputar valores faltantes durante profiling o EDA inicial.
8. Toda anomalía debe registrarse primero como hallazgo.
9. Las relaciones entre tablas deben considerarse hipótesis hasta ser validadas con los datos.
10. No comenzar modelado, agentes IA o frontend mientras la etapa correspondiente de análisis no haya sido completada.

---

## Estructura objetivo

notebooks/
- 00_dataset_inventory.ipynb
- 01_ingestion_profiling.ipynb
- 02_eda.ipynb
- 02b_transaction_dispute_eda_addendum.ipynb
- 03_dispute case workflow discovery.ipynb
- 04_use_case_definition.ipynb
- 05_baseline.ipynb

data/
- raw/
- interim/
- processed/

reports/
- figures/
- profiling/

src/
- __init__.py
- config.py
- data_utils.py
- profiling_utils.py

Antes de crear carpetas nuevas, revisar la estructura existente y reutilizarla cuando sea razonable.

---

## Datos

Los datasets ya se encuentran dentro del proyecto.

No mover ni duplicar archivos grandes sin necesidad.

La carpeta o ubicación real de los datasets debe detectarse mediante inspección del repositorio.

La capa raw debe considerarse inmutable.

---

## Python

Usar Python 3.12 o superior.

Preferencias:

- pathlib para rutas
- DuckDB para consultas analíticas sobre datasets grandes
- Polars para procesamiento eficiente
- pandas cuando el tamaño sea razonable o simplifique el análisis
- matplotlib para visualización

Evitar seaborn.

No hardcodear rutas absolutas.

El código debe funcionar ejecutándose desde la raíz del repositorio.

---

## Rendimiento

Antes de cargar un dataset completo:

1. comprobar formato;
2. comprobar tamaño;
3. determinar si realmente es necesario cargarlo completo.

Para datasets grandes:

- usar DuckDB;
- usar Polars lazy;
- usar lectura por batches;
- o usar muestras reproducibles.

Cuando se utilice sampling, documentar claramente qué resultados son estimaciones.

---

## Notebooks

Los notebooks deben:

- ejecutarse de arriba hacia abajo;
- no depender de estado oculto;
- contener explicaciones breves de cada etapa;
- separar análisis de conclusiones;
- reutilizar funciones de `src/`;
- evitar duplicación innecesaria de código.

Los resultados importantes deben almacenarse en `reports/` cuando tenga sentido.

---

## Etapas del proyecto

El trabajo debe seguir este orden:

1. Dataset inventory
2. Ingestion and profiling
3. EDA
4. Customer journey discovery
5. Use case definition
6. Baseline
7. Diseño de solución IA
8. Implementación de agentes/modelos
9. Evaluación
10. Demo

No saltar directamente a agentes o modelos.

---

## Dataset inventory

El inventario debe permitir conocer:

- archivos disponibles;
- formatos;
- tamaños;
- filas;
- columnas;
- schemas;
- nulos;
- cardinalidades;
- posibles IDs;
- posibles fechas;
- posibles relaciones.

Las relaciones detectadas automáticamente son candidatas y deben validarse.

---

## Profiling

El profiling debe identificar al menos:

- nulos;
- duplicados;
- tipos;
- cardinalidad;
- constantes;
- casi constantes;
- fechas inválidas;
- rangos;
- posibles outliers;
- calidad de IDs;
- anomalías.

No corregir automáticamente los problemas detectados.

---

## EDA

El EDA debe partir de los resultados del profiling.

No crear análisis basados en columnas que no existan.

Priorizar preguntas que ayuden a entender:

- clientes;
- transacciones;
- comportamiento temporal;
- interacciones;
- reclamos;
- satisfacción;
- journeys;
- relaciones entre datasets.

---

## Calidad del código

Priorizar:

- simplicidad;
- legibilidad;
- reproducibilidad;
- modularidad;
- eficiencia.

No introducir arquitectura innecesaria para un hackathon.

No crear clases si funciones simples son suficientes.

---

## Antes de finalizar una tarea

Verificar:

1. que el código ejecuta;
2. que no se modificaron datos raw;
3. que no hay rutas locales hardcodeadas;
4. que no se inventaron columnas;
5. que las salidas importantes están documentadas;
6. que cualquier limitación queda indicada.

Después de ejecutar análisis importantes, resumir los hallazgos y archivos generados.