"""Cliente mínimo para The Odds API v4 con guardrail de coste incorporado.

Cualquier método que consuma cuota (`get_odds`) solo estima el coste por
defecto (`dry_run=True`). Solo gasta crédito real si se pasa `dry_run=False`
explícitamente. Ver la sección "Guardrail de coste" en CLAUDE.md.
"""

import logging
import math
import os

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"


class OddsApiError(RuntimeError):
    """La API devolvió un error o falta configuración necesaria."""


class OddsApiClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ODDS_API_KEY")
        if not self.api_key:
            raise OddsApiError("ODDS_API_KEY no está configurada (revisa tu .env)")

    def _get(self, path: str, params: dict | None = None) -> requests.Response:
        params = dict(params or {})
        params["apiKey"] = self.api_key
        try:
            response = requests.get(f"{BASE_URL}{path}", params=params, timeout=10)
        except requests.RequestException as exc:
            raise OddsApiError(f"{path} falló por error de red: {exc.__class__.__name__}") from exc
        logger.info(
            "GET %s -> %s (x-requests-used=%s, x-requests-remaining=%s)",
            path,
            response.status_code,
            response.headers.get("x-requests-used"),
            response.headers.get("x-requests-remaining"),
        )
        if not response.ok:
            raise OddsApiError(f"{path} devolvió {response.status_code}: {response.text}")
        return response

    def get_sports(self) -> list[dict]:
        """GET /v4/sports — coste 0, siempre permitido."""
        return self._get("/sports").json()

    def get_usage(self) -> dict[str, str | None]:
        """Consulta la cuota usando GET /v4/sports, que tiene coste 0."""
        response = self._get("/sports")
        return {
            "remaining": response.headers.get("x-requests-remaining"),
            "used": response.headers.get("x-requests-used"),
            "last": response.headers.get("x-requests-last"),
        }

    def get_events(self, sport: str) -> list[dict]:
        """GET /v4/sports/{sport}/events — coste 0, siempre permitido."""
        return self._get(f"/sports/{sport}/events").json()

    def get_odds(
        self,
        sport: str,
        markets: list[str],
        bookmakers: list[str],
        dry_run: bool = True,
    ) -> dict:
        """GET /v4/sports/{sport}/odds.

        Coste = len(markets) * ceil(len(bookmakers) / 10). Con dry_run=True
        (por defecto) no hace ninguna petición real, solo devuelve el coste
        estimado y la petición que se haría.
        """
        estimated_cost = len(markets) * math.ceil(len(bookmakers) / 10)
        params = {"markets": ",".join(markets), "bookmakers": ",".join(bookmakers)}

        if dry_run:
            return {
                "dry_run": True,
                "estimated_cost": estimated_cost,
                "url": f"{BASE_URL}/sports/{sport}/odds",
                "params": params,
            }

        response = self._get(f"/sports/{sport}/odds", params=params)
        return {
            "dry_run": False,
            "estimated_cost": estimated_cost,
            "data": response.json(),
            "requests_used": response.headers.get("x-requests-used"),
            "requests_remaining": response.headers.get("x-requests-remaining"),
        }
