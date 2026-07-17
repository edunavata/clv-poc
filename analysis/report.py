"""Extracción de CLV por snapshot: une los snapshots soft capturados con el cierre
fair de Pinnacle y materializa el mart `clv_snapshots` en DuckDB (full refresh).

Grano = un snapshot soft. Objetivo analítico: ver cómo evoluciona el CLV según se
acerca el cierre (columna hours_to_commence), no elegir una apuesta.

El benchmark es el cierre de Pinnacle FIJO por (event, market): se saca una vez con
closing_lines + devig y cada snapshot soft se compara contra ese número.

LIMITACIÓN: devig normaliza sobre los outcomes de Pinnacle presentes en el cierre. Si
a un mercado le falta algún outcome (p. ej. h2h de fútbol sin el empate en Pinnacle),
la eliminación del overround queda sesgada. Se acepta para el POC; pinnacle_closing_
last_update por fila permite además auditar el sesgo "cierre real vs último poll".

Uso:
    uv run python -m analysis.report                      # todos los targets activos
    uv run python -m analysis.report --target world_cup_2026   # debug de uno solo
"""

import argparse
import logging
import sys

from analysis.clv import clv, devig
from config import AppConfig, Target, load_config, load_dotenv
from storage.db import closing_lines, get_connection, replace_clv_snapshots, soft_snapshots

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# Índices de columna de closing_lines(): event_id, market, outcome, home, away,
# commence, closing_odds, closing_last_update, closing_captured_at.
_C_EVENT, _C_MARKET, _C_OUTCOME, _C_ODDS, _C_LAST_UPDATE, _C_CAPTURED_AT = 0, 1, 2, 6, 7, 8
# Índices de soft_snapshots(): event_id, market, outcome, home, away, commence,
# book, captured_at, odds.
_S_EVENT, _S_MARKET, _S_OUTCOME, _S_HOME, _S_AWAY = 0, 1, 2, 3, 4
_S_COMMENCE, _S_BOOK, _S_CAPTURED, _S_ODDS = 5, 6, 7, 8


def fair_probs_by_market(closing_rows: list[tuple]) -> dict[tuple[str, str], dict]:
    """Reagrupa las filas de cierre por (event_id, market), devig-a cada mercado completo
    y devuelve por outcome su fair_prob, closing_odds y closing_last_update.

    Función pura (sin DB): {(event_id, market): {outcome: {"fair_prob", "closing_odds",
    "closing_last_update"}}}.
    """
    odds_by_market: dict[tuple[str, str], dict[str, float]] = {}
    meta_by_market: dict[tuple[str, str], dict[str, tuple]] = {}
    for row in closing_rows:
        key = (row[_C_EVENT], row[_C_MARKET])
        odds_by_market.setdefault(key, {})[row[_C_OUTCOME]] = row[_C_ODDS]
        meta_by_market.setdefault(key, {})[row[_C_OUTCOME]] = (
            row[_C_LAST_UPDATE],
            row[_C_CAPTURED_AT],
        )

    result: dict[tuple[str, str], dict] = {}
    for key, prices in odds_by_market.items():
        fair = devig(prices)  # normaliza sobre los outcomes presentes de ese mercado
        result[key] = {
            outcome: {
                "fair_prob": fair[outcome],
                "closing_odds": prices[outcome],
                "closing_last_update": meta_by_market[key][outcome][0],
                "closing_captured_at": meta_by_market[key][outcome][1],
            }
            for outcome in prices
        }
    return result


