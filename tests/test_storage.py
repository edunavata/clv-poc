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
