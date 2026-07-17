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


def test_closing_jobs_flagged_so_quota_floor_does_not_block_them(scheduler):
    """El suelo de créditos (capture_target's is_closing) solo debe cortar
    trayectoria. El daemon debe marcar cada job con su rol real."""
    target = _target("wc", "soccer_fifa_world_cup")
    config = _config([target])
    commence = datetime.now(UTC) + timedelta(hours=2)
    event = {"id": "evt1", "commence_time": commence.isoformat().replace("+00:00", "Z")}
    client = FakeClient(events_by_sport={"soccer_fifa_world_cup": [event]})

    daemon.schedule_captures(scheduler, config, client=client)

    jobs = [j for j in scheduler.get_jobs() if j.id.startswith("capture_wc_")]
    assert jobs, "no se programó ningún job"

    closing_run_dates = {
        commence - timedelta(minutes=6),
        commence - timedelta(minutes=2),
    }
    for job in jobs:
        is_closing_arg = job.args[3]
        if job.trigger.run_date in closing_run_dates:
            assert is_closing_arg is True, f"job de cierre {job.id} no marcado is_closing"
        else:
            assert is_closing_arg is False, f"job de trayectoria {job.id} marcado is_closing"


def _dispersed_events(sport_key, hours_ahead_list):
    return [
        {
            "id": f"evt{i}",
            "commence_time": (datetime.now(UTC) + timedelta(hours=h)).isoformat().replace(
                "+00:00", "Z"
            ),
        }
        for i, h in enumerate(hours_ahead_list)
    ]


def _trajectory_run_dates(sched, target_name):
    jobs = [j for j in sched.get_jobs() if j.id.startswith(f"capture_{target_name}_")]
    return sorted(j.trigger.run_date for j in jobs if j.args[3] is False)


def test_trajectory_count_independent_of_dispersed_event_count(scheduler):
    """R1/AC1: trayectoria es cadencia de tablero, no por evento. Con eventos
    dispersos (sin coincidencias de horario, como MLS) el número de capturas de
    trayectoria no debe crecer con el número de eventos."""
    target = _target("mls", "soccer_usa_mls")
    config = _config([target])

    few = _dispersed_events("soccer_usa_mls", [5, 15, 25])
    many = _dispersed_events("soccer_usa_mls", [5, 15, 25, 35, 45, 55, 65, 75, 85, 95])

    client_few = FakeClient(events_by_sport={"soccer_usa_mls": few})
    daemon.schedule_captures(scheduler, config, client=client_few)
    count_few = len(_trajectory_run_dates(scheduler, "mls"))

    client_many = FakeClient(events_by_sport={"soccer_usa_mls": many})
    daemon.schedule_captures(scheduler, config, client=client_many)
    count_many = len(_trajectory_run_dates(scheduler, "mls"))

    assert count_few == count_many, (
        f"trayectoria escala con nº de eventos: {count_few} eventos=3 vs "
        f"{count_many} eventos=10"
    )
    assert 0 < count_few <= 4, f"nº de capturas de trayectoria fuera de rango: {count_few}"


def test_trajectory_cadence_matches_target_poll_interval(scheduler):
    """R1: la cadencia de trayectoria usa target.poll_interval_hours, no una
    lista fija de offsets relativos al evento."""
    target = _target("mls", "soccer_usa_mls")
    config = _config([target])
    events = _dispersed_events("soccer_usa_mls", [50])
    client = FakeClient(events_by_sport={"soccer_usa_mls": events})

    daemon.schedule_captures(scheduler, config, client=client)
    trajectory_dates = _trajectory_run_dates(scheduler, "mls")

    assert len(trajectory_dates) >= 2, "no hay suficientes puntos para medir cadencia"
    for a, b in zip(trajectory_dates, trajectory_dates[1:]):
        gap_hours = (b - a).total_seconds() / 3600
        assert abs(gap_hours - target.poll_interval_hours) < 0.01, (
            f"cadencia {gap_hours}h no coincide con poll_interval_hours="
            f"{target.poll_interval_hours}"
        )


def test_trajectory_horizon_capped_by_discovery_interval(scheduler):
    """R4: aunque el evento esté muy lejos en el futuro, la trayectoria no se
    programa más allá del próximo ciclo de discovery (que la reconstruirá)."""
    target = _target("mls", "soccer_usa_mls")
    config = _config([target])
    events = _dispersed_events("soccer_usa_mls", [24 * 30])  # evento a 30 días
    client = FakeClient(events_by_sport={"soccer_usa_mls": events})

    now = datetime.now(UTC)
    daemon.schedule_captures(scheduler, config, client=client)
    trajectory_dates = _trajectory_run_dates(scheduler, "mls")

    assert trajectory_dates, "no se programó ninguna captura de trayectoria"
    horizon = now + timedelta(hours=daemon.DISCOVERY_INTERVAL_HOURS)
    assert max(trajectory_dates) < horizon, (
        f"trayectoria programada más allá del horizonte de discovery: "
        f"{max(trajectory_dates)} >= {horizon}"
    )


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


class TestClosingBurstRecheck:
    """El job de cierre re-verifica el kickoff vía /events (0 créditos) antes de
    gastar el crédito de /odds; si el partido se aplazó, reprograma la ráfaga."""

    def _run(self, monkeypatch, scheduler, current_commence_iso=None, fail=False):
        expected_iso = (datetime.now(UTC) + timedelta(minutes=6)).isoformat().replace("+00:00", "Z")
        target = _target("t1", "soccer_test")
        monkeypatch.setattr("config.load_config", lambda: _config([target]))

        events = [] if current_commence_iso is None else [
            {"id": "evt1", "commence_time": current_commence_iso}
        ]
        fake = FakeClient({"soccer_test": events}, fail_sports={"soccer_test"} if fail else ())
        monkeypatch.setattr("client.odds_api.OddsApiClient", lambda: fake)

        captured = []
        monkeypatch.setattr(daemon, "capture_target", lambda *a, **k: captured.append(a) or type(
            "R", (), {"ok": True, "reason": ""}
        )())

        daemon.run_capture_job(
            "t1", ":memory:", 50, is_closing=True,
            event_checks=[("evt1", expected_iso)], scheduler=scheduler,
        )
        return captured, expected_iso

    def test_postponed_skips_capture_and_reschedules(self, monkeypatch, scheduler):
        new_iso = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        captured, _ = self._run(monkeypatch, scheduler, current_commence_iso=new_iso)

        assert captured == []  # crédito de /odds ahorrado
        moved_jobs = [j for j in scheduler.get_jobs() if "_moved_evt1_" in j.id]
        assert len(moved_jobs) == 2  # ráfaga -6/-2 min sobre el nuevo kickoff

    def test_unchanged_commence_captures(self, monkeypatch, scheduler):
        captured, expected_iso = self._run(monkeypatch, scheduler)
        # el fake devuelve [] (evento ausente) => fail-open, captura
        assert len(captured) == 1
        assert not [j for j in scheduler.get_jobs() if "_moved_" in j.id]

    def test_events_endpoint_down_captures_anyway(self, monkeypatch, scheduler):
        captured, _ = self._run(monkeypatch, scheduler, fail=True)
        assert len(captured) == 1
