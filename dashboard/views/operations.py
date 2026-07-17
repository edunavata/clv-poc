"""Página de operaciones: salud del pipeline de captura, schedule del daemon
y acceso a la tabla cruda del mart."""

import streamlit as st

from config import load_config
from dashboard.charts import capture_growth_line, capture_heatmap
from dashboard.queries import (
    capture_polls,
    poll_timestamps,
    raw_clv_snapshots,
    raw_snapshots,
    snapshot_growth,
)
from dashboard.transforms import detect_gaps, heatmap_frame
from dashboard.views.common import chart_help, db_connection

HEATMAP_HELP = """
Cada celda es un día para un deporte. El color dice cuántas veces capturamos
precios ese día comparado con lo que tocaba (cada 3 horas = 8 al día).

- **Azul oscuro** = día completo, el sistema capturó todo lo planificado.
- **Azul claro** = día incompleto, se perdieron capturas.
- **Sin celda / casi blanco** = día sin capturas (el daemon estuvo parado).

Sirve para fiarse (o no) del resto del dashboard: si hay muchos huecos, los
análisis de CLV se construyen sobre datos incompletos.
"""

GROWTH_HELP = """
Cuántas filas de precios llevamos guardadas en total, día a día y por deporte.

- Cada punto es un día; la línea siempre debe **subir** (nunca borramos datos).
- Un tramo **plano** significa un día sin capturas nuevas — mismo aviso que un
  hueco en el mapa de calor de arriba.
- Es el equivalente "crudo" del gráfico de crecimiento de muestra de la página
  Go/No-Go: aquí se cuenta todo lo capturado, allí solo lo que ya se puede
  puntuar con CLV.
"""


@st.cache_data(ttl=300)
def _upcoming_schedule():
    """Recompute del schedule del daemon (get_events, 0 créditos). Cacheado 5 min
    para no llamar red en cada rerun Streamlit."""
    from client.odds_api import OddsApiClient
    from scheduler.preview import build_schedule_rows

    return build_schedule_rows(OddsApiClient(), load_config())


def render() -> None:
    st.title("Operaciones")

    config = load_config()
    intervals = {t.sport_key: t.poll_interval_hours for t in config.active_targets()}
    expected_per_day = {k: 24 / v for k, v in intervals.items() if v > 0}

    with db_connection() as con:
        polls = capture_polls(con)
        timestamps = poll_timestamps(con)
        growth = snapshot_growth(con)
        raw = raw_clv_snapshots(con)
        raw_odds = raw_snapshots(con)

    st.subheader("Salud de capturas")
    st.caption(
        "Polls por día y deporte vs la cadencia esperada de config.yaml "
        f"({', '.join(f'{k}: {24 / v:.0f}/día' for k, v in intervals.items())}). "
        "Días en claro u oscuro incompleto = gaps del daemon."
    )
    if polls.empty:
        st.info("Todavía no hay capturas en snapshots.")
    else:
        st.altair_chart(
            capture_heatmap(heatmap_frame(polls, expected_per_day)),
            width="stretch",
        )
        chart_help(HEATMAP_HELP)

        st.subheader("Crecimiento de capturas")
        st.altair_chart(capture_growth_line(growth), width="stretch")
        chart_help(GROWTH_HELP)

        gaps = detect_gaps(timestamps, intervals)
        if gaps.empty:
            st.caption("Sin gaps de captura > 2× el intervalo esperado.")
        else:
            st.subheader(f"Gaps de captura detectados ({len(gaps)})")
            st.caption("Huecos > 2× el intervalo de poll esperado del deporte.")
            st.dataframe(gaps, width="stretch", hide_index=True)

    st.subheader("Próximas capturas programadas")
    st.caption(
        "Recompute vía get_events (coste 0 créditos): lo que el daemon programaría con un "
        "discovery en este instante. El jobstore del daemon es en memoria y no se "
        "introspecciona; esto se recalcula (cache 5 min)."
    )
    try:
        schedule_rows = _upcoming_schedule()
    except Exception as exc:  # falta ODDS_API_KEY, red caída, etc.
        st.warning(f"No se pudo recalcular el schedule (¿ODDS_API_KEY, red?): {exc}")
        schedule_rows = []

    if schedule_rows:
        import pandas as pd

        sched_df = pd.DataFrame(schedule_rows)
        sched_df["run_at"] = pd.to_datetime(sched_df["run_at"])
        st.dataframe(sched_df, width="stretch", hide_index=True)
        n_closing = int(sched_df["is_closing"].sum())
        st.caption(f"{len(sched_df)} capturas planificadas, {n_closing} de cierre.")
    else:
        st.info("Sin capturas planificadas (o sin acceso a la API).")

    st.subheader("Datos: CLV calculados (clv_snapshots)")
    st.caption("Cada fila es un precio soft ya comparado con el cierre de Pinnacle.")
    if raw.empty:
        st.info("clv_snapshots está vacía. Corre `uv run python -m analysis.report`.")
    else:
        col1, col2, col3 = st.columns(3)
        sport_filter = col1.multiselect("sport_key", sorted(raw["sport_key"].unique()))
        book_filter = col2.multiselect("soft_book", sorted(raw["soft_book"].unique()))
        role_filter = col3.multiselect("snapshot_role", sorted(raw["snapshot_role"].unique()))
        filtered = raw
        if sport_filter:
            filtered = filtered[filtered["sport_key"].isin(sport_filter)]
        if book_filter:
            filtered = filtered[filtered["soft_book"].isin(book_filter)]
        if role_filter:
            filtered = filtered[filtered["snapshot_role"].isin(role_filter)]
        st.caption(f"{len(filtered)} de {len(raw)} filas.")
        st.dataframe(filtered, width="stretch", hide_index=True)

    st.subheader("Datos: cuotas crudas capturadas (snapshots)")
    st.caption(
        "Cada fila es un precio tal cual lo publicó una casa en un instante de captura, "
        "sin ningún cálculo encima. Es la materia prima de todo lo demás."
    )
    if raw_odds.empty:
        st.info("Todavía no hay capturas en snapshots.")
        return
    col1, col2, col3 = st.columns(3)
    odds_sport = col1.multiselect(
        "sport_key", sorted(raw_odds["sport_key"].unique()), key="odds_sport"
    )
    odds_book = col2.multiselect("book", sorted(raw_odds["book"].unique()), key="odds_book")
    odds_event = col3.text_input(
        "Buscar equipo", key="odds_event", placeholder="p. ej. Inter Miami"
    )
    filtered_odds = raw_odds
    if odds_sport:
        filtered_odds = filtered_odds[filtered_odds["sport_key"].isin(odds_sport)]
    if odds_book:
        filtered_odds = filtered_odds[filtered_odds["book"].isin(odds_book)]
    if odds_event:
        mask = filtered_odds["home_team"].str.contains(
            odds_event, case=False
        ) | filtered_odds["away_team"].str.contains(odds_event, case=False)
        filtered_odds = filtered_odds[mask]
    st.caption(f"{len(filtered_odds)} de {len(raw_odds)} filas.")
    st.dataframe(filtered_odds.head(1000), width="stretch", hide_index=True)
    if len(filtered_odds) > 1000:
        st.caption("Mostrando las 1.000 más recientes; afina los filtros para ver el resto.")
