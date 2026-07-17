"""Página Go/No-Go: la decisión del POC en una pantalla.

¿Baten las soft books al cierre de Pinnacle de forma consistente? KPIs de
muestra arriba, luego CLV por book con intervalos de confianza, distribución
completa (la media sola engaña), horizonte temporal y desglose por deporte.
"""

import streamlit as st

from dashboard.charts import (
    clv_by_book_bar,
    clv_by_sport,
    clv_distribution,
    clv_vs_horizon,
    sample_growth_line,
)
from dashboard.queries import (
    clv_stats_by_book,
    clv_stats_by_sport_book,
    clv_values,
    kpi_summary,
    sample_growth,
)
from dashboard.transforms import SAMPLE_TARGET, book_stats_frame, bucket_hours
from dashboard.views.common import db_connection


def render() -> None:
    st.title("Go / No-Go CLV")
    st.caption(
        "Criterio (notas/como-funciona-la-poc.md §7): CLV medio por soft book "
        "sobre benchmarks de cierre válidos (sondeo ≤ 15 min antes del kickoff). "
        "CLV > 0 = el precio capturado batió al cierre de Pinnacle."
    )

    with db_connection() as con:
        kpis = kpi_summary(con)
        stats = clv_stats_by_book(con)
        values = clv_values(con)
        sport_stats = clv_stats_by_sport_book(con)
        growth = sample_growth(con)

    n_valid = int(kpis["n_valid"])
    if n_valid == 0:
        st.info("Todavía no hay CLVs con benchmark de cierre válido en clv_snapshots.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "CLVs válidos",
        n_valid,
        delta=f"{n_valid - SAMPLE_TARGET:+d} vs meta {SAMPLE_TARGET}",
        delta_color="normal" if n_valid >= SAMPLE_TARGET else "inverse",
    )
    c2.metric("CLV medio global", f"{kpis['avg_clv']:+.2%}")
    c3.metric("Hit-rate (CLV > 0)", f"{kpis['hit_rate']:.0%}")
    c4.metric("Días capturando", int(kpis["days_capturing"]))
    c5.metric("Eventos con benchmark", int(kpis["n_events"]))

    if n_valid < SAMPLE_TARGET:
        st.warning(
            f"Muestra pequeña: {n_valid} CLVs válidos (meta {SAMPLE_TARGET}). "
            "Ninguna conclusión go/no-go todavía."
        )

    st.subheader("CLV medio por soft book (CI 95%)")
    st.altair_chart(clv_by_book_bar(book_stats_frame(stats)), width="stretch")
    st.dataframe(
        book_stats_frame(stats),
        width="stretch",
        hide_index=True,
        column_config={
            "soft_book": "book",
            "n": st.column_config.NumberColumn("n"),
            "avg_clv": st.column_config.NumberColumn("CLV medio", format="percent"),
            "std_clv": st.column_config.NumberColumn("std", format="%.3f"),
            "hit_rate": st.column_config.NumberColumn("hit-rate", format="percent"),
            "median_clv": st.column_config.NumberColumn("mediana", format="percent"),
            "stderr": None,
            "ci_low": st.column_config.NumberColumn("CI95 inf", format="percent"),
            "ci_high": st.column_config.NumberColumn("CI95 sup", format="percent"),
        },
    )

    st.subheader("Distribución de CLV")
    st.caption("La media puede ocultar una cola positiva explotable (o al revés).")
    st.altair_chart(clv_distribution(values), width="stretch")

    st.subheader("CLV por horizonte al kickoff")
    st.caption("¿A qué distancia del cierre aparece el edge, si existe?")
    st.altair_chart(clv_vs_horizon(bucket_hours(values)), width="stretch")

    st.subheader("CLV por deporte")
    st.altair_chart(clv_by_sport(sport_stats), width="content")

    st.subheader("Crecimiento de la muestra")
    st.altair_chart(sample_growth_line(growth, SAMPLE_TARGET), width="stretch")
