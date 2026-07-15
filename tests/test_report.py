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
        # Cierre sharp: dos outcomes -> devig sobre mercado completo. Capturado a
        # 2min del pitido -- dentro del umbral de validez (<=15min).
        _row(COMMENCE - timedelta(minutes=2), "pinnacle", 1.80, "Team A"),
        _row(COMMENCE - timedelta(minutes=2), "pinnacle", 2.05, "Team B"),
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


def test_hours_before_commence_reflects_our_capture_of_the_close(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")
    _seed_two_outcome_market(con)  # cierre sharp sondeado a COMMENCE - 2min

    rows, _, _ = build_target_rows(con, TARGET)

    assert all(r["hours_before_commence"] == pytest.approx(2 / 60) for r in rows)
    assert all(r["pinnacle_closing_last_update"] == COMMENCE - timedelta(minutes=2) for r in rows)


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


def test_rancid_closing_benchmark_nullifies_clv(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")
    insert_snapshot_rows(
        con,
        [
            _row(COMMENCE - timedelta(hours=5), "pinnacle", 1.80, "Team A"),
            _row(COMMENCE - timedelta(hours=5), "pinnacle", 2.05, "Team B"),
            _row(COMMENCE - timedelta(hours=2), "williamhill", 2.10, "Team A"),
        ],
    )

    rows, _, _ = build_target_rows(con, TARGET)
    assert len(rows) == 1
    assert rows[0]["hours_before_commence"] == pytest.approx(5.0)
    assert rows[0]["is_valid_closing_benchmark"] is False
    assert rows[0]["clv"] is None


def _row_stale(captured_at, api_last_update, book, odds, outcome="Team A"):
    row = _row(captured_at, book, odds, outcome)
    row["api_last_update"] = api_last_update
    return row


def test_quiet_market_valid_if_our_capture_is_near_commence(tmp_path):
    """Eje correcto: validez se mide sobre CUÁNDO sondeamos (captured_at), no sobre
    cuándo Pinnacle actualizó su precio (api_last_update). Un mercado tranquilo
    (Pinnacle no mueve línea en 30min) capturado a 2min del pitido SIGUE siendo
    un cierre válido -- el precio no cambia, pero nuestro sondeo sí fue cerca."""
    con = get_connection(tmp_path / "odds.duckdb")
    insert_snapshot_rows(
        con,
        [
            _row_stale(
                COMMENCE - timedelta(minutes=2), COMMENCE - timedelta(minutes=30), "pinnacle", 1.80, "Team A"
            ),
            _row_stale(
                COMMENCE - timedelta(minutes=2), COMMENCE - timedelta(minutes=30), "pinnacle", 2.05, "Team B"
            ),
            _row(COMMENCE - timedelta(minutes=5), "williamhill", 2.10, "Team A"),
        ],
    )

    rows, _, _ = build_target_rows(con, TARGET)

    assert len(rows) == 1
    assert rows[0]["is_valid_closing_benchmark"] is True
    assert rows[0]["clv"] is not None


def test_capture_far_from_commence_invalid_even_with_matching_last_update(tmp_path):
    """Reproduce el bug real: Pinnacle sondeado a 78min del pitido, api_last_update
    coincide con nuestro captured_at (mismo instante, market en movimiento). El
    viejo eje (closing_last_update) lo marcaba válido por error; el nuevo eje
    (captured_at real) debe rechazarlo."""
    con = get_connection(tmp_path / "odds.duckdb")
    insert_snapshot_rows(
        con,
        [
            _row(COMMENCE - timedelta(minutes=78), "pinnacle", 1.80, "Team A"),
            _row(COMMENCE - timedelta(minutes=78), "pinnacle", 2.05, "Team B"),
            _row(COMMENCE - timedelta(minutes=80), "williamhill", 2.10, "Team A"),
        ],
    )

    rows, _, _ = build_target_rows(con, TARGET)

    assert len(rows) == 1
    assert rows[0]["is_valid_closing_benchmark"] is False
    assert rows[0]["clv"] is None


def test_validity_threshold_edge_at_15_minutes(tmp_path):
    """Clava el corte del umbral (report.py: <= 0.25h). 14min debe ser válido,
    16min no -- si un refactor desplaza el umbral, este test lo detecta."""
    con14 = get_connection(tmp_path / "at14.duckdb")
    insert_snapshot_rows(
        con14,
        [
            _row(COMMENCE - timedelta(minutes=14), "pinnacle", 1.80, "Team A"),
            _row(COMMENCE - timedelta(minutes=14), "pinnacle", 2.05, "Team B"),
            _row(COMMENCE - timedelta(minutes=14), "williamhill", 2.10, "Team A"),
        ],
    )
    rows14, _, _ = build_target_rows(con14, TARGET)
    assert rows14[0]["is_valid_closing_benchmark"] is True
    assert rows14[0]["clv"] is not None

    con16 = get_connection(tmp_path / "at16.duckdb")
    insert_snapshot_rows(
        con16,
        [
            _row(COMMENCE - timedelta(minutes=16), "pinnacle", 1.80, "Team A"),
            _row(COMMENCE - timedelta(minutes=16), "pinnacle", 2.05, "Team B"),
            _row(COMMENCE - timedelta(minutes=16), "williamhill", 2.10, "Team A"),
        ],
    )
    rows16, _, _ = build_target_rows(con16, TARGET)
    assert rows16[0]["is_valid_closing_benchmark"] is False
    assert rows16[0]["clv"] is None


def test_snapshot_role(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")
    insert_snapshot_rows(
        con,
        [
            _row(COMMENCE - timedelta(hours=1), "pinnacle", 1.80, "Team A"),
            _row(COMMENCE - timedelta(hours=1), "pinnacle", 2.05, "Team B"),
            _row(COMMENCE - timedelta(hours=5), "williamhill", 2.10, "Team A"),
            _row(COMMENCE - timedelta(minutes=10), "williamhill", 1.95, "Team A"),
        ],
    )
    rows, _, _ = build_target_rows(con, TARGET)
    assert len(rows) == 2
    r_traj = next(r for r in rows if r["hours_to_commence"] > 1.0)
    r_close = next(r for r in rows if r["hours_to_commence"] < 0.5)
    assert r_traj["snapshot_role"] == "trajectory"
    assert r_close["snapshot_role"] == "closing"
