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

CLOSING_LINES_QUERY = """
SELECT event_id, market, outcome, home_team, away_team, commence_time,
       arg_max(odds, captured_at) AS closing_odds,
       max(captured_at)           AS closing_captured_at
FROM snapshots
WHERE sport_key = ? AND book = ? AND captured_at < commence_time
GROUP BY event_id, market, outcome, home_team, away_team, commence_time
"""

INSERT_QUERY = """
INSERT INTO snapshots
    (captured_at, sport_key, event_id, commence_time, home_team, away_team,
     book, market, outcome, odds, api_last_update)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def get_connection(db_path: str | Path) -> duckdb.DuckDBPyConnection:
    """Abre (o crea) la base DuckDB en db_path y aplica el esquema (idempotente)."""
    db_path = Path(db_path)
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
    """Tarea 7: última fila de sharp_book con captured_at < commence_time, por evento+outcome."""
    return con.execute(CLOSING_LINES_QUERY, [sport_key, sharp_book]).fetchall()
