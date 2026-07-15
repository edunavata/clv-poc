# Spec — Corrección de selección de cierre en el mart (`clv_snapshots`)

Sub-proyecto A del documento de requisitos "Captura autónoma y CLV contra cierre real". Independiente y previo al sub-proyecto B (sistema de captura autónomo), porque se apoya en datos ya capturados (columna `api_last_update`, presente desde el esquema actual de `snapshots`).

## Problema

`CLOSING_LINES_QUERY` (storage/db.py) selecciona el cierre con `arg_max(odds, captured_at)`, filtrando solo `captured_at < commence_time`. Esto usa el **instante de sondeo** (nuestro proceso) como criterio de "más reciente", no el **timestamp de validez que el propio Pinnacle reporta** (`api_last_update`). Un sondeo puede devolver un precio con `api_last_update` viejo (mercado no actualizado) y aun así ganar por ser el sondeo más tardío. Además no existe ninguna auditoría de cuán lejos del inicio quedó ese cierre.

Evidencia real: `France–Spain` (empate, William Hill) y `Argentina–Egypt` (Egipto, Winamax) tienen "cierre" de Pinnacle idéntico al instante de captura del soft, a 4.6h y 22.3h del inicio respectivamente — el sistema de captura actual no tiene ninguna ráfaga cerca del inicio, así que el único pre-commence disponible está lejos. Este fix corrige la **lógica de selección**; no puede, por sí solo, arreglar la **falta de dato** cercano al cierre — eso depende del scheduler de sub-proyecto B.

## Alcance

**Dentro:**
- Cambiar el criterio de selección de cierre de `captured_at` a `api_last_update`.
- Exponer `hours_before_commence` por fila de `clv_snapshots` como auditoría (sin umbral duro de exclusión).
- Loguear explícitamente la lista de `event_id` sin cierre válido (no solo un conteo agregado).
- Tests que reproducen el caso real y un caso donde `api_last_update` y `captured_at` divergen.

**Fuera:**
- Sistema de captura autónomo (descubrimiento, scheduling, ráfaga de cierre, resiliencia, supervivencia a reinicios) — sub-proyecto B, spec aparte.
- Matemática de devig/CLV — no se toca.
- Umbral duro de "cierre rancio" que excluya filas — se deja para cuando haya datos reales del scheduler nuevo con los que calibrar un umbral con sentido.

## Diseño

### 1. `storage/db.py` — `CLOSING_LINES_QUERY`

Cambiar:
```sql
WHERE sport_key = ? AND book = ? AND captured_at < commence_time
...
arg_max(odds, captured_at) AS closing_odds,
max(captured_at) AS closing_captured_at
```
a filtrar y ordenar por `api_last_update`:
```sql
WHERE sport_key = ? AND book = ? AND api_last_update < commence_time
...
arg_max(odds, api_last_update) AS closing_odds,
max(api_last_update) AS closing_api_last_update
```

### 2. `analysis/report.py`

- `fair_probs_by_market`: el campo devuelto pasa de `closing_captured_at` a `closing_api_last_update` (misma posición de columna, semántica corregida).
- `build_clv_rows`: añade `hours_before_commence = (commence_time - closing_api_last_update).total_seconds() / 3600` por fila.
- `build_target_rows`: cuando un (event_id, market) no tenga fila con `api_last_update < commence_time`, la fila sigue excluida de `clv_snapshots` (comportamiento actual), pero además se loguea la lista de `event_id` afectados (hoy solo hay un contador agregado `skipped`).

### 3. Esquema `clv_snapshots` (storage/db.py)

- Renombrar `pinnacle_closing_captured_at` → `pinnacle_closing_last_update`.
- Añadir `hours_before_commence DOUBLE NOT NULL`.
- Full refresh (`CREATE OR REPLACE TABLE`), sin migración — comportamiento ya existente del mart.

### 4. Tests

- `tests/test_storage.py`: caso donde dos sondeos pre-commence tienen `captured_at` distinto pero el de `captured_at` mayor tiene `api_last_update` **menor** (mercado stale) — debe ganar el de `api_last_update` mayor, no el de `captured_at` mayor.
- `tests/test_report.py`: mismo caso a nivel de `build_clv_rows`, verificar `hours_before_commence` calculado correctamente; caso evento sin ninguna fila `api_last_update < commence_time` → excluido y aparece en el log de sin-cierre.
- Verificación con datos reales: correr `analysis.report` sobre `data/odds.duckdb`, confirmar que France–Spain / Argentina–Egypt siguen apareciendo en `clv_snapshots` (no hay caso de "cierre inexistente" hoy) con `hours_before_commence` reflejando 4.6h / 22.3h — auditable, no oculto.

## Criterios de aceptación

- AC-A1. Selección de cierre usa `api_last_update`, no `captured_at`.
- AC-A2. `clv_snapshots` expone `hours_before_commence` por fila.
- AC-A3. Eventos sin ninguna fila sharp pre-commence quedan excluidos de `clv_snapshots` y su `event_id` aparece en el log, no solo en un conteo.
- AC-A4. Tests cubren el caso de divergencia `captured_at` vs `api_last_update` y pasan.
- AC-A5. Con los datos actuales, France–Spain / Argentina–Egypt siguen calculándose (fix no introduce falsos "sin cierre" donde antes había dato), con distancia al inicio visible.
