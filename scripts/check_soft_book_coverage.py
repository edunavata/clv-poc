"""Confirma qué soft books candidatos tienen cobertura real para el Mundial 2026
antes de fijarlos como definitivos en config.yaml.

bet365_uk ya se probó SIN cobertura en scripts/verify_pinnacle.py (Tarea 0) --
esto no concluye que esté excluido del tier gratis, solo que no tenía precio
publicado en esos 6 eventos. bwin no existe como bookmaker key en ninguna
región (docs/the-odds-api/bookmakers.md) -- descartado, no se prueba aquí.

Uso:
    uv run python scripts/check_soft_book_coverage.py         # pide confirmación
    uv run python scripts/check_soft_book_coverage.py --yes   # sin prompt interactivo
"""

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from client.odds_api import OddsApiClient, OddsApiError  # noqa: E402

SPORT = "soccer_fifa_world_cup"
MARKETS = ["h2h"]
SHARP_BOOK = "pinnacle"
CANDIDATES = ["williamhill", "betvictor", "winamax_fr", "marathonbet"]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes", action="store_true", help="Confirma el gasto real sin preguntar interactivamente."
    )
    args = parser.parse_args()

    _load_dotenv(REPO_ROOT / ".env")

    try:
        client = OddsApiClient()
    except OddsApiError as exc:
        print(f"ERROR: {exc}")
        return 1

    bookmakers = [SHARP_BOOK, *CANDIDATES]

    try:
        usage = client.get_usage()
        print(f"Créditos restantes ahora mismo: {usage['remaining']}")

        estimate = client.get_odds(SPORT, markets=MARKETS, bookmakers=bookmakers, dry_run=True)
        print(f"Coste estimado de esta llamada: {estimate['estimated_cost']} crédito(s) real(es).")
        print(f"Bookmakers a probar: {bookmakers}")

        if not args.yes:
            answer = input("¿Confirmas gastar este crédito real? [y/N] ").strip().lower()
            if answer != "y":
                print("Cancelado. No se ha gastado ningún crédito.")
                return 0

        result = client.get_odds(SPORT, markets=MARKETS, bookmakers=bookmakers, dry_run=False)
    except OddsApiError as exc:
        print(f"ERROR: {exc}")
        return 1

    found = {
        bookmaker["key"] for event in result["data"] for bookmaker in event.get("bookmakers", [])
    }

    print(f"\nEventos devueltos: {len(result['data'])}")
    print(f"Bookmakers encontrados: {sorted(found) or '(ninguno)'}")
    for candidate in [SHARP_BOOK, *CANDIDATES]:
        presente = "SÍ" if candidate in found else "NO"
        print(f"{candidate} presente: {presente}")
    print(f"Créditos usados este mes: {result['requests_used']}")
    print(f"Créditos restantes: {result['requests_remaining']}")

    covered = [c for c in CANDIDATES if c in found]
    print(f"\nSoft books con cobertura real confirmada: {covered or '(ninguno)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
