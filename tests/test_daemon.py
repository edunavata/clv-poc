from datetime import UTC, datetime, timedelta

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from config import AppConfig, Target
from scheduler import daemon


def _noop():
    pass


class FakeClient:
    """Cliente inyectable: devuelve eventos por sport_key o lanza para simular /events caído."""

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


def _future_event(hours_ahead=3):
    commence = datetime.now(UTC) + timedelta(hours=hours_ahead)
    return {"id": "evt1", "commence_time": commence.isoformat().replace("+00:00", "Z")}


@pytest.fixture
def scheduler():
    sched = BackgroundScheduler(timezone=UTC)
    yield sched
    sched.shutdown(wait=False) if sched.running else None


def _capture_job_ids(sched, target_name):
    return [j.id for j in sched.get_jobs() if j.id.startswith(f"capture_{target_name}_")]


def test_discovery_failure_preserves_existing_agenda(scheduler):
    """Bug 1: un /events caído NO debe borrar la agenda ya programada del target."""
    target = _target("wc", "soccer_fifa_world_cup")
    config = _config([target])

    # Agenda previa ya programada (simula corrida anterior exitosa)
    run_at = datetime.now(UTC) + timedelta(hours=1)
    scheduler.add_job(_noop, trigger=DateTrigger(run_date=run_at), id="capture_wc_pre_0")

    client = FakeClient(fail_sports=["soccer_fifa_world_cup"])
    daemon.schedule_captures(scheduler, config, client=client)

    assert "capture_wc_pre_0" in _capture_job_ids(scheduler, "wc"), (
        "discovery caído borró la agenda existente"
    )


def test_successful_discovery_replaces_target_jobs(scheduler):
    """Discovery exitoso reprograma jobs del target (limpia los viejos, añade nuevos)."""
    target = _target("wc", "soccer_fifa_world_cup")
    config = _config([target])

    scheduler.add_job(_noop, trigger=DateTrigger(
        run_date=datetime.now(UTC) + timedelta(hours=1)), id="capture_wc_stale_0")

    client = FakeClient(events_by_sport={"soccer_fifa_world_cup": [_future_event()]})
    daemon.schedule_captures(scheduler, config, client=client)

    ids = _capture_job_ids(scheduler, "wc")
    assert "capture_wc_stale_0" not in ids, "job viejo no reemplazado"
    assert len(ids) > 0, "no reprogramó capturas tras discovery exitoso"


def test_capture_jobs_have_misfire_grace_time(scheduler):
    """Bug 2: default de APScheduler es 1s -- un job de cierre con leve retraso
    (hilo ocupado, sleep de sistema) se descartaría sin traza. Debe tener margen."""
    target = _target("wc", "soccer_fifa_world_cup")
    config = _config([target])
    client = FakeClient(events_by_sport={"soccer_fifa_world_cup": [_future_event()]})

    daemon.schedule_captures(scheduler, config, client=client)

    jobs = [j for j in scheduler.get_jobs() if j.id.startswith("capture_wc_")]
    assert jobs, "no se programó ningún job de captura"
    for job in jobs:
        assert job.misfire_grace_time is not None and job.misfire_grace_time >= 60, (
            f"job {job.id} sin margen de misfire suficiente: {job.misfire_grace_time}"
        )


def test_close_kickoffs_do_not_drop_closing_burst(scheduler):
    """Bug 3: dedup greedy es ciego al rol. Con kickoffs a pocos minutos (Mundial:
    21:00, 21:03), la ráfaga de cierre de un evento puede caer <240s de la del
    vecino y perderse. La ráfaga de cierre NUNCA debe adelgazarse."""
    target = _target("wc", "soccer_fifa_world_cup")
    config = _config([target])

    base = datetime.now(UTC) + timedelta(hours=3)
    event_a = {"id": "a", "commence_time": base.isoformat().replace("+00:00", "Z")}
    event_b = {
        "id": "b",
        "commence_time": (base + timedelta(minutes=3)).isoformat().replace("+00:00", "Z"),
    }
    client = FakeClient(events_by_sport={"soccer_fifa_world_cup": [event_a, event_b]})

    daemon.schedule_captures(scheduler, config, client=client)

    scheduled = {j.trigger.run_date for j in scheduler.get_jobs() if j.id.startswith("capture_wc_")}

    expected_closing = {
        base - timedelta(minutes=6),
        base - timedelta(minutes=2),
        base + timedelta(minutes=3) - timedelta(minutes=6),
        base + timedelta(minutes=3) - timedelta(minutes=2),
    }
    missing = expected_closing - scheduled
    assert not missing, f"ráfaga de cierre perdida por dedup: {missing}"


def test_partial_failure_isolates_targets(scheduler):
    """Discovery falla en un target pero no en otro: cada uno se resuelve por separado."""
    good = _target("good", "sport_good")
    bad = _target("bad", "sport_bad")
    config = _config([good, bad])

    scheduler.add_job(_noop, trigger=DateTrigger(
        run_date=datetime.now(UTC) + timedelta(hours=1)), id="capture_bad_pre_0")

    client = FakeClient(
        events_by_sport={"sport_good": [_future_event()]},
        fail_sports=["sport_bad"],
    )
    daemon.schedule_captures(scheduler, config, client=client)

    assert len(_capture_job_ids(scheduler, "good")) > 0, "target sano no programado"
    assert "capture_bad_pre_0" in _capture_job_ids(scheduler, "bad"), (
        "fallo en un target borró la agenda de otro"
    )
