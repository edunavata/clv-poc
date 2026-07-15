# Mart Closing-Line Selection Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `clv_snapshots` select Pinnacle's closing price by the timestamp Pinnacle itself reports as its last update (`api_last_update`), not by our polling instant (`captured_at`), and expose per-row distance-to-commence auditing plus explicit visibility into events with no valid closing line.

**Architecture:** Two-column change in the `snapshots` → `clv_snapshots` pipeline: (1) `CLOSING_LINES_QUERY` in `storage/db.py` re-keys its `arg_max`/`max` on `api_last_update` instead of `captured_at`; (2) `analysis/report.py` threads that renamed field through, computes `hours_before_commence`, and surfaces the list of events lacking a closing line instead of only a count.

**Tech Stack:** Python, DuckDB, pytest. No new dependencies.

## Global Constraints

- No devig/CLV math changes — `analysis/clv.py` untouched.
- No schema migration machinery — `clv_snapshots` is `CREATE OR REPLACE TABLE`, full refresh, already the existing pattern.
- No hard exclusion threshold on `hours_before_commence` — audit-only column, per spec decision.
- Every piece proven with real output before considered done (project convention, CLAUDE.md "Testing").
- Commit each task atomically once its tests pass (project convention, CLAUDE.md "Guardrail de control de versiones").

---

### Task 1: Fix `CLOSING_LINES_QUERY` to select by `api_last_update`

**Files:**
- Modify: `storage/db.py:26-33` (`CLOSING_LINES_QUERY`), `storage/db.py:115-117` (`closing_lines` docstring)
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `closing_lines(con, sport_key, sharp_book)` still returns tuples of `(event_id, market, outcome, home_team, away_team, commence_time, closing_odds, closing_last_update)` — column 7 (`closing_captured_at` today) is renamed in meaning to `closing_last_update` and now holds `api_last_update`, not `captured_at`. Column order/count unchanged, so callers indexing by position (`analysis/report.py` `_C_CAPTURED`) still work positionally until Task 3 renames the constant.

- [ ] **Step 1: Write the failing test for divergence between `captured_at` and `api_last_update`**

Add to `tests/test_storage.py`, after the existing `_row` helper:

```python
def _row_stale(captured_at, api_last_update, book, odds, outcome="Team A"):
    row = _row(captured_at, book, odds, outcome)
    row["api_last_update"] = api_last_update
    return row


def test_closing_lines_selects_by_api_last_update_not_captured_at(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")

    rows = [
        # Sondeo temprano, pero es el precio realmente más reciente (api_last_update -6h).
        _row_stale(COMMENCE - timedelta(hours=6), COMMENCE - timedelta(hours=6), "pinnacle", 2.00),
        # Sondeo tardío (captured_at -1h) pero devuelve un precio viejo (api_last_update -8h):
        # bajo la lógica antigua (arg_max por captured_at) este ganaba por error.
        _row_stale(COMMENCE - timedelta(hours=1), COMMENCE - timedelta(hours=8), "pinnacle", 1.50),
    ]
    insert_snapshot_rows(con, rows)

    result = closing_lines(con, "soccer_fifa_world_cup", "pinnacle")

    assert len(result) == 1
    row = result[0]
    assert row[6] == 2.00  # closing_odds: gana el api_last_update más reciente (-6h), no el sondeo más tardío
    assert row[7] == COMMENCE - timedelta(hours=6)  # closing_last_update
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_storage.py::test_closing_lines_selects_by_api_last_update_not_captured_at -v`
Expected: FAIL — assertion `row[6] == 2.00` fails because current query returns `1.50` (the row with the latest `captured_at`).

- [ ] **Step 3: Fix `CLOSING_LINES_QUERY`**

In `storage/db.py`, replace:

```python
CLOSING_LINES_QUERY = """
SELECT event_id, market, outcome, home_team, away_team, commence_time,
       arg_max(odds, captured_at) AS closing_odds,
       max(captured_at)           AS closing_captured_at
FROM snapshots
WHERE sport_key = ? AND book = ? AND captured_at < commence_time
GROUP BY event_id, market, outcome, home_team, away_team, commence_time
"""
```

with:

