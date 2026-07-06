"""Consulta los créditos restantes de The Odds API.

Usa GET /v4/sports, que devuelve las cabeceras de cuota y no consume créditos.

Uso:
    uv run python scripts/check_odds_api_credits.py
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from client.odds_api import OddsApiClient, OddsApiError  # noqa: E402


def _load_dotenv(path: Path) -> None:
    """Carga .env a mano (sin dependencia nueva) si las vars no están ya en el entorno."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    _load_dotenv(REPO_ROOT / ".env")

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
