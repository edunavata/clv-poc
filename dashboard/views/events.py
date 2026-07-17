"""Página de trayectorias: cómo se movió cada cuota soft hacia el cierre de
Pinnacle en un evento concreto, outcome a outcome (nunca mezclados: las
cuotas de outcomes distintos no son comparables)."""

import streamlit as st

from dashboard.charts import clv_trajectory_chart, trajectory_chart
from dashboard.queries import events, trajectory_for_event
from dashboard.views.common import db_connection


def render() -> None:
    st.title("Trayectorias por evento")

    with db_connection() as con:
        event_rows = events(con)
        if not event_rows:
            st.info("Todavía no hay eventos en clv_snapshots.")
            return

        options = {
            f"{home} vs {away} ({commence:%Y-%m-%d %H:%M})": event_id
            for event_id, home, away, commence in event_rows
        }
        label = st.selectbox("Evento", list(options.keys()))
        traj = trajectory_for_event(con, options[label])

    outcomes = sorted(traj["outcome"].unique())
    outcome = st.selectbox("Outcome", outcomes)
    subset = traj[traj["outcome"] == outcome]

    closing_odds = float(subset["pinnacle_closing_odds"].iloc[0])
    st.subheader(f"Cuota soft vs cierre Pinnacle — {outcome}")
    st.caption("Eje X invertido: el tiempo fluye hacia el cierre (0h) a la derecha.")
    st.altair_chart(trajectory_chart(subset, closing_odds), width="stretch")

    with_clv = subset[subset["clv"].notna()]
    if not with_clv.empty:
        st.subheader("CLV a lo largo del tiempo")
        st.caption("Solo snapshots con benchmark de cierre válido.")
        st.altair_chart(clv_trajectory_chart(with_clv), width="stretch")
    else:
        st.info("Este evento no tiene benchmark de cierre válido: sin CLV calculable.")