def build_clv_rows(
    soft_rows: list[tuple],
    fair_by_market: dict[tuple[str, str], dict],
    sport_key: str,
) -> tuple[list[dict], int]:
    """Función pura: por cada snapshot soft, calcula su CLV contra el cierre fair de
    Pinnacle. Devuelve (filas, nº descartadas por no tener cierre para ese outcome).
    """
    rows: list[dict] = []
    skipped = 0
    for s in soft_rows:
        market_fair = fair_by_market.get((s[_S_EVENT], s[_S_MARKET]))
        outcome_fair = market_fair.get(s[_S_OUTCOME]) if market_fair else None
        if outcome_fair is None:
            skipped += 1
            continue

        commence, captured, soft_odds = s[_S_COMMENCE], s[_S_CAPTURED], s[_S_ODDS]
        hours_to_commence = (commence - captured).total_seconds() / 3600
        closing_last_update = outcome_fair["closing_last_update"]
        closing_captured_at = outcome_fair["closing_captured_at"]
        # El eje de validez es CUÁNDO NOSOTROS sondeamos el cierre (closing_captured_at),
        # no cuándo Pinnacle actualizó su precio (closing_last_update). Un mercado
        # tranquilo (precio sin mover en 30min) capturado a 2min del pitido sigue siendo
        # un cierre válido -- closing_last_update solo audita la frescura del PRECIO,
        # no decide validez.
        hours_before_commence = (commence - closing_captured_at).total_seconds() / 3600

        # R12, R13, R15: Validamos el benchmark. Umbral en minutos, no horas: la ráfaga
        # de cierre del demonio sondea a 6/2 min del pitido y nunca se adelgaza
        # (scheduler/daemon.py), así que un cierre real siempre cae muy por debajo de
        # este umbral. 15 min da margen sobre eso sin aceptar un sondeo lejano como cierre.
        #
        # INVARIANTE (acopla con scheduler/daemon.py): este umbral debe mantenerse
        # >= poll de cierre más temprano (CLOSE_BURST_MINUTES) + misfire_grace_time
        # máximo. Hoy: 6min + 90s ~= 7.5min << 15min, margen amplio. Si algún día se
        # adelanta el primer poll de la ráfaga o se sube la gracia, revisar este
        # umbral -- si no, un cierre real puede empezar a salir inválido.
        is_valid_closing_benchmark = hours_before_commence <= 0.25

        # R14: Distinguir rol del snapshot (trayectoria vs benchmark de cierre)
        snapshot_role = "closing" if hours_to_commence <= 0.5 else "trajectory"

        fair_prob = outcome_fair["fair_prob"]
        clv_val = clv(soft_odds, fair_prob) if is_valid_closing_benchmark else None

        rows.append(
            {
                "sport_key": sport_key,
                "event_id": s[_S_EVENT],
                "home_team": s[_S_HOME],
                "away_team": s[_S_AWAY],
                "market": s[_S_MARKET],
                "outcome": s[_S_OUTCOME],
                "soft_book": s[_S_BOOK],
                "commence_time": commence,
                "captured_at": captured,
                "hours_to_commence": hours_to_commence,
                "soft_odds": soft_odds,
                "pinnacle_closing_odds": outcome_fair["closing_odds"],
                "pinnacle_closing_last_update": closing_last_update,
                "hours_before_commence": hours_before_commence,
                "pinnacle_fair_prob": fair_prob,
                "clv": clv_val,
                "is_valid_closing_benchmark": is_valid_closing_benchmark,
                "snapshot_role": snapshot_role,
            }
        )
    return rows, skipped


def build_target_rows(con, target: Target) -> tuple[list[dict], int, list[str]]:
    """Orquesta un target: cierre sharp -> devig -> une con snapshots soft -> filas CLV.

    Además de las filas y el nº de descartes, devuelve events_without_closing: la lista
    ordenada y deduplicada de event_ids que tienen snapshots soft pero ningún cierre de
    Pinnacle para ese mercado (no hay fallback silencioso: se hace visible qué eventos
    quedan fuera del cálculo de CLV por completo, no solo cuántas filas).
    """
    fair_by_market = fair_probs_by_market(closing_lines(con, target.sport_key, target.sharp_book))
    soft_rows = soft_snapshots(con, target.sport_key, target.soft_books)
    rows, skipped = build_clv_rows(soft_rows, fair_by_market, target.sport_key)
    events_without_closing = sorted(
        {s[_S_EVENT] for s in soft_rows if (s[_S_EVENT], s[_S_MARKET]) not in fair_by_market}
    )
    return rows, skipped, events_without_closing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", help="Procesar solo este target (por nombre), para debug.")
    args = parser.parse_args(argv)

    load_dotenv()
    config: AppConfig = load_config()

    targets = config.active_targets()
    if args.target:
        targets = [t for t in targets if t.name == args.target]
        if not targets:
            logger.error("target %s no encontrado o inactivo en config.yaml", args.target)
            return 1

    con = get_connection(config.db_path)

    all_rows: list[dict] = []
    total_skipped = 0
    all_events_without_closing: list[str] = []
    for target in targets:
        rows, skipped, events_without_closing = build_target_rows(con, target)
        total_skipped += skipped
        all_rows.extend(rows)
        all_events_without_closing.extend(events_without_closing)
        logger.info(
            "target=%s filas_clv=%d descartadas_sin_cierre=%d eventos_sin_cierre=%s",
            target.name,
            len(rows),
            skipped,
            events_without_closing,
        )

    inserted = replace_clv_snapshots(con, all_rows, [t.sport_key for t in targets])
    con.close()
    logger.info(
        "clv_snapshots reconstruida: %d filas totales, %d descartadas por falta de cierre, "
        "%d eventos sin ningún cierre válido: %s",
        inserted,
        total_skipped,
        len(all_events_without_closing),
        all_events_without_closing,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
