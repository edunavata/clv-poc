from datetime import datetime, timedelta

from storage.db import closing_lines, get_connection, insert_snapshot_rows

COMMENCE = datetime(2026, 7, 10, 20, 0, 0)


def _row(captured_at, book, odds, outcome="Team A"):
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
        "api_last_update": captured_at,
    }


def _row_stale(captured_at, api_last_update, book, odds, outcome="Team A"):
    row = _row(captured_at, book, odds, outcome)
    row["api_last_update"] = api_last_update
    return row


def test_schema_creation_is_idempotent(tmp_path):
    db_path = tmp_path / "odds.duckdb"
    get_connection(db_path).close()
    con = get_connection(db_path)  # segunda vez, no debe fallar
    con.close()


def test_insert_and_round_trip(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")

    inserted = insert_snapshot_rows(con, [_row(COMMENCE - timedelta(hours=1), "pinnacle", 1.90)])

    assert inserted == 1
    assert con.execute("SELECT count(*) FROM snapshots").fetchone()[0] == 1


def test_closing_lines_returns_last_pre_commence_sharp_row(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")

    rows = [
        _row(COMMENCE - timedelta(hours=6), "pinnacle", 2.00),  # sharp, más antigua
        _row(COMMENCE - timedelta(hours=1), "pinnacle", 1.85),  # sharp, cierre real
        _row(COMMENCE + timedelta(minutes=5), "pinnacle", 1.50),  # post-commence, debe excluirse
        _row(COMMENCE - timedelta(hours=2), "williamhill", 2.10),  # soft, no es el sharp_book
    ]
    insert_snapshot_rows(con, rows)

    result = closing_lines(con, "soccer_fifa_world_cup", "pinnacle")

    assert len(result) == 1
    row = result[0]
    assert row[0] == "evt1"  # event_id
    assert row[6] == 1.85  # closing_odds: la última fila sharp pre-commence


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
    assert (
        row[6] == 2.00
    )  # closing_odds: gana el api_last_update más reciente (-6h), no el sondeo más tardío
    assert row[7] == COMMENCE - timedelta(hours=6)  # closing_last_update


def test_closing_lines_exposes_captured_at_of_winning_row(tmp_path):
    """La validez del benchmark (fuera de esta función) necesita saber CUÁNDO
    sondeamos nosotros, no solo cuándo Pinnacle actualizó su precio."""
    con = get_connection(tmp_path / "odds.duckdb")

    rows = [
        _row_stale(COMMENCE - timedelta(minutes=2), COMMENCE - timedelta(minutes=30), "pinnacle", 1.85),
    ]
    insert_snapshot_rows(con, rows)

    result = closing_lines(con, "soccer_fifa_world_cup", "pinnacle")

    assert len(result) == 1
    row = result[0]
    assert row[7] == COMMENCE - timedelta(minutes=30)  # closing_last_update (Pinnacle)
    assert row[8] == COMMENCE - timedelta(minutes=2)  # closing_captured_at (nuestro sondeo)


def test_closing_lines_uses_latest_commence_after_postponement(tmp_path):
    """Partido aplazado: la API actualiza commence_time y las capturas nuevas lo
    traen. El cierre debe evaluarse contra el ÚLTIMO kickoff conocido, no contra
    el que traía cada fila vieja."""
    con = get_connection(tmp_path / "odds.duckdb")
    new_commence = COMMENCE + timedelta(minutes=16)

    rows = [
        # ráfaga de cierre programada para el kickoff original
        _row(COMMENCE - timedelta(minutes=2), "pinnacle", 1.85),
        # captura posterior (cualquier book) ya con el kickoff aplazado
        {**_row(COMMENCE + timedelta(minutes=5), "williamhill", 1.90), "commence_time": new_commence},
    ]
    insert_snapshot_rows(con, rows)

    result = closing_lines(con, "soccer_fifa_world_cup", "pinnacle")

    assert len(result) == 1
    row = result[0]
    assert row[5] == new_commence  # commence canónico, no el de la fila del cierre
    assert row[8] == COMMENCE - timedelta(minutes=2)  # closing_captured_at intacto
    # la validez (en analysis/report.py) saldrá de new_commence - closing_captured_at
    # = 18 min > 15 min => benchmark inválido, como debe ser


def test_soft_snapshots_include_rows_between_old_and_new_commence(tmp_path):
    """Con el kickoff aplazado, una captura soft posterior al kickoff viejo pero
    anterior al nuevo sigue siendo pre-partido y debe contar."""
    from storage.db import soft_snapshots

    con = get_connection(tmp_path / "odds.duckdb")
    new_commence = COMMENCE + timedelta(hours=1)

    rows = [
        {**_row(COMMENCE + timedelta(minutes=10), "williamhill", 2.0), "commence_time": new_commence},
    ]
    insert_snapshot_rows(con, rows)

    result = soft_snapshots(con, "soccer_fifa_world_cup", ["williamhill"])
    assert len(result) == 1
    assert result[0][5] == new_commence