```python
CLOSING_LINES_QUERY = """
SELECT event_id, market, outcome, home_team, away_team, commence_time,
       arg_max(odds, api_last_update) AS closing_odds,
       max(api_last_update)           AS closing_last_update
FROM snapshots
WHERE sport_key = ? AND book = ? AND api_last_update < commence_time
GROUP BY event_id, market, outcome, home_team, away_team, commence_time
"""
```

And update the `closing_lines` docstring:

```python
def closing_lines(con: duckdb.DuckDBPyConnection, sport_key: str, sharp_book: str) -> list[tuple]:
    """Última fila de sharp_book por api_last_update < commence_time (timestamp de validez
    del propio precio, no el instante de nuestro sondeo), por evento+outcome."""
    return con.execute(CLOSING_LINES_QUERY, [sport_key, sharp_book]).fetchall()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_storage.py -v`
Expected: all tests PASS, including the new one and the pre-existing `test_closing_lines_returns_last_pre_commence_sharp_row` (unaffected — its rows all have `api_last_update == captured_at`).

- [ ] **Step 5: Commit**

```bash
git add storage/db.py tests/test_storage.py
git commit -m "fix: select Pinnacle closing line by api_last_update, not poll instant"
```

---

### Task 2: Add `hours_before_commence` and rename closing-timestamp column in `clv_snapshots`

**Files:**
- Modify: `storage/db.py:55-81` (`CLV_SNAPSHOTS_SCHEMA`, `INSERT_CLV_QUERY`, `replace_clv_snapshots`)

**Interfaces:**
- Consumes: rows passed to `replace_clv_snapshots` must now include keys `pinnacle_closing_last_update` (renamed from `pinnacle_closing_captured_at`) and `hours_before_commence` (new) — produced by Task 3.
- Produces: `clv_snapshots` table with columns `pinnacle_closing_last_update TIMESTAMP NOT NULL` (renamed) and `hours_before_commence DOUBLE NOT NULL` (new), inserted via `replace_clv_snapshots(con, rows)`.

- [ ] **Step 1: Update schema and insert query**

In `storage/db.py`, replace `CLV_SNAPSHOTS_SCHEMA`:

```python
CLV_SNAPSHOTS_SCHEMA = """
CREATE OR REPLACE TABLE clv_snapshots (
    sport_key                    VARCHAR NOT NULL,
    event_id                     VARCHAR NOT NULL,
    home_team                    VARCHAR NOT NULL,
    away_team                    VARCHAR NOT NULL,
    market                       VARCHAR NOT NULL,
    outcome                      VARCHAR NOT NULL,
    soft_book                    VARCHAR NOT NULL,
    commence_time                TIMESTAMP NOT NULL,
    captured_at                  TIMESTAMP NOT NULL,
    hours_to_commence            DOUBLE NOT NULL,
    soft_odds                    DOUBLE NOT NULL,
    pinnacle_closing_odds        DOUBLE NOT NULL,
    pinnacle_closing_last_update TIMESTAMP NOT NULL,
    hours_before_commence        DOUBLE NOT NULL,
    pinnacle_fair_prob           DOUBLE NOT NULL,
    clv                          DOUBLE NOT NULL
)
"""
```

Replace `INSERT_CLV_QUERY`:

```python
INSERT_CLV_QUERY = """
INSERT INTO clv_snapshots
    (sport_key, event_id, home_team, away_team, market, outcome, soft_book,
     commence_time, captured_at, hours_to_commence, soft_odds,
     pinnacle_closing_odds, pinnacle_closing_last_update, hours_before_commence,
     pinnacle_fair_prob, clv)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
```

Replace the parameter list inside `replace_clv_snapshots`:

```python
def replace_clv_snapshots(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> int:
    """Reconstruye la tabla clv_snapshots entera (full refresh) e inserta rows. Idempotente."""
    con.execute(CLV_SNAPSHOTS_SCHEMA)
    for row in rows:
        con.execute(
            INSERT_CLV_QUERY,
            [
                row["sport_key"],
                row["event_id"],
                row["home_team"],
                row["away_team"],
                row["market"],
                row["outcome"],
                row["soft_book"],
                row["commence_time"],
                row["captured_at"],
                row["hours_to_commence"],
                row["soft_odds"],
                row["pinnacle_closing_odds"],
                row["pinnacle_closing_last_update"],
                row["hours_before_commence"],
                row["pinnacle_fair_prob"],
                row["clv"],
            ],
        )
    return len(rows)
```

