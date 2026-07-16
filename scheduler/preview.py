"""Vista previa de las próximas capturas programadas.

Recalcula -- de forma standalone y con **coste 0 créditos** -- el schedule que el
daemon (`scheduler.daemon`) programaría con un discovery en este instante. El
jobstore del daemon es en memoria, así que no se puede introspeccionar el proceso
vivo; en su lugar se llama `get_events` (endpoint gratuito) y se reusa la misma
función pura de planificación (`scheduler.planning.plan_capture_times`), de modo que
lo que se muestra no puede divergir de lo que el daemon haría.

`build_schedule_rows` es reutilizable (lo consume también el dashboard). `main`
imprime una tabla ANSI por consola.

Uso:
    uv run python -m scheduler.preview            # todos los targets activos
    uv run python -m scheduler.preview --target world_cup_2026
"""

import argparse
import logging
import sys
from datetime import UTC, datetime

from client.odds_api import OddsApiClient, OddsApiError
from config import AppConfig, load_config, load_dotenv
from scheduler.planning import plan_capture_times

logger = logging.getLogger(__name__)


def _commence(event: dict) -> datetime:
    return datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))


def _event_label(event: dict) -> str:
    """`Home vs Away (HH:MM)` con la hora de kickoff en UTC; cae al id si faltan equipos."""
    ko = _commence(event).strftime("%H:%M")
    home, away = event.get("home_team"), event.get("away_team")
    if home and away:
        return f"{home} vs {away} ({ko})"
    return f"{event.get('id', '?')} ({ko})"


def build_schedule_rows(
    client: OddsApiClient, config: AppConfig, now: datetime | None = None
) -> list[dict]:
    """Filas de las próximas capturas de todos los targets activos.

    Cada fila: target, sport_key, run_at (UTC), minutes_until, is_closing, role,
    events_desc. Un target cuyo `get_events` falle se omite con un warning (no
    revienta el resto). Consume 0 créditos (`get_events` es gratuito).
    """
    if now is None:
        now = datetime.now(UTC)

    rows: list[dict] = []
    for target in config.active_targets():
        try:
            events = client.get_events(target.sport_key)
        except Exception as exc:  # red caída, /events no disponible, etc.
            logger.warning("No se pudieron descubrir eventos para %s: %s", target.name, exc)
            continue

        planned = plan_capture_times(events, now, target.poll_interval_hours)
        for pc in planned:
            if pc.is_closing:
                events_desc = "; ".join(_event_label(e) for e in pc.events)
            else:
                n_upcoming = sum(1 for e in events if _commence(e) > pc.run_at)
                events_desc = f"todo el tablero ({n_upcoming} próximos)"

            rows.append(
                {
                    "target": target.name,
                    "sport_key": target.sport_key,
                    "run_at": pc.run_at,
                    "minutes_until": int((pc.run_at - now).total_seconds() // 60),
                    "is_closing": pc.is_closing,
                    "role": "cierre" if pc.is_closing else "trayectoria",
                    "events_desc": events_desc,
                }
            )

    rows.sort(key=lambda r: r["run_at"])
    return rows


# ── Formato ANSI (mismo estilo que scripts/list_sports.py) ──────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"


def _humanize(minutes: int) -> str:
    if minutes < 0:
        return "ahora"
    return f"{minutes // 60}h{minutes % 60:02d}m"


def _print_rows(rows: list[dict]) -> None:
    width = 78
    print()
    print(f"{BOLD}{CYAN}{'━' * width}{RESET}")
    print(f"{BOLD}{CYAN}  PRÓXIMAS CAPTURAS PROGRAMADAS{RESET}")
    print(f"{DIM}  Recompute vía get_events (0 créditos). Lo que el daemon programaría ahora.{RESET}")
    print(f"{BOLD}{CYAN}{'━' * width}{RESET}")

    if not rows:
        print(f"\n  {YELLOW}Sin capturas próximas (ningún evento en el horizonte).{RESET}\n")
        return

    current_target = None
    # Agrupar por target en bloques contiguos (las filas llegan en orden temporal
    # global; para la vista de consola preferimos un bloque por target).
    for r in sorted(rows, key=lambda x: (x["target"], x["run_at"])):
        if r["target"] != current_target:
            current_target = r["target"]
            print(f"\n  {BOLD}▌ {current_target}{RESET}  {DIM}({r['sport_key']}){RESET}")
            print(f"  {DIM}{'─' * (width - 2)}{RESET}")

        role = f"{RED}🔒 cierre{RESET}" if r["is_closing"] else f"{GREEN}📈 tray  {RESET}"
        ts = r["run_at"].strftime("%Y-%m-%d %H:%M")
        eta = _humanize(r["minutes_until"])
        print(f"    {DIM}{ts} UTC{RESET}  {DIM}en{RESET} {eta:>7}  {role}  {r['events_desc']}")

    closing = sum(1 for r in rows if r["is_closing"])
    traj = len(rows) - closing
    print(f"\n{BOLD}{CYAN}{'━' * width}{RESET}")
    print(
        f"  {BOLD}Total{RESET} {len(rows)} capturas  "
        f"({RED}{closing} cierre{RESET}, {GREEN}{traj} trayectoria{RESET})   "
        f"{DIM}coste: 0 créditos (get_events gratis){RESET}"
    )
    print(f"{BOLD}{CYAN}{'━' * width}{RESET}\n")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Muestra las próximas capturas programadas (recompute, 0 créditos)."
    )
    parser.add_argument("--target", help="Filtrar por nombre de target")
    args = parser.parse_args(argv)

    load_dotenv()
    config = load_config()

    try:
        client = OddsApiClient()
    except OddsApiError as exc:
        print(f"{RED}{BOLD}✖ Error de configuración:{RESET} {exc}")
        return 1

    rows = build_schedule_rows(client, config)
    if args.target:
        rows = [r for r in rows if r["target"] == args.target]

    _print_rows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
