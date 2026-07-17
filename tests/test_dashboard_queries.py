from datetime import datetime, timedelta

from dashboard.queries import (
    capture_polls,
    clv_stats_by_book,
    clv_stats_by_sport_book,
    clv_values,
    events_summary,
    kpi_summary,
    poll_timestamps,
    raw_snapshots,
    sample_growth,
    snapshot_growth,
)
from storage.db import get_connection, insert_snapshot_rows, replace_clv_snapshots

COMMENCE = datetime(2026, 7, 10, 20, 0, 0)


def _clv_row(
    sport_key="soccer_usa_mls",
    event_id="evt1",
    soft_book="bookA",
    clv=0.02,
    valid=True,
    captured_at=None,
    hours_to_commence=1.0,
):
    return {
        "sport_key": sport_key,
        "event_id": event_id,
        "home_team": "Team A",
        "away_team": "Team B",
        "market": "h2h",
        "outcome": "Team A",
        "soft_book": soft_book,
        "commence_time": COMMENCE,
        "captured_at": captured_at or (COMMENCE - timedelta(hours=hours_to_commence)),
        "hours_to_commence": hours_to_commence,
        "soft_odds": 2.10,
        "pinnacle_closing_odds": 1.95,
        "pinnacle_closing_last_update": COMMENCE - timedelta(minutes=5),
        "hours_before_commence": 0.1,
        "pinnacle_fair_prob": 0.49,
        "clv": clv if valid else None,
        "is_valid_closing_benchmark": valid,
        "snapshot_role": "trajectory",
    }


def _snapshot_row(captured_at, sport_key="soccer_usa_mls", book="pinnacle"):
    return {
        "captured_at": captured_at,
        "sport_key": sport_key,
        "event_id": "evt1",
        "commence_time": COMMENCE,
        "home_team": "Team A",
        "away_team": "Team B",
        "book": book,
        "market": "h2h",
        "outcome": "Team A",
        "odds": 1.90,
        "api_last_update": captured_at,
    }


def _seeded_con(tmp_path):
    con = get_connection(tmp_path / "odds.duckdb")
    replace_clv_snapshots(
        con,
        [
            _clv_row(clv=0.05, event_id="evt1"),
            _clv_row(clv=-0.03, event_id="evt2", soft_book="bookB"),
            _clv_row(valid=False, event_id="evt3"),  # clv NULL, no cuenta
            _clv_row(
                clv=0.01,
                sport_key="baseball_mlb",
                event_id="evt4",
                hours_to_commence=5.0,
                captured_at=COMMENCE - timedelta(days=1),
            ),
        ],
        ["soccer_usa_mls", "baseball_mlb"],
    )
    insert_snapshot_rows(
        con,
        [
            _snapshot_row(COMMENCE - timedelta(days=1)),
            _snapshot_row(COMMENCE - timedelta(hours=1)),
            _snapshot_row(COMMENCE - timedelta(hours=1), book="bookA"),  # mismo poll
        ],
    )
    return con


def test_kpi_summary(tmp_path):
    kpis = kpi_summary(_seeded_con(tmp_path))
    assert kpis["n_valid"] == 3
    assert round(kpis["avg_clv"], 4) == 0.01
    assert round(kpis["hit_rate"], 4) == round(2 / 3, 4)
    assert kpis["n_events"] == 3
    assert kpis["days_capturing"] == 2


def test_clv_stats_by_book_excludes_invalid(tmp_path):
    stats = clv_stats_by_book(_seeded_con(tmp_path)).set_index("soft_book")
    assert int(stats.loc["bookA", "n"]) == 2  # evt1 + evt4; evt3 inválido fuera
    assert stats.loc["bookA", "hit_rate"] == 1.0
    assert int(stats.loc["bookB", "n"]) == 1


def test_clv_values_only_valid_rows(tmp_path):
    values = clv_values(_seeded_con(tmp_path))
    assert len(values) == 3
    assert values["clv"].notna().all()


def test_clv_stats_by_sport_book_splits_sports(tmp_path):
    stats = clv_stats_by_sport_book(_seeded_con(tmp_path))
    assert set(stats["sport_key"]) == {"soccer_usa_mls", "baseball_mlb"}


def test_sample_growth_accumulates(tmp_path):
    growth = sample_growth(_seeded_con(tmp_path))
    assert list(growth["cumulative_n"]) == [1, 3]  # 1 el día previo, +2 el día del evento


def test_capture_polls_counts_distinct_minutes(tmp_path):
    polls = capture_polls(_seeded_con(tmp_path))
    by_day = polls.set_index("day")["polls"]
    # dos filas en el mismo minuto (pinnacle + bookA) = 1 poll
    assert list(by_day) == [1, 1]


def test_poll_timestamps_distinct(tmp_path):
    ts = poll_timestamps(_seeded_con(tmp_path))
    assert len(ts) == 2  # 3 filas raw, 2 instantes distintos


def test_events_summary_flags_valid_benchmark_first(tmp_path):
    summary = events_summary(_seeded_con(tmp_path))
    assert len(summary) == 4  # evt1..evt4
    # evt3 es el único sin benchmark válido: debe ir al final
    assert not summary.iloc[-1]["has_valid_benchmark"]
    assert summary.iloc[-1]["event_id"] == "evt3"
    assert summary["has_valid_benchmark"].iloc[:3].all()


def test_snapshot_growth_accumulates_per_sport(tmp_path):
    growth = snapshot_growth(_seeded_con(tmp_path))
    mls = growth[growth["sport_key"] == "soccer_usa_mls"]
    assert list(mls["cumulative_rows"]) == [1, 3]  # 1 el día previo, +2 el día del evento


def test_raw_snapshots_returns_all_rows(tmp_path):
    raw = raw_snapshots(_seeded_con(tmp_path))
    assert len(raw) == 3
    assert "odds" in raw.columns