- [ ] **Step 2: Verify no test currently depends on the old column name**

Run: `grep -rn "pinnacle_closing_captured_at" tests/ analysis/ storage/`
Expected: no matches in `tests/` (only `analysis/report.py`, fixed in Task 3). If `analysis/report.py` still has old references, that's expected — Task 3 fixes it next; `replace_clv_snapshots` is not called by any test directly today (verified: no test imports it), so this task alone is safe to commit before Task 3.

- [ ] **Step 3: Commit**

```bash
git add storage/db.py
git commit -m "feat: add hours_before_commence audit column, rename closing timestamp to last_update"
```

---

### Task 3: Thread `api_last_update`-based closing through `analysis/report.py`, add `hours_before_commence`, surface events without closing

**Files:**
- Modify: `analysis/report.py` (whole file — small, shown in full below where changed)

**Interfaces:**
- Consumes: `closing_lines()` tuples with column 7 now meaning `closing_last_update` (Task 1); `replace_clv_snapshots` expecting `pinnacle_closing_last_update` and `hours_before_commence` keys (Task 2).
- Produces: `build_target_rows(con, target) -> tuple[list[dict], int, list[str]]` — **signature change**: third element `events_without_closing: list[str]` (sorted, deduplicated `event_id`s present in soft snapshots but absent from `fair_by_market`). `build_clv_rows` unchanged in signature (`list[tuple], dict, str -> tuple[list[dict], int]`) but each row dict gains `hours_before_commence` and renames `pinnacle_closing_captured_at` → `pinnacle_closing_last_update`. `fair_probs_by_market` unchanged signature; its per-outcome dict renames key `closing_captured_at` → `closing_last_update`.

- [ ] **Step 1: Update `fair_probs_by_market` to use the renamed field**

In `analysis/report.py`, update the column index comment and the function body:

```python
# Índices de columna de closing_lines(): event_id, market, outcome, home, away,
# commence, closing_odds, closing_last_update.
_C_EVENT, _C_MARKET, _C_OUTCOME, _C_ODDS, _C_LAST_UPDATE = 0, 1, 2, 6, 7
```

```python
def fair_probs_by_market(closing_rows: list[tuple]) -> dict[tuple[str, str], dict]:
    """Reagrupa las filas de cierre por (event_id, market), devig-a cada mercado completo
    y devuelve por outcome su fair_prob, closing_odds y closing_last_update.

    Función pura (sin DB): {(event_id, market): {outcome: {"fair_prob", "closing_odds",
    "closing_last_update"}}}.
    """
    odds_by_market: dict[tuple[str, str], dict[str, float]] = {}
    meta_by_market: dict[tuple[str, str], dict[str, tuple]] = {}
    for row in closing_rows:
        key = (row[_C_EVENT], row[_C_MARKET])
        odds_by_market.setdefault(key, {})[row[_C_OUTCOME]] = row[_C_ODDS]
        meta_by_market.setdefault(key, {})[row[_C_OUTCOME]] = row[_C_LAST_UPDATE]

    result: dict[tuple[str, str], dict] = {}
    for key, prices in odds_by_market.items():
        fair = devig(prices)  # normaliza sobre los outcomes presentes de ese mercado
        result[key] = {
            outcome: {
                "fair_prob": fair[outcome],
                "closing_odds": prices[outcome],
                "closing_last_update": meta_by_market[key][outcome],
            }
            for outcome in prices
        }
    return result
```

- [ ] **Step 2: Update `build_clv_rows` to compute `hours_before_commence` and rename the output key**

