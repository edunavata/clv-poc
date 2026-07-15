"""Consultas de solo lectura sobre data/odds.duckdb para el dashboard.

Funciones puras: reciben una conexión ya abierta (read_only) y devuelven filas
planas, igual que storage/db.py. Sin lógica de presentación aquí.
"""

import duckdb

CLV_BY_SOFT_BOOK_QUERY = """
    SELECT soft_book, count(*) AS n, avg(clv) AS avg_clv, min(clv) AS min_clv, max(clv) AS max_clv
    FROM clv_snapshots
    WHERE is_valid_closing_benchmark
    GROUP BY soft_book
    ORDER BY soft_book
"""

EVENTS_QUERY = """
    SELECT DISTINCT event_id, home_team, away_team, commence_time
    FROM clv_snapshots
    ORDER BY commence_time DESC
"""

TRAJECTORY_QUERY = """
    SELECT soft_book, hours_to_commence, soft_odds, pinnacle_closing_odds, snapshot_role, captured_at
    FROM clv_snapshots
    WHERE event_id = ?
    ORDER BY hours_to_commence DESC
"""

CAPTURE_HEALTH_QUERY = """
    SELECT date_trunc('day', captured_at) AS day, sport_key, count(*) AS n
    FROM snapshots
    GROUP BY 1, 2
    ORDER BY 1
"""

RAW_CLV_SNAPSHOTS_QUERY = "SELECT * FROM clv_snapshots ORDER BY captured_at DESC"


def clv_by_soft_book(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """CLV medio por soft book, solo sobre benchmarks de cierre válidos
    (is_valid_closing_benchmark) — es la métrica go/no-go del proyecto."""
    return con.execute(CLV_BY_SOFT_BOOK_QUERY).fetchall()


def events(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """Eventos distintos presentes en clv_snapshots, más recientes primero."""
    return con.execute(EVENTS_QUERY).fetchall()


def trajectory_for_event(con: duckdb.DuckDBPyConnection, event_id: str) -> list[tuple]:
    """Todas las filas de clv_snapshots de un evento, para graficar la
    trayectoria soft vs pinnacle según se acerca el cierre."""
    return con.execute(TRAJECTORY_QUERY, [event_id]).fetchall()


def capture_health(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """Filas capturadas en snapshots por día y target (sport_key), sanity
    check de que el daemon sigue capturando."""
    return con.execute(CAPTURE_HEALTH_QUERY).fetchall()


def raw_clv_snapshots(con: duckdb.DuckDBPyConnection):
    """clv_snapshots completo como DataFrame, para la tabla filtrable del dashboard."""
    return con.execute(RAW_CLV_SNAPSHOTS_QUERY).fetchdf()
