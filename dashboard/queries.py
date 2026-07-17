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
    SELECT market, outcome, soft_book, hours_to_commence, soft_odds,
           pinnacle_closing_odds, clv, snapshot_role, captured_at
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

# Un CLV es "válido" cuando el benchmark de cierre lo es (sondeo <= 0.25h antes del
# kickoff); clv es NULL exactamente en los benchmarks inválidos, así que basta filtrar
# por is_valid_closing_benchmark, pero se exige clv IS NOT NULL como cinturón.
_VALID_CLV = "is_valid_closing_benchmark AND clv IS NOT NULL"

KPI_CLV_QUERY = f"""
SELECT
    count(*) AS n_valid,
    avg(clv) AS avg_clv,
    avg((clv > 0)::INT) AS hit_rate,
    count(DISTINCT event_id) AS n_events
FROM clv_snapshots
WHERE {_VALID_CLV}
"""

KPI_CAPTURE_QUERY = """
SELECT
    count(DISTINCT date_trunc('day', captured_at)) AS days_capturing,
    min(captured_at) AS first_capture,
    max(captured_at) AS last_capture,
    count(DISTINCT event_id) AS events_seen
FROM snapshots
"""

CLV_STATS_BY_BOOK_QUERY = f"""
SELECT
    soft_book,
    count(*) AS n,
    avg(clv) AS avg_clv,
    stddev_samp(clv) AS std_clv,
    avg((clv > 0)::INT) AS hit_rate,
    median(clv) AS median_clv
FROM clv_snapshots
WHERE {_VALID_CLV}
GROUP BY soft_book
ORDER BY soft_book
"""

CLV_VALUES_QUERY = f"""
SELECT soft_book, sport_key, clv, hours_to_commence, captured_at, snapshot_role
FROM clv_snapshots
WHERE {_VALID_CLV}
ORDER BY captured_at
"""

CLV_STATS_BY_SPORT_BOOK_QUERY = f"""
SELECT
    sport_key,
    soft_book,
    count(*) AS n,
    avg(clv) AS avg_clv,
    stddev_samp(clv) AS std_clv,
    avg((clv > 0)::INT) AS hit_rate
FROM clv_snapshots
WHERE {_VALID_CLV}
GROUP BY sport_key, soft_book
ORDER BY sport_key, soft_book
"""

SAMPLE_GROWTH_QUERY = f"""
SELECT
    day,
    n_valid,
    sum(n_valid) OVER (ORDER BY day) AS cumulative_n
FROM (
    SELECT date_trunc('day', captured_at) AS day, count(*) AS n_valid
    FROM clv_snapshots
    WHERE {_VALID_CLV}
    GROUP BY 1
)
ORDER BY day
"""

CAPTURE_POLLS_QUERY = """
SELECT
    date_trunc('day', captured_at) AS day,
    sport_key,
    count(DISTINCT date_trunc('minute', captured_at)) AS polls,
    count(*) AS rows
FROM snapshots
GROUP BY 1, 2
ORDER BY 1, 2
"""

POLL_TIMESTAMPS_QUERY = """
SELECT DISTINCT sport_key, captured_at
FROM snapshots
ORDER BY sport_key, captured_at
"""


def clv_by_soft_book(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """CLV medio por soft book, solo sobre benchmarks de cierre válidos
    (is_valid_closing_benchmark) — es la métrica go/no-go del proyecto."""
    return con.execute(CLV_BY_SOFT_BOOK_QUERY).fetchall()


def events(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """Eventos distintos presentes en clv_snapshots, más recientes primero."""
    return con.execute(EVENTS_QUERY).fetchall()


def trajectory_for_event(con: duckdb.DuckDBPyConnection, event_id: str):
    """Todas las filas de clv_snapshots de un evento como DataFrame, para
    graficar la trayectoria soft vs pinnacle según se acerca el cierre.
    Incluye outcome: un chart por outcome, nunca mezclados (sus cuotas no
    son comparables ni promediables)."""
    return con.execute(TRAJECTORY_QUERY, [event_id]).fetchdf()


def capture_health(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """Filas capturadas en snapshots por día y target (sport_key), sanity
    check de que el daemon sigue capturando."""
    return con.execute(CAPTURE_HEALTH_QUERY).fetchall()


def raw_clv_snapshots(con: duckdb.DuckDBPyConnection):
    """clv_snapshots completo como DataFrame, para la tabla filtrable del dashboard."""
    return con.execute(RAW_CLV_SNAPSHOTS_QUERY).fetchdf()


def kpi_summary(con: duckdb.DuckDBPyConnection) -> dict:
    """KPIs de cabecera: muestra CLV válida (clv_snapshots) + cobertura de
    captura (snapshots). Un dict plano para la fila de st.metric."""
    clv = con.execute(KPI_CLV_QUERY).fetchdf().iloc[0]
    cap = con.execute(KPI_CAPTURE_QUERY).fetchdf().iloc[0]
    return {**clv.to_dict(), **cap.to_dict()}


def clv_stats_by_book(con: duckdb.DuckDBPyConnection):
    """Stats de CLV por soft book (n, media, std, hit-rate, mediana), solo
    benchmarks válidos — la base de la decisión go/no-go."""
    return con.execute(CLV_STATS_BY_BOOK_QUERY).fetchdf()


def clv_values(con: duckdb.DuckDBPyConnection):
    """CLVs válidos individuales; una sola query alimenta histograma, boxplot,
    bucketing por horizonte y evolución temporal."""
    return con.execute(CLV_VALUES_QUERY).fetchdf()


def clv_stats_by_sport_book(con: duckdb.DuckDBPyConnection):
    """Stats de CLV por deporte x soft book (el devig 3-way de fútbol y el
    2-way de MLB no son comparables sin separar)."""
    return con.execute(CLV_STATS_BY_SPORT_BOOK_QUERY).fetchdf()


def sample_growth(con: duckdb.DuckDBPyConnection):
    """N de CLVs válidos acumulado por día, para el tracker hacia N=100."""
    return con.execute(SAMPLE_GROWTH_QUERY).fetchdf()


def capture_polls(con: duckdb.DuckDBPyConnection):
    """Polls (aprox: minutos distintos con capturas) y filas por día x sport."""
    return con.execute(CAPTURE_POLLS_QUERY).fetchdf()


def poll_timestamps(con: duckdb.DuckDBPyConnection):
    """Timestamps de captura distintos por sport, para detectar gaps."""
    return con.execute(POLL_TIMESTAMPS_QUERY).fetchdf()
