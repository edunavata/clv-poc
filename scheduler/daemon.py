"""Demonio autónomo de captura.

Descubre eventos periódicamente y programa capturas (trayectoria + ráfaga de cierre).
Resiliente a reinicios: al arrancar lee la API y programa lo necesario.

Sin backfill, a propósito: si el demonio cae durante una ráfaga de cierre, ese cierre
no se recupera al reiniciar. Reconstruirlo a posteriori (vía endpoint histórico de
pago) sería fabricar un dato que no se capturó en su momento -- justo lo que este
proyecto no acepta. Un cierre ausente se queda ausente y marcado como hueco, no
rellenado.
"""

import logging
import sys
import time
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from client.odds_api import OddsApiClient
from config import AppConfig, load_config, load_dotenv
from scheduler.capture import capture_target
from scheduler.planning import (
    CLOSE_BURST_MINUTES,
    DISCOVERY_INTERVAL_HOURS,
    plan_capture_times,
    split_due_and_moved,
)
from storage.db import get_connection

import os
from logging.handlers import RotatingFileHandler


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)

    fh = RotatingFileHandler("logs/daemon.log", maxBytes=10 * 1024 * 1024, backupCount=5)
    fh.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(ch)
    root_logger.addHandler(fh)


logger = logging.getLogger(__name__)


def discover_events(client: OddsApiClient, sport_key: str) -> list[dict]:
    try:
        # R3: endpoint /events tiene coste 0
        events = client.get_events(sport_key)
        return events
    except Exception as e:
        logger.error("Error descubriendo eventos para %s: %s", sport_key, e)
        return []


def reschedule_moved_burst(
    scheduler: BackgroundScheduler,
    target_name: str,
    db_path: str,
    min_credits: int,
    moved: list[tuple[str, str]],
    now: datetime,
) -> None:
    """Reprograma la ráfaga de cierre de eventos cuyo kickoff se aplazó.

    Los jobs llevan el prefijo capture_{target}_ para que el siguiente discovery
    los reemplace igual que al resto de la agenda."""
    for event_id, new_iso in moved:
        new_commence = datetime.fromisoformat(new_iso.replace("Z", "+00:00"))
        for minutes in CLOSE_BURST_MINUTES:
            run_at = new_commence - timedelta(minutes=minutes)
            if run_at <= now:
                continue
            scheduler.add_job(
                run_capture_job,
                trigger=DateTrigger(run_date=run_at),
                args=[target_name, db_path, min_credits, True],
                kwargs={"event_checks": [(event_id, new_iso)], "scheduler": scheduler},
                id=f"capture_{target_name}_moved_{event_id}_{run_at.timestamp()}",
                replace_existing=True,
                misfire_grace_time=90,
            )
        logger.info(
            "Kickoff aplazado: ráfaga de %s reprogramada a %s para evento %s",
            target_name,
            new_iso,
            event_id,
        )


def run_capture_job(
    target_name: str,
    db_path: str,
    min_credits: int,
    is_closing: bool = False,
    event_checks: list[tuple[str, str]] | None = None,
    scheduler: BackgroundScheduler | None = None,
):
    # Aislar imports e instanciación para el worker del job
    from client.odds_api import OddsApiClient
    from config import load_config

    config = load_config()
    targets = [t for t in config.active_targets() if t.name == target_name]
    if not targets:
        return

    client = OddsApiClient()

    # Recheck de aplazamientos antes de gastar el crédito de /odds: la ráfaga se
    # programó en el discovery y el kickoff puede haberse movido después (meteo,
    # retrasos). /events cuesta 0 créditos. Fail-open: si el recheck falla, se
    # captura igualmente.
    if is_closing and event_checks and scheduler is not None:
        try:
            events = client.get_events(targets[0].sport_key)  # coste 0
            current = {e["id"]: e["commence_time"] for e in events}
        except Exception as e:
            logger.warning(
                "Recheck de commence falló para %s (%s); capturo igualmente", target_name, e
            )
            current = None
        if current is not None:
            now = datetime.now(UTC)
            due, moved = split_due_and_moved(event_checks, current, now)
            if moved:
                reschedule_moved_burst(scheduler, target_name, db_path, min_credits, moved, now)
            if not due:
                logger.info(
                    "Ráfaga de %s omitida: kickoff(s) aplazados, crédito de /odds ahorrado",
                    target_name,
                )
                return

    con = get_connection(db_path)
    captured_at = datetime.now(UTC)
    result = capture_target(client, con, targets[0], min_credits, captured_at, is_closing=is_closing)
    con.close()

    if not result.ok:
        logger.error("Fallo en job de captura para %s: %s", target_name, result.reason)


