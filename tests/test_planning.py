from datetime import UTC, datetime, timedelta

from scheduler.planning import (
    DISCOVERY_INTERVAL_HOURS,
    PlannedCapture,
    plan_capture_times,
    split_due_and_moved,
)


def _event(event_id, commence):
    return {"id": event_id, "commence_time": commence.isoformat().replace("+00:00", "Z")}


def _closing_times(planned):
    return {pc.run_at for pc in planned if pc.is_closing}


def _trajectory_times(planned):
    return sorted(pc.run_at for pc in planned if not pc.is_closing)


def test_returns_planned_capture_objects():
    now = datetime.now(UTC)
    events = [_event("a", now + timedelta(hours=3))]
    planned = plan_capture_times(events, now, poll_interval_hours=3)
    assert planned
    assert all(isinstance(pc, PlannedCapture) for pc in planned)


def test_closing_burst_at_minus_6_and_2():
    now = datetime.now(UTC)
    commence = now + timedelta(hours=3)
    planned = plan_capture_times([_event("a", commence)], now, poll_interval_hours=3)
    closing = _closing_times(planned)
    assert commence - timedelta(minutes=6) in closing
    assert commence - timedelta(minutes=2) in closing


def test_closing_burst_never_thinned_for_clustered_kickoffs():
    """Kickoffs a 3min: los 4 instantes de cierre deben sobrevivir el dedup."""
    now = datetime.now(UTC)
    base = now + timedelta(hours=3)
    events = [_event("a", base), _event("b", base + timedelta(minutes=3))]
    planned = plan_capture_times(events, now, poll_interval_hours=3)
    closing = _closing_times(planned)
    expected = {
        base - timedelta(minutes=6),
        base - timedelta(minutes=2),
        base + timedelta(minutes=3) - timedelta(minutes=6),
        base + timedelta(minutes=3) - timedelta(minutes=2),
    }
    assert expected <= closing


def test_closing_capture_attributes_its_events():
    now = datetime.now(UTC)
    commence = now + timedelta(hours=3)
    planned = plan_capture_times([_event("a", commence)], now, poll_interval_hours=3)
    closing = [pc for pc in planned if pc.is_closing]
    assert closing
    for pc in closing:
        assert pc.events
        assert pc.events[0]["id"] == "a"


def test_two_events_share_one_closing_instant():
    """Dos eventos con el mismo kickoff comparten el instante de cierre y ambos se atribuyen."""
    now = datetime.now(UTC)
    commence = now + timedelta(hours=3)
    events = [_event("a", commence), _event("b", commence)]
    planned = plan_capture_times(events, now, poll_interval_hours=3)
    shared = [pc for pc in planned if pc.is_closing and pc.run_at == commence - timedelta(minutes=6)]
    assert len(shared) == 1
    ids = {e["id"] for e in shared[0].events}
    assert ids == {"a", "b"}


def test_trajectory_events_empty():
    now = datetime.now(UTC)
    events = [_event("a", now + timedelta(hours=50))]
    planned = plan_capture_times(events, now, poll_interval_hours=3)
    traj = [pc for pc in planned if not pc.is_closing]
    assert traj
    assert all(pc.events == () for pc in traj)


def test_trajectory_cadence_matches_poll_interval():
    now = datetime.now(UTC)
    events = [_event("a", now + timedelta(hours=50))]
    planned = plan_capture_times(events, now, poll_interval_hours=3)
    traj = _trajectory_times(planned)
    assert len(traj) >= 2
    for a, b in zip(traj, traj[1:]):
        gap = (b - a).total_seconds() / 3600
        assert abs(gap - 3) < 0.01


def test_trajectory_count_independent_of_event_count():
    now = datetime.now(UTC)
    few = [_event(f"e{i}", now + timedelta(hours=h)) for i, h in enumerate([5, 15, 25])]
    many = [
        _event(f"e{i}", now + timedelta(hours=h))
        for i, h in enumerate([5, 15, 25, 35, 45, 55, 65, 75, 85, 95])
    ]
    count_few = len(_trajectory_times(plan_capture_times(few, now, poll_interval_hours=3)))
    count_many = len(_trajectory_times(plan_capture_times(many, now, poll_interval_hours=3)))
    assert count_few == count_many
    assert 0 < count_few <= 4


def test_trajectory_horizon_capped_by_discovery_interval():
    now = datetime.now(UTC)
    events = [_event("a", now + timedelta(hours=24 * 30))]  # evento a 30 días
    planned = plan_capture_times(events, now, poll_interval_hours=3)
    traj = _trajectory_times(planned)
    assert traj
    horizon = now + timedelta(hours=DISCOVERY_INTERVAL_HOURS)
    assert max(traj) < horizon


def test_no_events_returns_empty():
    now = datetime.now(UTC)
    assert plan_capture_times([], now, poll_interval_hours=3) == []


def test_past_closing_times_excluded():
    """Un kickoff tan próximo que -6/-2min ya pasó no genera cierre en el pasado."""
    now = datetime.now(UTC)
    commence = now + timedelta(minutes=1)  # -6 y -2 min ya son pasado
    planned = plan_capture_times([_event("a", commence)], now, poll_interval_hours=3)
    assert all(pc.run_at > now for pc in planned)


def test_results_sorted_ascending():
    now = datetime.now(UTC)
    events = [_event("a", now + timedelta(hours=3)), _event("b", now + timedelta(hours=8))]
    planned = plan_capture_times(events, now, poll_interval_hours=3)
    times = [pc.run_at for pc in planned]
    assert times == sorted(times)


class TestSplitDueAndMoved:
    NOW = datetime(2026, 7, 17, 4, 24, 0, tzinfo=UTC)

    def test_unchanged_commence_is_due(self):
        checks = [("evt1", "2026-07-17T04:30:00Z")]
        current = {"evt1": "2026-07-17T04:30:00Z"}
        due, moved = split_due_and_moved(checks, current, self.NOW)
        assert due == ["evt1"] and moved == []

    def test_postponed_to_future_is_moved(self):
        checks = [("evt1", "2026-07-17T04:30:00Z")]
        current = {"evt1": "2026-07-17T04:46:00Z"}
        due, moved = split_due_and_moved(checks, current, self.NOW)
        assert due == [] and moved == [("evt1", "2026-07-17T04:46:00Z")]

    def test_missing_event_is_due_fail_open(self):
        checks = [("evt1", "2026-07-17T04:30:00Z")]
        due, moved = split_due_and_moved(checks, {}, self.NOW)
        assert due == ["evt1"] and moved == []

    def test_moved_to_past_is_due_fail_open(self):
        # adelantado o ya empezado: capturar ahora es lo mejor disponible
        checks = [("evt1", "2026-07-17T04:30:00Z")]
        current = {"evt1": "2026-07-17T04:00:00Z"}
        due, moved = split_due_and_moved(checks, current, self.NOW)
        assert due == ["evt1"] and moved == []

    def test_mixed_burst(self):
        checks = [("evt1", "2026-07-17T04:30:00Z"), ("evt2", "2026-07-17T04:30:00Z")]
        current = {"evt1": "2026-07-17T04:30:00Z", "evt2": "2026-07-17T05:30:00Z"}
        due, moved = split_due_and_moved(checks, current, self.NOW)
        assert due == ["evt1"] and moved == [("evt2", "2026-07-17T05:30:00Z")]
