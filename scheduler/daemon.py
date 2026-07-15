"""Demonio autónomo de captura.

Descubre eventos periódicamente y programa capturas (trayectoria + ráfaga de cierre).
Resiliente a reinicios: al arrancar lee la API y programa lo necesario.
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
from storage.db import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# Configuración de captura
DISCOVERY_INTERVAL_HOURS = 12
TRAJECTORY_HOURS = [48, 24, 12, 6, 3, 1]
CLOSE_BURST_MINUTES = [6, 2]  # Ráfaga antes del inicio (R5, R9)


def discover_events(client: OddsApiClient, sport_key: str) -> list[dict]:
    try:
        # R3: endpoint /events tiene coste 0
        events = client.get_events(sport_key)
        return events
    except Exception as e:
        logger.error("Error descubriendo eventos para %s: %s", sport_key, e)
        return []


def run_capture_job(target_name: str, db_path: str, min_credits: int):
    # Aislar imports e instanciación para el worker del job
    from client.odds_api import OddsApiClient
    from config import load_config

    config = load_config()
    targets = [t for t in config.active_targets() if t.name == target_name]
    if not targets:
        return

    client = OddsApiClient()
    con = get_connection(db_path)
    captured_at = datetime.now(UTC)
    result = capture_target(client, con, targets[0], min_credits, captured_at)
    con.close()

    if not result.ok:
        logger.error("Fallo en job de captura para %s: %s", target_name, result.reason)


def schedule_captures(scheduler: BackgroundScheduler, config: AppConfig):
    client = OddsApiClient()
    targets = config.active_targets()
    now = datetime.now(UTC)

    # R8: limpiar jobs anteriores del target para evitar duplicados en reprogramación
    # Solo eliminamos jobs de captura, no el de discovery
    for job in scheduler.get_jobs():
        if job.id.startswith("capture_"):
            scheduler.remove_job(job.id)

    total_jobs = 0
    for target in targets:
        events = discover_events(client, target.sport_key)
        if not events:
            continue

        poll_times = set()
        for event in events:
            # commence_time viene en formato ISO con 'Z'
            commence = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))

            # R6: Trayectoria
            for h in TRAJECTORY_HOURS:
                t = commence - timedelta(hours=h)
                if t > now:
                    poll_times.add(t)

            # R4, R5, R9: Ráfaga de cierre
            for m in CLOSE_BURST_MINUTES:
                t = commence - timedelta(minutes=m)
                if t > now:
                    poll_times.add(t)

        # R7: Deduplicación por sport_key y ventana temporal
        # Ordenamos y mantenemos llamadas con al menos 4 minutos de diferencia
        sorted_times = sorted(list(poll_times))
        filtered_times = []
        for t in sorted_times:
            if not filtered_times or (t - filtered_times[-1]).total_seconds() >= 240:
                filtered_times.append(t)

        for i, t in enumerate(filtered_times):
            job_id = f"capture_{target.name}_{i}_{t.timestamp()}"
            scheduler.add_job(
                run_capture_job,
                trigger=DateTrigger(run_date=t),
                args=[target.name, config.db_path, config.min_remaining_credits],
                id=job_id,
                replace_existing=True,
            )

        logger.info("Programadas %d capturas para target %s", len(filtered_times), target.name)
        total_jobs += len(filtered_times)

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
