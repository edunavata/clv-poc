"""Tarea 0 — verificación bloqueante: ¿Pinnacle responde en el tier gratuito?

Toda la tesis de Edge A depende de que Pinnacle esté accesible con la key
gratuita. Este script no asume nada de la documentación de marketing: hace
la llamada real y reporta el resultado exacto.

Pasos (los dos primeros son gratis, coste 0):
  1. GET /sports        -> confirma la cuota real de esta key (headers de la
                            respuesta), no una cifra de la web de precios.
  2. GET /events        -> confirma que hay partidos programados del Mundial
                            2026 antes de gastar nada en /odds.
  3. Estimación de coste de la llamada a /odds (dry-run, sin red).
  4. Solo con confirmación explícita (interactiva o --yes): llamada real a
     /odds con bookmakers=pinnacle,bet365 y markets=h2h.

Uso:
    uv run python scripts/verify_pinnacle.py            # pide confirmación
    uv run python scripts/verify_pinnacle.py --yes       # sin prompt interactivo
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from client.odds_api import OddsApiClient, OddsApiError  # noqa: E402

SPORT = "soccer_fifa_world_cup"
MARKETS = ["h2h"]
BOOKMAKERS = ["pinnacle", "bet365_uk"]

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma el gasto real de crédito sin preguntar interactivamente.",
    )
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")

    try:
        client = OddsApiClient()
    except OddsApiError as exc:
        print(f"ERROR: {exc}")
        return 1

    try:
        print("--- Paso 1/4: cuota real de esta key (GET /sports, coste 0) ---")
        sports = client.get_sports()
        print(f"{len(sports)} deportes en temporada (ver log arriba para cuota real).")

        print(f"\n--- Paso 2/4: eventos programados de {SPORT} (GET /events, coste 0) ---")
        events = client.get_events(SPORT)
        print(f"{len(events)} eventos programados.")
        if not events:
            print(
                f"No hay eventos programados para {SPORT} ahora mismo. "
                "Deteniendo — no se gasta crédito."
            )
            return 1

        print(
            f"\n--- Paso 3/4: estimación de coste (bookmakers={BOOKMAKERS}, markets={MARKETS}) ---"
        )
        estimate = client.get_odds(SPORT, markets=MARKETS, bookmakers=BOOKMAKERS, dry_run=True)
        print(f"Coste estimado: {estimate['estimated_cost']} crédito(s) real(es).")

        if not args.yes:
            answer = input("¿Confirmas gastar este crédito real? [y/N] ").strip().lower()
            if answer != "y":
                print("Cancelado. No se ha gastado ningún crédito.")
                return 0

        print("\n--- Paso 4/4: llamada real a /odds ---")
        result = client.get_odds(SPORT, markets=MARKETS, bookmakers=BOOKMAKERS, dry_run=False)
    except OddsApiError as exc:
        print(f"ERROR: {exc}")
        return 1

    found_bookmakers = {
        bookmaker["key"] for event in result["data"] for bookmaker in event.get("bookmakers", [])
    }

    print(f"\nEventos devueltos: {len(result['data'])}")
    print(f"Bookmakers encontrados: {sorted(found_bookmakers) or '(ninguno)'}")
    for requested in BOOKMAKERS:
        presente = "SÍ" if requested in found_bookmakers else "NO"
        print(f"{requested} presente: {presente}")
    print(f"Créditos usados este mes: {result['requests_used']}")
    print(f"Créditos restantes: {result['requests_remaining']}")

    if "pinnacle" not in found_bookmakers:
        print(
            "\nRESULTADO: Pinnacle NO aparece en la respuesta con esta key gratuita. "
            "Edge A tal como está planteado no es viable sin cambiar de plan. Parar aquí."
        )
        return 1

    print("\nRESULTADO: Pinnacle SÍ está disponible con esta key en el tier gratuito.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
