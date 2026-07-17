"""Página de trayectorias: cómo se movió cada cuota soft hacia el cierre de
Pinnacle en un evento concreto, outcome a outcome (nunca mezclados: las
cuotas de outcomes distintos no son comparables)."""

import pandas as pd
import streamlit as st

from dashboard.charts import clv_trajectory_chart, trajectory_chart
from dashboard.queries import events_summary, trajectory_for_event
from dashboard.views.common import chart_help, db_connection, sport_label

TRAJECTORY_HELP = """
Cada línea de color es una casa de apuestas soft y muestra el precio (cuota)
que publicó para este resultado a lo largo del tiempo. La línea discontinua
horizontal es el **precio de cierre de Pinnacle**, la referencia que
consideramos "el precio correcto".

- El eje horizontal son las **horas que faltan para el partido**: la izquierda
  es "faltan muchas horas" y la derecha es "el partido está a punto de empezar".
- **Qué buscar**: momentos en los que una línea de color está POR ENCIMA de la
  discontinua. Ahí la casa soft ofrecía un precio mejor que el cierre de
  Pinnacle — eso es lo que queremos cazar.
"""

CLV_TRAJECTORY_HELP = """
Este gráfico traduce el anterior a **CLV**: cuánto mejor (positivo) o peor
(negativo) era el precio soft comparado con el cierre de Pinnacle, en %.

- La línea discontinua en 0% es el empate: mismo precio que el cierre.
- Un punto en **+2%** significa "si hubieras apostado en ese momento, tu precio
  era un 2% mejor que el cierre". Sostenido en el tiempo, eso es ventaja real.
- Solo aparece si el evento tiene un cierre de Pinnacle fiable (capturado en
  los últimos 15 minutos antes del partido).
"""


def _event_label(row: pd.Series) -> str:
    badge = "CLV ✓" if row["has_valid_benchmark"] else "sin cierre"
    return (
        f"{row['commence_time']:%d %b %H:%M} · {row['home_team']} vs {row['away_team']} "
        f"· {sport_label(row['sport_key'])} · {badge}"
    )


def render() -> None:
    st.title("Trayectorias por evento")
    st.caption(
        "Sigue un partido concreto: qué precios publicaron las casas soft y cómo "
        "se comparan con el cierre de Pinnacle."
    )

    with db_connection() as con:
        summary = events_summary(con)
        if summary.empty:
            st.info("Todavía no hay eventos en clv_snapshots.")
            return

        col1, col2 = st.columns([1, 1])
        sports = sorted(summary["sport_key"].unique())
        sport_filter = col1.pills(
            "Deporte",
            sports,
            format_func=sport_label,
            selection_mode="multi",
        )
        only_valid = col2.segmented_control(
            "Eventos",
            ["Con CLV válido", "Todos"],
            default="Con CLV válido",
            help=(
                "'Con CLV válido' muestra solo eventos con cierre de Pinnacle fiable "
                "(los que permiten medir CLV). 'Todos' incluye eventos futuros o sin cierre."
            ),
        )

        filtered = summary
        if sport_filter:
            filtered = filtered[filtered["sport_key"].isin(sport_filter)]
        if only_valid == "Con CLV válido":
            filtered = filtered[filtered["has_valid_benchmark"]]

        if filtered.empty:
            st.info(
                "Ningún evento cumple el filtro. Prueba 'Todos': los eventos futuros "
                "aún no tienen cierre de Pinnacle, así que no aparecen en 'Con CLV válido'."
            )
            return

        st.caption(f"{len(filtered)} de {len(summary)} eventos.")
        options = {_event_label(row): row["event_id"] for _, row in filtered.iterrows()}
        label = st.selectbox("Evento", list(options.keys()))
        traj = trajectory_for_event(con, options[label])

    event = filtered[filtered["event_id"] == options[label]].iloc[0]
    # La validez del benchmark es por outcome, no por evento: Pinnacle puede no
    # haber actualizado el precio de un outcome concreto cerca del cierre.
    valid_by_outcome = traj.groupby("outcome")["clv"].apply(lambda s: s.notna().any())
    outcomes = sorted(traj["outcome"].unique(), key=lambda o: (not valid_by_outcome[o], o))
    outcome = st.selectbox(
        "Outcome",
        outcomes,
        format_func=lambda o: f"{o} · CLV ✓" if valid_by_outcome[o] else f"{o} · sin cierre fiable",
        help=(
            "Resultado concreto del partido (victoria local, empate...). Cada outcome "
            "tiene sus propias cuotas y su propio cierre de Pinnacle."
        ),
    )
    subset = traj[traj["outcome"] == outcome]

    closing_odds = float(subset["pinnacle_closing_odds"].iloc[0])
    st.subheader(f"Cuota soft vs cierre Pinnacle — {outcome}")
    if not event["has_valid_benchmark"]:
        st.caption(
            ":material/warning: Este evento no tiene cierre fiable todavía: la línea "
            "'cierre Pinnacle' es el último precio capturado y puede seguir moviéndose."
        )
    st.altair_chart(trajectory_chart(subset, closing_odds), width="stretch")
    chart_help(TRAJECTORY_HELP)

    with_clv = subset[subset["clv"].notna()]
    if not with_clv.empty:
        st.subheader("CLV a lo largo del tiempo")
        st.altair_chart(clv_trajectory_chart(with_clv), width="stretch")
        chart_help(CLV_TRAJECTORY_HELP)
    else:
        st.info(
            "Este outcome no tiene cierre de Pinnacle fiable (su último precio se "
            "capturó demasiado pronto antes del kickoff): sin CLV calculable. "
            "Prueba otro outcome del selector."
        )
