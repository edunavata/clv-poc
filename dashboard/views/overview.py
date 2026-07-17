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
from dashboard.views.common import chart_help, db_connection

BAR_HELP = """
Cada barra es una casa de apuestas soft. La altura dice, en promedio, cuánto
mejor o peor eran sus precios comparados con el cierre de Pinnacle (el "precio
correcto" de referencia).

- Barra que baja de la línea 0 = precios **peores** que el cierre (lo normal).
- Barra que sube de 0 = precios **mejores** que el cierre = ventaja explotable.
- La rayita vertical negra es el **margen de error** (intervalo de confianza
  95%): el valor real está casi seguro dentro de ese rango. Si la rayita cruza
  el 0, aún no se puede afirmar nada con esa casa.
"""

DIST_HELP = """
Arriba: cada caja resume TODOS los CLV de una casa, no solo su media. La línea
del centro de la caja es el valor típico (mediana); la caja cubre la mitad
central de los casos; los puntos sueltos son casos raros.

Abajo: cuántos snapshots caen en cada rango de CLV. Las barras a la derecha
del 0% son capturas que batieron al cierre.

**Por qué importa**: una media negativa puede esconder una minoría de capturas
muy buenas (cola derecha). Si toda la masa está a la izquierda del 0, no hay
nada que rascar.
"""

HORIZON_HELP = """
Lo mismo que el gráfico de barras, pero separado por **cuántas horas faltaban
para el partido** cuando se capturó el precio.

- Cada grupo del eje horizontal es una franja: "0-1h" = capturas en la última
  hora, "24h+" = capturas con más de un día de antelación.
- **Qué buscar**: si alguna franja tiene puntos por encima de 0 con su margen
  de error también por encima, esa sería LA ventana donde apostar.
"""

SPORT_HELP = """
El mismo CLV medio, separado por competición. Se separan porque no son
comparables: un partido de fútbol tiene 3 resultados posibles y uno de béisbol
2, y eso cambia cómo se calculan las probabilidades.

También delata si un resultado global viene dominado por un solo deporte con
muchos datos (mira la 'n' en el tooltip de cada barra).
"""

GROWTH_HELP = """
Cuántos CLV medibles llevamos acumulados día a día. La línea discontinua es la
meta de 100: por debajo de eso, cualquier conclusión es prematura por pura
falta de datos. La pendiente dice a qué ritmo crece la evidencia.
"""


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
    chart_help(BAR_HELP)
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
    chart_help(DIST_HELP)

    st.subheader("CLV por horizonte al kickoff")
    st.caption("¿A qué distancia del cierre aparece el edge, si existe?")
    st.altair_chart(clv_vs_horizon(bucket_hours(values)), width="stretch")
    chart_help(HORIZON_HELP)

    st.subheader("CLV por deporte")
    st.altair_chart(clv_by_sport(sport_stats), width="content")
    chart_help(SPORT_HELP)

    st.subheader("Crecimiento de la muestra")
    st.altair_chart(sample_growth_line(growth, SAMPLE_TARGET), width="stretch")
    chart_help(GROWTH_HELP)
