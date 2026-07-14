"""Consulta los créditos restantes de The Odds API.

Usa GET /v4/sports, que devuelve las cabeceras de cuota y no consume créditos.

Uso:
    uv run python scripts/check_odds_api_credits.py
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from client.odds_api import OddsApiClient, OddsApiError  # noqa: E402


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")

    try:
        usage = OddsApiClient().get_usage()
    except OddsApiError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Créditos restantes: {usage['remaining']}")
    print(f"Créditos usados: {usage['used']}")
    print(f"Coste última llamada: {usage['last']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
