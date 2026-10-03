"""Resumen reproducible de métricas guardadas; no consulta ni modifica datos raw."""
import json
from src.config import REPORTS


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(str(v) for v in row) + ' |' for row in rows])


def write_summary():
    inventory = json.loads((REPORTS / 'inventory.json').read_text())
    profile = json.loads((REPORTS / 'profiling.json').read_text())
    columns = profile['columns']
    lines = ['# Inventario e ingesta: resultados', '',
             'Alcance completado: 00 y 01. No se realizó EDA, limpieza, imputación ni modelado.', '',
             '## Datasets', '',
             table(['Dataset', 'Archivos CSV', 'Filas', 'Columnas', 'Bytes', 'MiB'],
                   [(d['dataset'], d['files'], d['rows'], d['columns'], d['bytes'],
                     f"{d['bytes']/2**20:.2f}") for d in inventory['datasets']]), '',
             f"Total: {sum(d['files'] for d in inventory['datasets']):,} archivos; "
             f"{sum(d['rows'] for d in inventory['datasets']):,} filas; "
             f"{sum(d['bytes'] for d in inventory['datasets']):,} bytes.", '',
             '## Claves candidatas comprobadas', '',
             'Son únicas y no nulas en esta entrega; esto no prueba estabilidad ni significado de negocio.', '',
             table(['Dataset', 'Columnas', 'Valores distintos'],
                   [(k['dataset'], k['columns'], k['distinct']) for k in profile['keys'] if k['candidate_key']]), '',
             'La lista completa, incluidos IDs que fallan unicidad, está en `candidate_keys.csv`.', '',
             'La unicidad accidental de direcciones, teléfonos, coordenadas o referencias externas no las convierte en claves de negocio recomendadas. Priorizar los IDs propios de cada entidad y contrastar las referencias con sus destinos.', '',
             '## Duplicados de fila', '',
             table(['Dataset', 'Filas repetidas adicionales'],
                   [(d['dataset'], d['duplicate_rows_excess']) for d in profile['datasets']]), '',
             '## Relaciones candidatas: comprobación de valores', '',
             'Nulos y referencias ausentes se reportan por separado. La unicidad del destino debe revisarse antes de hacer joins. La semántica sigue pendiente de validación.', '',
             table(['Origen', 'Destino', 'Nulos', 'Huérfanas', 'Coincidencia no nulos %', 'Repeticiones ID destino'],
                   [(f"{r['source_dataset']}.{r['source_column']}", f"{r['target_dataset']}.{r['target_column']}",
                     r['null_rows'], r['orphan_rows'], f"{r['match_pct_non_null']:.4f}" if r['match_pct_non_null'] is not None else 'N/A',
                     r['parent_duplicate_excess']) for r in profile['relationships']]), '',
             'Hipótesis adicional pendiente: relacionar la fecha de `transactions.transaction_date` y `transactions.currency` con `daily_exchange_rates.date` y `source_currency`, fijando la moneda destino requerida. Este enlace compuesto no se validó en esta fase.', '',
             '## Calidad de columnas', '',
             f"Columnas totalmente nulas: {sum(c['nulls'] == c['rows'] for c in columns)}. "
             f"Constantes entre no nulos: {sum(c['constant'] for c in columns)}. "
             f"Casi constantes: {sum(c['almost_constant'] for c in columns)}.", '',
             'Mayor porcentaje de faltantes (hasta 25 columnas; detalle completo en `column_profiles.csv`):', '',
             table(['Dataset', 'Columna', 'Nulos', '%'],
                   [(c['dataset'], c['column'], c['nulls'], f"{c['null_pct']:.2f}")
                    for c in sorted(columns, key=lambda x: x['null_pct'] or 0, reverse=True)[:25]]), '',
             'Los faltantes pueden depender de campos opcionales; no se asumen defectos de negocio sin evidencia.', '',
             '## Fechas', '',
             table(['Dataset', 'Columna', 'Inválidas', 'Posteriores al corte', 'Mínimo', 'Máximo'],
                   [(c['dataset'], c['column'], c['invalid_dates'], c['future_dates'], c['minimum'], c['maximum'])
                    for c in columns if c['possible_date']]), '',
             'Corte reproducible: 2026-09-28. Una fecha futura de expiración o fin de campaña puede ser legítima.', '',
             '## Posibles outliers', '',
             table(['Dataset', 'Columna', 'Mínimo', 'Máximo', 'Fuera de 1,5×IQR'],
                   [(c['dataset'], c['column'], c['minimum'], c['maximum'], c['possible_outliers'])
                    for c in columns if c['possible_outliers']]), '',
             'Son señales de perfilado, no errores demostrados. Monedas y escalas mezcladas pueden producirlas; no se eliminó ningún valor.', '',
             '## Decisiones técnicas y límites', '',
             '- Python 3.12, DuckDB para datos completos y pandas solo para resúmenes pequeños.',
             '- Lectura estricta con VARCHAR conserva IDs y ceros iniciales. Los tipos son candidatos verificados por conversión, no cambios al origen.',
             '- Vacíos CSV se interpretan como NULL; los espacios se registran sin normalizarlos.',
             '- Se verifican todos los encabezados; las particiones Hive no se añaden como columnas.',
             '- Conteos y cuartiles exactos; no se utilizó muestreo.',
             '- Casi constante: frecuencia dominante ≥99% de los valores no nulos.',
             '- Solo se prueba explícitamente una clave compuesta: fecha, moneda origen y moneda destino en tipos de cambio.',
             '- La cobertura de IDs no valida coherencia de cliente/producto/agente ni temporalidad entre tablas.',
             '- No hay diccionario de negocio que permita confirmar todos los rangos válidos o campos obligatorios.',
             '- Los originales permanecen en sus ubicaciones iniciales, tratadas como raw inmutable.', '',
             '## Integridad de originales', '']
    findings = ['## Hallazgos principales', '']
    for r in profile['relationships']:
        if r['orphan_rows']:
            findings.append(f"- `{r['source_dataset']}.{r['source_column']}`: {r['orphan_rows']:,} referencias sin coincidencia de {r['source_rows'] - r['null_rows']:,} no nulas en `{r['target_dataset']}.{r['target_column']}`.")
    for c in columns:
        if c['nulls'] == c['rows']:
            findings.append(f"- `{c['dataset']}.{c['column']}`: completamente nula ({c['rows']:,} filas).")
        if c['column'] == 'last_updated' and c['future_dates']:
            findings.append(f"- `{c['dataset']}.last_updated`: {c['future_dates']:,} valores posteriores al corte 2026-09-28; máximo {c['maximum']}. Requieren aclaración temporal.")
    findings.extend([
        f"- Filas duplicadas adicionales dentro de las tablas: {sum(d['duplicate_rows_excess'] for d in profile['datasets']):,}. Valores de fecha no convertibles en las columnas evaluadas: {sum(c['invalid_dates'] or 0 for c in columns):,}.",
        f"- {sum(bool(c['possible_outliers']) for c in columns)} columnas numéricas contienen posibles outliers IQR; no se corrigieron ni eliminaron.", '',
    ])
    lines[4:4] = findings
    for name in ('inventory_integrity.json', 'profiling_integrity.json'):
        lines.extend([f"`{name}`: `{(REPORTS / name).read_text().strip()}`", ''])
    (REPORTS / 'SUMMARY.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    write_summary()
