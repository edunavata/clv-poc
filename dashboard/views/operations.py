"""Página de operaciones: salud del pipeline de captura, schedule del daemon
y acceso a la tabla cruda del mart."""

import streamlit as st

from config import load_config
from dashboard.charts import capture_heatmap
from dashboard.queries import capture_polls, poll_timestamps, raw_clv_snapshots
from dashboard.transforms import detect_gaps, heatmap_frame
from dashboard.views.common import db_connection


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
        raw = raw_clv_snapshots(con)

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

    st.subheader("Tabla raw: clv_snapshots")
    if raw.empty:
        st.info("clv_snapshots está vacía. Corre `uv run python -m analysis.report`.")
        return
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
    st.dataframe(filtered, width="stretch", hide_index=True)
