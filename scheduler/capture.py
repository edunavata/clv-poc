"""Captura periódica de cuotas sharp + soft para los targets activos de config.yaml.

Una ejecución = una foto: todos los targets de un mismo run comparten el
mismo captured_at. Pensado para invocarse vía cron (ver README para la línea
de crontab), no vía APScheduler -- este script hace su trabajo y termina.

Uso:
    uv run python -m scheduler.capture                    # todos los targets activos
    uv run python -m scheduler.capture --target world_cup_2026  # debug de uno solo
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

from client.odds_api import OddsApiClient, OddsApiError
from config import AppConfig, Target, load_config, load_dotenv
from storage.db import get_connection, insert_snapshot_rows

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class CaptureResult:
    target_name: str
    ok: bool
    rows_inserted: int = 0
    reason: str = ""


def parse_bookmaker_rows(event: dict, sport_key: str, captured_at: datetime) -> list[dict]:
    """Aplana un evento de /odds a filas (book, market, outcome). Sin red, función pura."""
    commence_time = datetime.fromisoformat(event["commence_time"])
    rows = []
    for bookmaker in event.get("bookmakers", []):
        book = bookmaker["key"]
        for market in bookmaker.get("markets", []):
            # api_last_update: nivel de MERCADO, no de bookmaker -- un mismo book puede
            # actualizar h2h y totals en momentos distintos.
            api_last_update = datetime.fromisoformat(market["last_update"])
            for outcome in market.get("outcomes", []):
                rows.append(
                    {
                        "captured_at": captured_at,
                        "sport_key": sport_key,
                        "event_id": event["id"],
                        "commence_time": commence_time,
                        "home_team": event["home_team"],
                        "away_team": event["away_team"],
                        "book": book,
                        "market": market["key"],
                        "outcome": outcome["name"],
                        "odds": outcome["price"],
                        "api_last_update": api_last_update,
                    }
                )
    return rows


def capture_target(
    client: OddsApiClient, con, target: Target, min_remaining_credits: int, captured_at: datetime
) -> CaptureResult:
    estimate = client.get_odds(target.sport_key, markets=target.markets, bookmakers=target.bookmakers)
    estimated_cost = estimate["estimated_cost"]

    usage = client.get_usage()
    remaining = usage["remaining"]
    if remaining is None:
        return CaptureResult(target.name, ok=False, reason="no se pudo leer la cuota restante")

    if int(remaining) - estimated_cost < min_remaining_credits:
        return CaptureResult(
            target.name,
            ok=False,
            reason=(
                f"cuota insuficiente: {remaining} restantes, coste estimado "
                f"{estimated_cost}, margen mínimo {min_remaining_credits}"
            ),
        )

    try:
        result = client.get_odds(
            target.sport_key, markets=target.markets, bookmakers=target.bookmakers, dry_run=False
        )
    except OddsApiError as exc:
        return CaptureResult(target.name, ok=False, reason=str(exc))

    rows = [
        row
        for event in result["data"]
        for row in parse_bookmaker_rows(event, target.sport_key, captured_at)
    ]
    inserted = insert_snapshot_rows(con, rows)
    logger.info(
        "target=%s eventos=%d filas=%d coste=%s creditos_restantes=%s",
        target.name,
        len(result["data"]),
        inserted,
        result["estimated_cost"],
        result["requests_remaining"],
    )
    return CaptureResult(target.name, ok=True, rows_inserted=inserted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", help="Capturar solo este target (por nombre), para debug.")
    args = parser.parse_args(argv)

    load_dotenv()
    config: AppConfig = load_config()

    targets = config.active_targets()
    if args.target:
        targets = [t for t in targets if t.name == args.target]
        if not targets:
            logger.error("target %s no encontrado o inactivo en config.yaml", args.target)
            return 1

    client = OddsApiClient()
    con = get_connection(config.db_path)
    captured_at = datetime.now(UTC)

    results = [
        capture_target(client, con, target, config.min_remaining_credits, captured_at)
        for target in targets
    ]
    con.close()

    failed = [r for r in results if not r.ok]
    for r in failed:
        logger.error("target=%s FALLO: %s", r.target_name, r.reason)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