```python
def build_clv_rows(
    soft_rows: list[tuple],
    fair_by_market: dict[tuple[str, str], dict],
    sport_key: str,
) -> tuple[list[dict], int]:
    """Función pura: por cada snapshot soft, calcula su CLV contra el cierre fair de
    Pinnacle. Devuelve (filas, nº descartadas por no tener cierre para ese outcome).
    """
    rows: list[dict] = []
    skipped = 0
    for s in soft_rows:
        market_fair = fair_by_market.get((s[_S_EVENT], s[_S_MARKET]))
        outcome_fair = market_fair.get(s[_S_OUTCOME]) if market_fair else None
        if outcome_fair is None:
            skipped += 1
            continue

        commence, captured, soft_odds = s[_S_COMMENCE], s[_S_CAPTURED], s[_S_ODDS]
        hours_to_commence = (commence - captured).total_seconds() / 3600
        closing_last_update = outcome_fair["closing_last_update"]
        hours_before_commence = (commence - closing_last_update).total_seconds() / 3600
        fair_prob = outcome_fair["fair_prob"]
        rows.append(
            {
                "sport_key": sport_key,
                "event_id": s[_S_EVENT],
                "home_team": s[_S_HOME],
                "away_team": s[_S_AWAY],
                "market": s[_S_MARKET],
                "outcome": s[_S_OUTCOME],
                "soft_book": s[_S_BOOK],
                "commence_time": commence,
                "captured_at": captured,
                "hours_to_commence": hours_to_commence,
                "soft_odds": soft_odds,
                "pinnacle_closing_odds": outcome_fair["closing_odds"],
                "pinnacle_closing_last_update": closing_last_update,
                "hours_before_commence": hours_before_commence,
                "pinnacle_fair_prob": fair_prob,
                "clv": clv(soft_odds, fair_prob),
            }
        )
    return rows, skipped
```

- [ ] **Step 3: Update `build_target_rows` to also return events without any closing line**

```python
def build_target_rows(con, target: Target) -> tuple[list[dict], int, list[str]]:
    """Orquesta un target: cierre sharp -> devig -> une con snapshots soft -> filas CLV.

    El tercer elemento devuelto es la lista (ordenada, sin duplicados) de event_id que
    tienen snapshots soft pero ningún cierre Pinnacle pre-commence -- R13: deben quedar
    visibles, no solo contados.
    """
    fair_by_market = fair_probs_by_market(
        closing_lines(con, target.sport_key, target.sharp_book)
    )
    soft_rows = soft_snapshots(con, target.sport_key, target.soft_books)
    rows, skipped = build_clv_rows(soft_rows, fair_by_market, target.sport_key)
    events_without_closing = sorted(
        {s[_S_EVENT] for s in soft_rows if (s[_S_EVENT], s[_S_MARKET]) not in fair_by_market}
    )
    return rows, skipped, events_without_closing
```

- [ ] **Step 4: Update `main()` to log the event list**

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", help="Procesar solo este target (por nombre), para debug.")
    args = parser.parse_args(argv)

    load_dotenv()
    config: AppConfig = load_config()

    targets = config.active_targets()
    if args.target:
        targets = [t for t in targets if t.name == args.target]
        if not targets:
            logger.error("target %s no encontrado o inactivo en config.yaml", args.target)
            return 1

    con = get_connection(config.db_path)

    all_rows: list[dict] = []
    total_skipped = 0
    all_events_without_closing: list[str] = []
    for target in targets:
        rows, skipped, events_without_closing = build_target_rows(con, target)
        total_skipped += skipped
        all_rows.extend(rows)
        all_events_without_closing.extend(events_without_closing)
        logger.info(
            "target=%s filas_clv=%d descartadas_sin_cierre=%d eventos_sin_cierre=%s",
            target.name,
            len(rows),
            skipped,
            events_without_closing,
        )

    inserted = replace_clv_snapshots(con, all_rows)
    con.close()
    logger.info(
        "clv_snapshots reconstruida: %d filas totales, %d descartadas por falta de cierre, "
        "%d eventos sin ningún cierre válido: %s",
        inserted,
        total_skipped,
        len(all_events_without_closing),
        all_events_without_closing,
    )
    return 0
```

- [ ] **Step 5: Commit**

```bash
git add analysis/report.py
git commit -m "feat: compute hours_before_commence and log events without a valid closing line"
```

---

### Task 4: Update `tests/test_report.py` for the new 3-tuple return and new fields

**Files:**
- Modify: `tests/test_report.py`

**Interfaces:**
- Consumes: `build_target_rows(con, target) -> tuple[list[dict], int, list[str]]` from Task 3.

- [ ] **Step 1: Write the updated test file**

Replace the full contents of `tests/test_report.py`:

```python
from datetime import datetime, timedelta

import pytest

from analysis.report import build_target_rows
from config import Target
from storage.db import get_connection, insert_snapshot_rows

COMMENCE = datetime(2026, 7, 10, 20, 0, 0)

TARGET = Target(
    name="test",
    active=True,
    sport_key="soccer_fifa_world_cup",
    markets=["h2h"],
    sharp_book="pinnacle",
    soft_books=["williamhill"],
    poll_interval_hours=3,
)