def schedule_captures(
    scheduler: BackgroundScheduler, config: AppConfig, client: OddsApiClient | None = None
):
    if client is None:
        client = OddsApiClient()
    targets = config.active_targets()
    now = datetime.now(UTC)

    total_jobs = 0
    for target in targets:
        events = discover_events(client, target.sport_key)
        # R8 + resiliencia: un discovery caído NO debe vaciar la agenda. Solo tocamos
        # los jobs de este target DESPUÉS de saber que podemos reconstruirlos; si falla,
        # conservamos la agenda previa hasta el próximo tick de discovery.
        if not events:
            logger.warning(
                "Discovery sin eventos para %s; conservo agenda previa", target.name
            )
            continue

        # Reemplazo atómico por target: borrar jobs viejos SOLO de este target
        for job in scheduler.get_jobs():
            if job.id.startswith(f"capture_{target.name}_"):
                scheduler.remove_job(job.id)

        # El algoritmo (ráfaga de cierre + trayectoria + dedup R7) vive en
        # scheduler.planning como función pura, compartida con la vista previa.
        planned = plan_capture_times(events, now, target.poll_interval_hours)

        for i, pc in enumerate(planned):
            job_id = f"capture_{target.name}_{i}_{pc.run_at.timestamp()}"
            # Las ráfagas de cierre llevan sus eventos esperados para el recheck de
            # aplazamientos justo antes de disparar (ver run_capture_job).
            job_kwargs = (
                {
                    "event_checks": [(e["id"], e["commence_time"]) for e in pc.events],
                    "scheduler": scheduler,
                }
                if pc.is_closing and pc.events
                else {}
            )
            scheduler.add_job(
                run_capture_job,
                trigger=DateTrigger(run_date=pc.run_at),
                args=[target.name, config.db_path, config.min_remaining_credits, pc.is_closing],
                kwargs=job_kwargs,
                id=job_id,
                replace_existing=True,
                # Default de APScheduler es 1s: un retraso mínimo (hilo ocupado, sleep
                # de sistema) descartaría en silencio el poll de cierre, el dato de
                # mayor valor. 90s cubre eso sin arriesgar capturar in-play.
                misfire_grace_time=90,
            )

        logger.info("Programadas %d capturas para target %s", len(planned), target.name)
        total_jobs += len(planned)

    # Re-programar este mismo descubrimiento (R8)
    scheduler.add_job(
        schedule_captures,
        trigger="interval",
        hours=DISCOVERY_INTERVAL_HOURS,
        args=[scheduler, config],
        id="discovery_job",
        replace_existing=True,
    )


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    load_dotenv()
    config = load_config()

    # Usar ThreadPoolExecutor interno de APScheduler por defecto
    scheduler = BackgroundScheduler(timezone=UTC)
    scheduler.start()

    logger.info("Iniciando demonio de captura. Ejecutando descubrimiento inicial...")
    schedule_captures(scheduler, config)

    try:
        # R1: Proceso de larga duración
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Deteniendo demonio...")
        scheduler.shutdown()
        return 0


if __name__ == "__main__":
    sys.exit(main())
