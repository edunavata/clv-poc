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

# Configuración de captura
DISCOVERY_INTERVAL_HOURS = 12
CLOSE_BURST_MINUTES = [6, 2]  # Ráfaga antes del inicio (R5, R9)


def discover_events(client: OddsApiClient, sport_key: str) -> list[dict]:
    try:
        # R3: endpoint /events tiene coste 0
        events = client.get_events(sport_key)
        return events
    except Exception as e:
        logger.error("Error descubriendo eventos para %s: %s", sport_key, e)
        return []


def run_capture_job(target_name: str, db_path: str, min_credits: int, is_closing: bool = False):
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

        closing_times = set()
        max_commence = None
        for event in events:
            # commence_time viene en formato ISO con 'Z'
            commence = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
            if max_commence is None or commence > max_commence:
                max_commence = commence

            # R4, R5, R9: Ráfaga de cierre
            for m in CLOSE_BURST_MINUTES:
                t = commence - timedelta(minutes=m)
                if t > now:
                    closing_times.add(t)

        # R1: la trayectoria es propiedad del tablero (sport_key), no del evento --
        # un solo poll cosecha todos los eventos próximos a la vez. Cadencia rala,
        # global, con el intervalo propio del target. Acotada al próximo ciclo de
        # discovery: no tiene sentido programar más lejos porque discovery_job
        # reconstruye la agenda entera antes de llegar ahí.
        trajectory_times = set()
        if max_commence is not None:
            horizon = min(max_commence, now + timedelta(hours=DISCOVERY_INTERVAL_HOURS))
            interval = timedelta(hours=target.poll_interval_hours)
            t = now + interval
            while t < horizon:
                trajectory_times.add(t)
                t += interval

        # R7: Deduplicación por sport_key y ventana temporal. La ráfaga de cierre
        # NUNCA se adelgaza -- con kickoffs apiñados (Mundial: 21:00, 21:03...) un
        # filtro ciego al rol puede tirar el -2min de un evento a favor del -6min
        # del vecino, degradando la cercanía al pitido en silencio. Solo la
        # trayectoria se adelgaza, y contra cualquier tiempo ya aceptado
        # (cierre o trayectoria) con al menos 4 minutos de diferencia.
        filtered_times = sorted(closing_times)
        for t in sorted(trajectory_times):
            if all(abs((t - accepted).total_seconds()) >= 240 for accepted in filtered_times):
                filtered_times.append(t)
        filtered_times.sort()

        for i, t in enumerate(filtered_times):
            job_id = f"capture_{target.name}_{i}_{t.timestamp()}"
            is_closing = t in closing_times
            scheduler.add_job(
                run_capture_job,
                trigger=DateTrigger(run_date=t),
                args=[target.name, config.db_path, config.min_remaining_credits, is_closing],
                id=job_id,
                replace_existing=True,
                # Default de APScheduler es 1s: un retraso mínimo (hilo ocupado, sleep
                # de sistema) descartaría en silencio el poll de cierre, el dato de
                # mayor valor. 90s cubre eso sin arriesgar capturar in-play.
                misfire_grace_time=90,
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