def _row(captured_at, book, odds, outcome="Team A", api_last_update=None):
    return {
        "captured_at": captured_at,
        "sport_key": "soccer_fifa_world_cup",
        "event_id": "evt1",
        "commence_time": COMMENCE,
        "home_team": "Team A",
        "away_team": "Team B",
        "book": book,
        "market": "h2h",
        "outcome": outcome,
        "odds": odds,
        "api_last_update": api_last_update if api_last_update is not None else captured_at,
    }


def _seed_two_outcome_market(con):
    """Cierre Pinnacle: Team A 1.80 / Team B 2.05 (overround conocido) + tres snapshots
    soft de Team A a distinta antelación, con el precio soft cayendo hacia el cierre.
    """
    rows = [
        # Cierre sharp: dos outcomes -> devig sobre mercado completo.
        _row(COMMENCE - timedelta(hours=1), "pinnacle", 1.80, "Team A"),
        _row(COMMENCE - timedelta(hours=1), "pinnacle", 2.05, "Team B"),
        # Snapshots soft (williamhill) de Team A: 7h/4h/1h antes, precio decreciente.
        _row(COMMENCE - timedelta(hours=7), "williamhill", 2.10, "Team A"),
        _row(COMMENCE - timedelta(hours=4), "williamhill", 1.95, "Team A"),
        _row(COMMENCE - timedelta(hours=1), "williamhill", 1.70, "Team A"),
    ]
    insert_snapshot_rows(con, rows)


