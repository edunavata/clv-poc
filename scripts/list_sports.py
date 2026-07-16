"""
Script: list_sports.py
Obtiene todos los deportes disponibles en The Odds API y los muestra por
consola agrupados por categoría, con formato legible y colores ANSI.

Uso:
    python scripts/list_sports.py          # Solo deportes en temporada
    python scripts/list_sports.py --all    # Todos (incluyendo fuera de temporada)
"""

import sys
import os
import argparse
from collections import defaultdict
from pathlib import Path

# ── Permite importar el paquete client desde la raíz del proyecto ──────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from client.odds_api import OddsApiClient, OddsApiError

# ── Constantes de color ANSI ───────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"

# Paleta de colores para grupos de deporte
CYAN    = "\033[96m"
YELLOW  = "\033[93m"
GREEN   = "\033[92m"
MAGENTA = "\033[95m"
BLUE    = "\033[94m"
RED     = "\033[91m"
WHITE   = "\033[97m"
ORANGE  = "\033[38;5;208m"
TEAL    = "\033[38;5;43m"
PINK    = "\033[38;5;213m"

GROUP_COLORS = [CYAN, YELLOW, GREEN, MAGENTA, BLUE, ORANGE, TEAL, PINK, RED, WHITE]

ACTIVE_DOT  = f"\033[92m●{RESET}"   # verde
INACTIVE_DOT = f"\033[90m○{RESET}"  # gris


def print_header(show_all: bool) -> None:
    width = 64
    title = "THE ODDS API — DEPORTES DISPONIBLES"
    subtitle = "Todos los deportes" if show_all else "Solo deportes en temporada"

    print()
    print(f"{BOLD}{CYAN}{'━' * width}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{DIM}  {subtitle}{RESET}")
    print(f"{BOLD}{CYAN}{'━' * width}{RESET}")
    print()


def print_sport_row(sport: dict, idx: int) -> None:
    status = ACTIVE_DOT if sport.get("active") else INACTIVE_DOT
    key    = f"{DIM}{sport['key']}{RESET}"
    title  = f"{BOLD}{sport['title']}{RESET}"
    desc   = sport.get("description", "")

    # Número de ítem alineado
    num = f"{DIM}{idx:>2}.{RESET}"
    print(f"   {num} {status}  {title:<28} {key}")
    if desc and desc != sport["title"]:
        print(f"         {DIM}   └─ {desc}{RESET}")


def print_group(group_name: str, sports: list[dict], color: str) -> None:
    active_count   = sum(1 for s in sports if s.get("active"))
    inactive_count = len(sports) - active_count

    # Cabecera del grupo
    print(f"  {BOLD}{color}▌ {group_name.upper()}{RESET}  "
          f"{DIM}({active_count} activos"
          f"{f', {inactive_count} inactivos' if inactive_count else ''}){RESET}")
    print(f"  {DIM}{'─' * 60}{RESET}")

    for i, sport in enumerate(sports, start=1):
        print_sport_row(sport, i)

    print()


def print_summary(sports: list[dict], show_all: bool) -> None:
    total    = len(sports)
    active   = sum(1 for s in sports if s.get("active"))
    inactive = total - active
    groups   = len({s.get("group", "Other") for s in sports})

    print(f"{BOLD}{CYAN}{'━' * 64}{RESET}")
    print(f"  {BOLD}Resumen{RESET}")
    print(f"  {ACTIVE_DOT}  {GREEN}{BOLD}{active}{RESET} deportes activos   "
          f"{INACTIVE_DOT}  {DIM}{inactive} inactivos{RESET}   "
          f"{BLUE}{BOLD}{total}{RESET} total   "
          f"{YELLOW}{groups}{RESET} categorías")
    if not show_all:
        print(f"\n  {DIM}Tip: usa --all para ver también los deportes fuera de temporada{RESET}")
    print(f"{BOLD}{CYAN}{'━' * 64}{RESET}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lista los deportes disponibles en The Odds API."
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Incluir deportes fuera de temporada"
    )
    args = parser.parse_args()
    show_all: bool = args.all

    try:
        client = OddsApiClient()
    except OddsApiError as exc:
        print(f"\n{RED}{BOLD}✖ Error de configuración:{RESET} {exc}\n")
        sys.exit(1)

    print_header(show_all)

    try:
        sports = client.get_sports()
        if show_all:
            # La API no tiene parámetro all directo en get_sports, lo pasamos manualmente
            from client.odds_api import BASE_URL
            import requests
            import os
            resp = requests.get(
                f"{BASE_URL}/sports",
                params={"apiKey": os.environ["ODDS_API_KEY"], "all": "true"},
                timeout=10,
            )
            resp.raise_for_status()
            sports = resp.json()
    except OddsApiError as exc:
        print(f"\n{RED}{BOLD}✖ Error al obtener deportes:{RESET} {exc}\n")
        sys.exit(1)

    # Agrupar por "group"
    groups: dict[str, list[dict]] = defaultdict(list)
    for sport in sports:
        group = sport.get("group") or "Other"
        groups[group].append(sport)

    # Ordenar grupos alfabéticamente; dentro de cada grupo, activos primero
    sorted_groups = sorted(groups.items(), key=lambda x: x[0])

    for color_idx, (group_name, group_sports) in enumerate(sorted_groups):
        color = GROUP_COLORS[color_idx % len(GROUP_COLORS)]
        # Activos primero, luego inactivos, alfabéticamente dentro de cada subgrupo
        sorted_sports = sorted(
            group_sports,
            key=lambda s: (not s.get("active", False), s.get("title", "").lower())
        )
        print_group(group_name, sorted_sports, color)

    print_summary(sports, show_all)


if __name__ == "__main__":
    main()
