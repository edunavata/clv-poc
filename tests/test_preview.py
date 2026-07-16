from datetime import UTC, datetime, timedelta

from config import AppConfig, Target
from scheduler.preview import _event_label, build_schedule_rows


class FakeClient:
    """Cliente inyectable: eventos por sport_key o lanza para simular /events caído."""

    def __init__(self, events_by_sport=None, fail_sports=()):
        self.events_by_sport = events_by_sport or {}
        self.fail_sports = set(fail_sports)

    def get_events(self, sport_key):
        if sport_key in self.fail_sports:
            raise RuntimeError("API down")
        return self.events_by_sport.get(sport_key, [])


def _target(name, sport_key):
    return Target(
        name=name,
        active=True,
        sport_key=sport_key,
        markets=["h2h"],
        sharp_book="pinnacle",
        soft_books=["williamhill"],
        poll_interval_hours=3,
    )


def _config(targets):
    return AppConfig(db_path=":memory:", min_remaining_credits=50, targets=targets)


def _event(event_id, commence, home=None, away=None):
    ev = {"id": event_id, "commence_time": commence.isoformat().replace("+00:00", "Z")}
    if home:
        ev["home_team"] = home
    if away:
        ev["away_team"] = away
    return ev


def test_rows_sorted_ascending_by_run_at():
    now = datetime.now(UTC)
    config = _config([_target("wc", "soccer_fifa_world_cup")])
    events = [_event("a", now + timedelta(hours=3)), _event("b", now + timedelta(hours=8))]
    client = FakeClient(events_by_sport={"soccer_fifa_world_cup": events})

    rows = build_schedule_rows(client, config, now=now)

    assert rows
    times = [r["run_at"] for r in rows]
    assert times == sorted(times)


def test_row_fields_and_roles():
    now = datetime.now(UTC)
    config = _config([_target("wc", "soccer_fifa_world_cup")])
    commence = now + timedelta(hours=50)  # lejos: genera cierre + trayectoria
    client = FakeClient(
        events_by_sport={"soccer_fifa_world_cup": [_event("a", commence, "USA", "MEX")]}
    )

    rows = build_schedule_rows(client, config, now=now)

    roles = {r["role"] for r in rows}
    assert "cierre" in roles
    assert "trayectoria" in roles
    for r in rows:
        assert r["target"] == "wc"
        assert r["minutes_until"] >= 0
        assert isinstance(r["is_closing"], bool)


def test_closing_desc_uses_team_names():
    now = datetime.now(UTC)
    config = _config([_target("wc", "soccer_fifa_world_cup")])
    commence = now + timedelta(hours=3)
    client = FakeClient(
        events_by_sport={"soccer_fifa_world_cup": [_event("a", commence, "USA", "MEX")]}
    )

    rows = build_schedule_rows(client, config, now=now)
    closing = [r for r in rows if r["is_closing"]]

    assert closing
    assert any("USA vs MEX" in r["events_desc"] for r in closing)


def test_trajectory_desc_is_whole_board():
    now = datetime.now(UTC)
    config = _config([_target("wc", "soccer_fifa_world_cup")])
    events = [_event(f"e{i}", now + timedelta(hours=h)) for i, h in enumerate([20, 40, 60])]
    client = FakeClient(events_by_sport={"soccer_fifa_world_cup": events})

    rows = build_schedule_rows(client, config, now=now)
    traj = [r for r in rows if not r["is_closing"]]

    assert traj
    assert all("todo el tablero" in r["events_desc"] for r in traj)


def test_failed_target_skipped_others_survive():
    now = datetime.now(UTC)
    good = _target("good", "sport_good")
    bad = _target("bad", "sport_bad")
    config = _config([good, bad])
    client = FakeClient(
        events_by_sport={"sport_good": [_event("a", now + timedelta(hours=3))]},
        fail_sports=["sport_bad"],
    )

    rows = build_schedule_rows(client, config, now=now)

    assert rows
    assert all(r["target"] == "good" for r in rows)


def test_no_events_returns_empty():
    now = datetime.now(UTC)
    config = _config([_target("wc", "soccer_fifa_world_cup")])
    client = FakeClient(events_by_sport={"soccer_fifa_world_cup": []})
    assert build_schedule_rows(client, config, now=now) == []


def test_event_label_falls_back_to_id_without_teams():
    commence = datetime(2026, 7, 16, 21, 0, tzinfo=UTC)
    label = _event_label({"id": "evt1", "commence_time": commence.isoformat().replace("+00:00", "Z")})
    assert "evt1" in label
    assert "21:00" in label
