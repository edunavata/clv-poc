"""Planificación pura de capturas.

Dado un lote de eventos y un instante `now`, calcula CUÁNDO capturar (ráfaga de
cierre + trayectoria) sin tocar red ni scheduler. Extraído de
`scheduler.daemon.schedule_captures` para que exista una única fuente de verdad del
algoritmo, compartida por:

- el daemon, que registra estos tiempos como jobs de APScheduler, y
- la vista previa / dashboard, que recalculan el mismo schedule con un discovery
  gratuito (`get_events`, coste 0 créditos) para enseñar las próximas capturas.

Al ser función pura es testeable en aislamiento y no puede divergir del daemon.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

# Config de captura (fuente única; daemon.py re-importa estas constantes).
DISCOVERY_INTERVAL_HOURS = 12
CLOSE_BURST_MINUTES = [6, 2]  # Ráfaga antes del inicio (R5, R9)


@dataclass(frozen=True)
class PlannedCapture:
    """Una captura planificada.

    `events` son los eventos que MOTIVAN esta captura: para un cierre, el/los
    evento(s) cuyo kickoff cae en la ventana de ráfaga de este instante; para
    trayectoria es `()` -- un poll de trayectoria cosecha todo el tablero, no un
    evento concreto.
    """

    run_at: datetime  # UTC
    is_closing: bool
    events: tuple[dict, ...] = ()


def split_due_and_moved(
    event_checks: list[tuple[str, str]],
    current_commence_by_id: dict[str, str],
    now: datetime,
) -> tuple[list[str], list[tuple[str, str]]]:
    """Separa los eventos de una ráfaga de cierre en 'due' (capturar ya) y
    'moved' (kickoff aplazado a futuro: reprogramar la ráfaga, no capturar).

    event_checks: [(event_id, commence_iso)] con el que se programó la ráfaga.
    current_commence_by_id: commence actual por event_id según /events (coste 0).

    Fail-open: un evento ausente de la respuesta o cuyo nuevo kickoff ya pasó se
    captura igualmente -- mejor gastar el crédito que perder un cierre real.
    """
    due: list[str] = []
    moved: list[tuple[str, str]] = []
    for event_id, expected_iso in event_checks:
        current_iso = current_commence_by_id.get(event_id)
        if current_iso is None or current_iso == expected_iso:
            due.append(event_id)
            continue
        new_commence = datetime.fromisoformat(current_iso.replace("Z", "+00:00"))
        if new_commence <= now:
            due.append(event_id)
        else:
            moved.append((event_id, current_iso))
    return due, moved


def plan_capture_times(
    events: list[dict],
    now: datetime,
    poll_interval_hours: float,
    close_burst_minutes: list[int] = CLOSE_BURST_MINUTES,
    discovery_interval_hours: int = DISCOVERY_INTERVAL_HOURS,
) -> list[PlannedCapture]:
    """Calcula las capturas planificadas para un lote de eventos de un sport_key.

    Réplica exacta del algoritmo inline que vivía en `schedule_captures`.
    """
    # R4, R5, R9: ráfaga de cierre. Un instante de cierre puede estar motivado por
    # varios eventos con kickoffs apiñados; los agrupamos para poder atribuirlos.
    closing_events: dict[datetime, list[dict]] = {}
    max_commence: datetime | None = None
    for event in events:
        # commence_time viene en formato ISO con 'Z'
        commence = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
        if max_commence is None or commence > max_commence:
            max_commence = commence

        for m in close_burst_minutes:
            t = commence - timedelta(minutes=m)
            if t > now:
                closing_events.setdefault(t, []).append(event)

    closing_times = set(closing_events)

    # R1: la trayectoria es propiedad del tablero (sport_key), no del evento -- un
    # solo poll cosecha todos los eventos próximos a la vez. Cadencia rala, global,
    # con el intervalo propio del target. Acotada al próximo ciclo de discovery: no
    # tiene sentido programar más lejos porque discovery reconstruye la agenda entera
    # antes de llegar ahí.
    trajectory_times: set[datetime] = set()
    if max_commence is not None:
        horizon = min(max_commence, now + timedelta(hours=discovery_interval_hours))
        interval = timedelta(hours=poll_interval_hours)
        t = now + interval
        while t < horizon:
            trajectory_times.add(t)
            t += interval

    # R7: deduplicación por ventana temporal. La ráfaga de cierre NUNCA se adelgaza
    # -- con kickoffs apiñados (Mundial: 21:00, 21:03...) un filtro ciego al rol puede
    # tirar el -2min de un evento a favor del -6min del vecino, degradando la cercanía
    # al pitido en silencio. Solo la trayectoria se adelgaza, y contra cualquier tiempo
    # ya aceptado (cierre o trayectoria) con al menos 4 minutos de diferencia.
    accepted = sorted(closing_times)
    for t in sorted(trajectory_times):
        if all(abs((t - a).total_seconds()) >= 240 for a in accepted):
            accepted.append(t)
    accepted.sort()

    result: list[PlannedCapture] = []
    for t in accepted:
        is_closing = t in closing_times
        evs = tuple(closing_events[t]) if is_closing else ()
        result.append(PlannedCapture(run_at=t, is_closing=is_closing, events=evs))
    return result
