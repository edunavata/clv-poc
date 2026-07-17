"""Persistencia point-in-time de cuotas: la tabla snapshots nunca sobrescribe, solo inserta.

Ver Tarea 3 (esquema) y Tarea 7 (lógica de línea de cierre) del roadmap de Edu.
"""

from pathlib import Path

import duckdb

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    captured_at     TIMESTAMP NOT NULL,
    sport_key       VARCHAR NOT NULL,
    event_id        VARCHAR NOT NULL,
    commence_time   TIMESTAMP NOT NULL,
    home_team       VARCHAR NOT NULL,
    away_team       VARCHAR NOT NULL,
    book            VARCHAR NOT NULL,
    market          VARCHAR NOT NULL,
    outcome         VARCHAR NOT NULL,
    odds            DOUBLE NOT NULL,
    api_last_update TIMESTAMP NOT NULL
)
"""

# Los partidos se aplazan: la API actualiza commence_time y cada snapshot guarda el
# valor vigente en su captura. El commence canónico de un evento es el de su captura
# más reciente (cualquier book) -- usar el de cada fila mezclaría kickoffs viejos y
# haría pasar por válido un "cierre" sondeado mucho antes del kickoff real.
LATEST_COMMENCE_CTE = """
WITH latest_commence AS (
    SELECT event_id, arg_max(commence_time, captured_at) AS commence_time
    FROM snapshots
    WHERE sport_key = ?
    GROUP BY event_id
)
"""

CLOSING_LINES_QUERY = (
    LATEST_COMMENCE_CTE
    + """
SELECT s.event_id, s.market, s.outcome, s.home_team, s.away_team, l.commence_time,
       arg_max(s.odds, s.api_last_update)        AS closing_odds,
       max(s.api_last_update)                    AS closing_last_update,
       arg_max(s.captured_at, s.api_last_update) AS closing_captured_at
FROM snapshots s JOIN latest_commence l USING (event_id)
WHERE s.sport_key = ? AND s.book = ? AND s.api_last_update < l.commence_time
GROUP BY s.event_id, s.market, s.outcome, s.home_team, s.away_team, l.commence_time
"""
)

INSERT_QUERY = """
INSERT INTO snapshots
    (captured_at, sport_key, event_id, commence_time, home_team, away_team,
     book, market, outcome, odds, api_last_update)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# Todos los snapshots pre-commence de las soft books de un target. A diferencia de
# closing_lines NO colapsa a la última fila: devuelve cada snapshot, porque el análisis
# de CLV es por-snapshot (queremos ver la trayectoria según se acerca el cierre).
# El placeholder de books se expande en Python según cuántas soft books haya.
# Mismo commence canónico que closing_lines (ver LATEST_COMMENCE_CTE).
SOFT_SNAPSHOTS_QUERY = (
    LATEST_COMMENCE_CTE
    + """
SELECT s.event_id, s.market, s.outcome, s.home_team, s.away_team, l.commence_time,
       s.book, s.captured_at, s.odds
FROM snapshots s JOIN latest_commence l USING (event_id)
WHERE s.sport_key = ? AND s.captured_at < l.commence_time AND s.book IN ({books})
"""
)

# Mart derivado: cada run regenera los sport_keys que procesa (delete + insert por
# deporte). No es append-only como snapshots -- es una vista materializada del cálculo
# de CLV, siempre regenerable.
CLV_SNAPSHOTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS clv_snapshots (
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
    clv                          DOUBLE,
    is_valid_closing_benchmark   BOOLEAN NOT NULL,
    snapshot_role                VARCHAR NOT NULL
)
"""

INSERT_CLV_QUERY = """
INSERT INTO clv_snapshots
    (sport_key, event_id, home_team, away_team, market, outcome, soft_book,
     commence_time, captured_at, hours_to_commence, soft_odds,
     pinnacle_closing_odds, pinnacle_closing_last_update, hours_before_commence,
     pinnacle_fair_prob, clv, is_valid_closing_benchmark, snapshot_role)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def get_connection(db_path: str | Path, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Abre (o crea) la base DuckDB en db_path y aplica el esquema (idempotente).

    read_only=True abre sin aplicar SCHEMA (requiere escritura) y permite lectura
    concurrente con el daemon, que abre/cierra su conexión por cada poll en vez de
    mantenerla abierta.
    """
    db_path = Path(db_path)
    if read_only:
        return duckdb.connect(str(db_path), read_only=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(SCHEMA)
    return con


def insert_snapshot_rows(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> int:
    """INSERT-only: nunca actualiza filas existentes, cada llamada solo añade."""
    for row in rows:
        con.execute(
            INSERT_QUERY,
            [
                row["captured_at"],
                row["sport_key"],
                row["event_id"],
                row["commence_time"],
                row["home_team"],
                row["away_team"],
                row["book"],
                row["market"],
                row["outcome"],
                row["odds"],
                row["api_last_update"],
            ],
        )
    return len(rows)


def closing_lines(con: duckdb.DuckDBPyConnection, sport_key: str, sharp_book: str) -> list[tuple]:
    """Última fila de sharp_book por api_last_update < commence_time (timestamp de validez
    del propio precio, no el instante de nuestro sondeo), por evento+outcome."""
    return con.execute(CLOSING_LINES_QUERY, [sport_key, sport_key, sharp_book]).fetchall()


def soft_snapshots(
    con: duckdb.DuckDBPyConnection, sport_key: str, soft_books: list[str]
) -> list[tuple]:
    """Todos los snapshots pre-commence de las soft books dadas (sin colapsar). Vacío si no hay books."""
    if not soft_books:
        return []
    placeholders = ", ".join("?" for _ in soft_books)
    query = SOFT_SNAPSHOTS_QUERY.format(books=placeholders)
    return con.execute(query, [sport_key, sport_key, *soft_books]).fetchall()


def replace_clv_snapshots(
    con: duckdb.DuckDBPyConnection, rows: list[dict], sport_keys: list[str]
) -> int:
    """Regenera clv_snapshots solo para sport_keys (delete + insert) e inserta rows.

    Idempotente por deporte: un run con --target no borra los sport_keys de otros
    targets ya materializados.
    """
    con.execute(CLV_SNAPSHOTS_SCHEMA)
    if sport_keys:
        placeholders = ", ".join("?" for _ in sport_keys)
        con.execute(f"DELETE FROM clv_snapshots WHERE sport_key IN ({placeholders})", sport_keys)
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
                row["is_valid_closing_benchmark"],
                row["snapshot_role"],
            ],
        )
    return len(rows)