def test_build_produces_one_row_per_soft_snapshot(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")
    _seed_two_outcome_market(con)

    rows, skipped, events_without_closing = build_target_rows(con, TARGET)

    assert len(rows) == 3  # tres snapshots soft, ninguno descartado
    assert skipped == 0
    assert events_without_closing == []


def test_hours_to_commence_computed_per_snapshot(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")
    _seed_two_outcome_market(con)

    rows, _, _ = build_target_rows(con, TARGET)
    hours = sorted(r["hours_to_commence"] for r in rows)

    assert hours == pytest.approx([1.0, 4.0, 7.0])


def test_hours_before_commence_reflects_pinnacle_last_update(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")
    _seed_two_outcome_market(con)  # cierre sharp con api_last_update = COMMENCE - 1h

    rows, _, _ = build_target_rows(con, TARGET)

    assert all(r["hours_before_commence"] == pytest.approx(1.0) for r in rows)
    assert all(r["pinnacle_closing_last_update"] == COMMENCE - timedelta(hours=1) for r in rows)


def test_clv_trajectory_decreases_toward_close(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")
    _seed_two_outcome_market(con)

    rows, _, _ = build_target_rows(con, TARGET)
    by_hours = {r["hours_to_commence"]: r["clv"] for r in rows}

    # Precio soft cae hacia el cierre -> CLV cae. Benchmark (fair Pinnacle) es fijo.
    assert by_hours[7.0] > by_hours[4.0] > by_hours[1.0]
    # Precio soft alto (2.10) bate el fair de cierre; el bajo (1.70) no.
    assert by_hours[7.0] > 0
    assert by_hours[1.0] < 0


def test_benchmark_is_fixed_closing_not_per_snapshot(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")
    _seed_two_outcome_market(con)

    rows, _, _ = build_target_rows(con, TARGET)

    # El fair de Pinnacle es el mismo en todas las filas (cierre fijo por event+market).
    fair_probs = {r["pinnacle_fair_prob"] for r in rows}
    assert len(fair_probs) == 1


def test_soft_snapshot_without_pinnacle_closing_is_skipped(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")
    # Soft para un outcome (Team B) que NO tiene cierre de Pinnacle -> se descarta.
    insert_snapshot_rows(
        con,
        [
            _row(COMMENCE - timedelta(hours=1), "pinnacle", 1.80, "Team A"),
            _row(COMMENCE - timedelta(hours=1), "pinnacle", 2.05, "Team B"),
            _row(COMMENCE - timedelta(hours=2), "williamhill", 3.00, "Team C"),
        ],
    )

    rows, skipped, events_without_closing = build_target_rows(con, TARGET)

    assert rows == []
    assert skipped == 1
    # El evento SÍ tiene cierre para el mercado (Team A/B) -- el outcome huérfano (Team C)
    # es un caso distinto de "evento sin cierre" y no debe aparecer en esta lista.
    assert events_without_closing == []


def test_event_with_no_pinnacle_closing_at_all_is_listed(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")
    # Ningún snapshot de pinnacle para este evento -- ninguna fila del mercado tiene cierre.
    insert_snapshot_rows(
        con,
        [
            _row(COMMENCE - timedelta(hours=2), "williamhill", 2.10, "Team A"),
        ],
    )

    rows, skipped, events_without_closing = build_target_rows(con, TARGET)

    assert rows == []
    assert skipped == 1
    assert events_without_closing == ["evt1"]


def test_post_commence_soft_snapshots_excluded(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")
    insert_snapshot_rows(
        con,
        [
            _row(COMMENCE - timedelta(hours=1), "pinnacle", 1.80, "Team A"),
            _row(COMMENCE - timedelta(hours=1), "pinnacle", 2.05, "Team B"),
            _row(COMMENCE - timedelta(hours=2), "williamhill", 2.10, "Team A"),
            _row(COMMENCE + timedelta(minutes=5), "williamhill", 1.50, "Team A"),  # post, excluir
        ],
    )

    rows, _, _ = build_target_rows(con, TARGET)

    assert len(rows) == 1
    assert rows[0]["hours_to_commence"] == pytest.approx(2.0)
```

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: all tests PASS (storage + report + clv + config + odds_api + capture).

- [ ] **Step 3: Commit**

```bash
git add tests/test_report.py
git commit -m "test: cover events-without-closing listing and hours_before_commence"
```

---

### Task 5: Verify against real captured data and confirm AC-A5

**Files:** none modified — verification only, against `data/odds.duckdb`.

**Interfaces:** none new.

- [ ] **Step 1: Confirm the DB is not locked by another process**

Run: `python3 -c "import duckdb; duckdb.connect('data/odds.duckdb').execute('select 1')"`
Expected: no `IOException` about a conflicting lock. If it fails, close whatever process holds it (e.g. a DB viewer/IDE) before continuing — do not delete or reset the file.

- [ ] **Step 2: Run the real pipeline**

Run: `uv run python -m analysis.report`
Expected: log line `clv_snapshots reconstruida: N filas totales, M descartadas por falta de cierre, K eventos sin ningún cierre válido: [...]`. Record the exact N/M/K and the event list.

- [ ] **Step 3: Inspect the France–Spain and Argentina–Egypt rows for `hours_before_commence`**

Run:
```bash
python3 -c "
import duckdb
con = duckdb.connect('data/odds.duckdb', read_only=True)
rows = con.execute('''
    SELECT home_team, away_team, soft_book, hours_before_commence, pinnacle_closing_last_update
    FROM clv_snapshots
    WHERE (home_team, away_team) IN (('France','Spain'), ('Argentina','Egypt'))
''').fetchall()
for r in rows:
    print(r)
"
```
Expected (per spec evidence): France–Spain rows show `hours_before_commence` ≈ 4.6, Argentina–Egypt rows show ≈ 22.3 — both still present in `clv_snapshots` (AC-A5: fix does not turn existing data into false "no closing" cases), with the staleness now visible instead of hidden.

- [ ] **Step 4: Report the real numbers to the user**

State in the response: exact row counts (N/M/K from Step 2), the two events' actual `hours_before_commence` values from Step 3, and whether any event newly appeared in the "sin cierre" list. This is the real-output proof required before considering the fix done (CLAUDE.md "Testing").

No commit for this task — it's verification only, nothing changes in the repo.

---

## Self-Review Notes

- **Spec coverage:** AC-A1 → Task 1. AC-A2 → Task 2 + Task 3 Step 2. AC-A3 → Task 3 Step 3/4 + Task 4's `test_event_with_no_pinnacle_closing_at_all_is_listed`. AC-A4 → Task 1 Step 1, Task 4 Step 1. AC-A5 → Task 5.
- **Type consistency:** `build_target_rows` 3-tuple return is consistent across Task 3 (producer) and Task 4 (consumer/tests). `closing_last_update` / `pinnacle_closing_last_update` naming consistent across Task 1 (query alias), Task 2 (schema/insert), Task 3 (report.py dict key).
- **No placeholders:** every step has literal code, exact commands, and expected output.
