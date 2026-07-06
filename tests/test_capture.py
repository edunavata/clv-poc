from datetime import UTC, datetime

import pytest

from client.odds_api import OddsApiClient, OddsApiError
from config import Target
from scheduler.capture import capture_target, parse_bookmaker_rows
from storage.db import get_connection

EVENT_FIXTURE = {
    "id": "event_id_123",
    "sport_key": "soccer_fifa_world_cup",
    "commence_time": "2026-07-10T20:00:00Z",
    "home_team": "Portugal",
    "away_team": "Spain",
    "bookmakers": [
        {
            "key": "pinnacle",
            "title": "Pinnacle",
            "last_update": "2026-07-06T10:00:00Z",  # nivel bookmaker, NO debe usarse
            "markets": [
                {
                    "key": "h2h",
                    "last_update": "2026-07-06T10:46:09Z",  # nivel mercado, SÍ debe usarse
                    "outcomes": [
                        {"name": "Portugal", "price": 2.50},
                        {"name": "Spain", "price": 1.52},
                    ],
                }
            ],
        }
    ],
}


def test_parse_bookmaker_rows_uses_market_level_last_update():
    captured_at = datetime(2026, 7, 6, 12, 0, 0)

    rows = parse_bookmaker_rows(EVENT_FIXTURE, "soccer_fifa_world_cup", captured_at)

    assert len(rows) == 2
    row = rows[0]
    assert row["event_id"] == "event_id_123"
    assert row["book"] == "pinnacle"
    assert row["market"] == "h2h"
    assert row["outcome"] == "Portugal"
    assert row["odds"] == 2.50
    assert row["api_last_update"] == datetime(2026, 7, 6, 10, 46, 9, tzinfo=UTC)


@pytest.fixture
def target():
    return Target(
        name="world_cup_2026",
        active=True,
        sport_key="soccer_fifa_world_cup",
        markets=["h2h"],
        sharp_book="pinnacle",
        soft_books=["williamhill"],
        poll_interval_hours=3,
    )


def test_capture_target_aborts_when_quota_margin_not_respected(target, tmp_path, monkeypatch):
    monkeypatch.setenv("ODDS_API_KEY", "test-key")
    client = OddsApiClient()
    monkeypatch.setattr(
        client, "get_usage", lambda: {"remaining": "10", "used": "490", "last": "0"}
    )
    con = get_connection(tmp_path / "odds.duckdb")

    result = capture_target(
        client, con, target, min_remaining_credits=20, captured_at=datetime.now(UTC)
    )

    assert result.ok is False
    assert "cuota insuficiente" in result.reason


def test_capture_target_isolates_api_failure(target, tmp_path, monkeypatch):
    monkeypatch.setenv("ODDS_API_KEY", "test-key")
    client = OddsApiClient()
    monkeypatch.setattr(
        client, "get_usage", lambda: {"remaining": "498", "used": "2", "last": "0"}
    )

    def raise_error(*args, **kwargs):
        if kwargs.get("dry_run") is False:
            raise OddsApiError("simulated network failure")
        return {"dry_run": True, "estimated_cost": 1, "url": "", "params": {}}

    monkeypatch.setattr(client, "get_odds", raise_error)
    con = get_connection(tmp_path / "odds.duckdb")

    result = capture_target(
        client, con, target, min_remaining_credits=20, captured_at=datetime.now(UTC)
    )

    assert result.ok is False
    assert "simulated network failure" in result.reason
