"""Capa de gráficos Altair del dashboard.

Una función por gráfico: DataFrame (ya transformado) entra, alt.Chart sale.
Sin Streamlit ni queries aquí.

Colores: primeros 4 slots de la paleta categórica validada (CVD-safe en ese
orden; el orden ES el mecanismo de seguridad, no cosmética). El color sigue
al book (entidad), nunca a su posición en un chart concreto, así que el
mapeo book->color es fijo y compartido por todos los gráficos.
"""

import altair as alt
import pandas as pd

# Slots categóricos en orden validado (validate_palette.js: todos los checks PASS
# en light; magenta/amarillo <3:1 de contraste => siempre tooltips + tabla al lado).
CATEGORICAL = ["#2a78d6", "#008300", "#e87ba4", "#eda100", "#1baf7a", "#eb6834"]

# Books conocidos en orden fijo de asignación de color. Books nuevos que aparezcan
# en datos se añaden por orden alfabético detrás, sin repintar los existentes.
KNOWN_BOOKS = ["betvictor", "marathonbet", "williamhill", "winamax_fr"]

PCT_AXIS = alt.Axis(format="+.1%")
PCT_FMT = "+.2%"

# Escala secuencial azul (magnitud) para el heatmap: light->dark, un solo tono.
SEQUENTIAL_BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"]


# Sports conocidos, mismo mecanismo de color estable que los books.
KNOWN_SPORTS = ["baseball_mlb", "soccer_fifa_world_cup", "soccer_usa_mls"]


def _stable_scale(values: pd.Series, known: list[str]) -> alt.Scale:
    """Escala color->entidad estable: dominio fijo por lista conocida + extras
    alfabéticos al final, para que el color siga a la entidad en todos los
    gráficos y no cambie al filtrar."""
    extras = sorted(set(values) - set(known))
    domain = [v for v in known if v in set(values)] + extras
    return alt.Scale(domain=domain, range=CATEGORICAL[: len(domain)])


def book_scale(books: pd.Series) -> alt.Scale:
    return _stable_scale(books, KNOWN_BOOKS)


def sport_scale(sports: pd.Series) -> alt.Scale:
    return _stable_scale(sports, KNOWN_SPORTS)


def _zero_rule() -> alt.Chart:
    """Línea de referencia CLV=0: la frontera go/no-go de cada gráfico de CLV."""
    return alt.Chart(pd.DataFrame({"y": [0.0]})).mark_rule(strokeDash=[4, 3]).encode(y="y:Q")


def clv_by_book_bar(stats: pd.DataFrame) -> alt.Chart:
    """CLV medio por soft book con intervalo de confianza 95%."""
    base = alt.Chart(stats)
    bars = base.mark_bar(size=28, cornerRadiusEnd=4).encode(
        x=alt.X("soft_book:N", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("avg_clv:Q", title="CLV medio", axis=PCT_AXIS),
        color=alt.Color("soft_book:N", scale=book_scale(stats["soft_book"]), legend=None),
        tooltip=[
            alt.Tooltip("soft_book", title="book"),
            alt.Tooltip("n", title="n"),
            alt.Tooltip("avg_clv", title="CLV medio", format=PCT_FMT),
            alt.Tooltip("median_clv", title="mediana", format=PCT_FMT),
            alt.Tooltip("hit_rate", title="hit-rate", format=".0%"),
            alt.Tooltip("ci_low", title="CI95 inf", format=PCT_FMT),
            alt.Tooltip("ci_high", title="CI95 sup", format=PCT_FMT),
        ],
    )
    errors = base.mark_rule(strokeWidth=2).encode(
        x="soft_book:N", y="ci_low:Q", y2="ci_high:Q"
    )
    return (bars + errors + _zero_rule()).properties(height=280)


def clv_distribution(values: pd.DataFrame) -> alt.Chart:
    """Distribución de CLV por book: boxplot + histograma. La media sola puede
    ocultar una cola positiva explotable."""
    scale = book_scale(values["soft_book"])
    box = (
        alt.Chart(values)
        .mark_boxplot(size=22)
        .encode(
            x=alt.X("clv:Q", title="CLV", axis=PCT_AXIS),
            y=alt.Y("soft_book:N", title=None),
            color=alt.Color("soft_book:N", scale=scale, legend=None),
        )
        .properties(height=160)
    )
    hist = (
        alt.Chart(values)
        .mark_bar(binSpacing=2)
        .encode(
            x=alt.X("clv:Q", bin=alt.Bin(maxbins=30), title="CLV", axis=PCT_AXIS),
            y=alt.Y("count()", title="snapshots"),
            color=alt.Color("soft_book:N", scale=scale, title="book"),
            tooltip=[
                alt.Tooltip("soft_book", title="book"),
                alt.Tooltip("count()", title="snapshots"),
            ],
        )
        .properties(height=200)
    )
    return alt.vconcat(box, hist).resolve_scale(color="shared")


def clv_vs_horizon(buckets: pd.DataFrame) -> alt.Chart:
    """CLV medio + CI95 por bucket de horas hasta el kickoff: ¿a qué distancia
    del cierre hay edge?"""
    order = list(buckets["bucket"].cat.categories)
    scale = book_scale(buckets["soft_book"])
    base = alt.Chart(buckets)
    points = base.mark_point(size=90, filled=True).encode(
        x=alt.X("bucket:N", sort=order, title="horas hasta el kickoff", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("avg_clv:Q", title="CLV medio", axis=PCT_AXIS),
        color=alt.Color("soft_book:N", scale=scale, title="book"),
        xOffset="soft_book:N",
        tooltip=[
            alt.Tooltip("soft_book", title="book"),
            alt.Tooltip("bucket", title="horizonte"),
            alt.Tooltip("n", title="n"),
            alt.Tooltip("avg_clv", title="CLV medio", format=PCT_FMT),
            alt.Tooltip("ci_low", title="CI95 inf", format=PCT_FMT),
            alt.Tooltip("ci_high", title="CI95 sup", format=PCT_FMT),
        ],
    )
    errors = base.mark_rule(strokeWidth=2).encode(
        x=alt.X("bucket:N", sort=order),
        y="ci_low:Q",
        y2="ci_high:Q",
        color=alt.Color("soft_book:N", scale=scale),
        xOffset="soft_book:N",
    )
    return (points + errors + _zero_rule()).properties(height=300)


def clv_by_sport(stats: pd.DataFrame) -> alt.Chart:
    """CLV medio book x deporte. El h2h 3-way de fútbol y el 2-way de MLB
    tienen devig distinto: no se promedian juntos."""
    # Horizontal + facet por fila: los nombres de books son largos y en
    # vertical facetado se solapan.
    return (
        alt.Chart(stats)
        .mark_bar(size=16, cornerRadiusEnd=4)
        .encode(
            y=alt.Y("soft_book:N", title=None),
            x=alt.X("avg_clv:Q", title="CLV medio", axis=PCT_AXIS),
            color=alt.Color("soft_book:N", scale=book_scale(stats["soft_book"]), legend=None),
            row=alt.Row("sport_key:N", title=None, header=alt.Header(labelFontWeight="bold")),
            tooltip=[
                alt.Tooltip("sport_key", title="deporte"),
                alt.Tooltip("soft_book", title="book"),
                alt.Tooltip("n", title="n"),
                alt.Tooltip("avg_clv", title="CLV medio", format=PCT_FMT),
                alt.Tooltip("hit_rate", title="hit-rate", format=".0%"),
            ],
        )
        .properties(height=110, width=520)
    )


def sample_growth_line(growth: pd.DataFrame, target: int = 100) -> alt.Chart:
    """N de CLVs válidos acumulado por día, con la meta de muestra como regla."""
    line = (
        alt.Chart(growth)
        .mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60, filled=True))
        .encode(
            x=alt.X("day:T", title=None),
            y=alt.Y("cumulative_n:Q", title="CLVs válidos acumulados"),
            tooltip=[
                alt.Tooltip("day:T", title="día"),
                alt.Tooltip("n_valid", title="nuevos"),
                alt.Tooltip("cumulative_n", title="acumulado"),
            ],
        )
    )
    rule = (
        alt.Chart(pd.DataFrame({"y": [target], "label": [f"meta N={target}"]}))
        .mark_rule(strokeDash=[4, 3])
        .encode(y="y:Q", tooltip=alt.Tooltip("label", title=None))
    )
    return (line + rule).properties(height=260)


# Color reservado para Pinnacle en la trayectoria: gris oscuro neutro, fuera de
# la paleta categórica de books, para que la referencia sharp se lea distinta de
# cualquier soft book y no compita con ellos por atención.
PINNACLE_COLOR = "#3a3a3a"
PINNACLE_LABEL = "Pinnacle"


def trajectory_chart(
    traj: pd.DataFrame,
    closing_odds: float,
    pinnacle: pd.DataFrame | None = None,
) -> alt.Chart:
    """Trayectoria de cuotas soft de un outcome vs Pinnacle.

    Eje X invertido: el tiempo fluye hacia el cierre (0h) a la derecha.
    Shape distingue snapshots de trayectoria vs ráfaga de cierre.
    Si se pasa ``pinnacle`` (cuota sharp en vivo snapshot a snapshot), se dibuja
    su curva además de la regla horizontal del cierre fijo: así se ve cómo se
    movió la referencia, no solo dónde acabó.
    """
    scale = book_scale(traj["soft_book"])
    x = alt.X(
        "hours_to_commence:Q",
        title="horas hasta el kickoff (0 = cierre)",
        scale=alt.Scale(reverse=True),
    )
    lines = (
        alt.Chart(traj)
        .mark_line(strokeWidth=2)
        .encode(x=x, y=alt.Y("soft_odds:Q", title="cuota", scale=alt.Scale(zero=False)),
                color=alt.Color("soft_book:N", scale=scale, title="book"))
    )
    points = (
        alt.Chart(traj)
        .mark_point(size=70, filled=True)
        .encode(
            x=x,
            y="soft_odds:Q",
            # legend=None: la leyenda de books ya la aporta la capa de líneas
            # (title="book"); sin esto los puntos generan una segunda leyenda
            # "soft_book" duplicada.
            color=alt.Color("soft_book:N", scale=scale, legend=None),
            shape=alt.Shape("snapshot_role:N", title="rol"),
            tooltip=[
                alt.Tooltip("soft_book", title="book"),
                alt.Tooltip("soft_odds", title="cuota", format=".2f"),
                alt.Tooltip("hours_to_commence", title="h al kickoff", format=".1f"),
                alt.Tooltip("snapshot_role", title="rol"),
                alt.Tooltip("captured_at:T", title="capturado"),
            ],
        )
    )
    closing = (
        alt.Chart(pd.DataFrame({"y": [closing_odds], "label": ["cierre Pinnacle"]}))
        .mark_rule(strokeWidth=2, strokeDash=[6, 3])
        .encode(y="y:Q", tooltip=[alt.Tooltip("label", title=None), alt.Tooltip("y", title="cuota", format=".2f")])
    )
    layers = [lines, points, closing]

    if pinnacle is not None and not pinnacle.empty:
        # Escala de color propia (un solo miembro) para que Pinnacle aparezca en
        # su propia leyenda sin robar un slot de la paleta de books.
        pin = pinnacle.assign(series=PINNACLE_LABEL)
        pin_scale = alt.Scale(domain=[PINNACLE_LABEL], range=[PINNACLE_COLOR])
        pin_color = alt.Color("series:N", scale=pin_scale, title=None)
        pin_line = (
            alt.Chart(pin)
            .mark_line(strokeWidth=2.5)
            .encode(x=x, y=alt.Y("pinnacle_odds:Q", scale=alt.Scale(zero=False)), color=pin_color)
        )
        pin_points = (
            alt.Chart(pin)
            .mark_point(size=60, filled=True, shape="diamond")
            .encode(
                x=x,
                y="pinnacle_odds:Q",
                color=alt.Color("series:N", scale=pin_scale, legend=None),
                tooltip=[
                    alt.Tooltip("series", title=None),
                    alt.Tooltip("pinnacle_odds", title="cuota", format=".2f"),
                    alt.Tooltip("hours_to_commence", title="h al kickoff", format=".1f"),
                    alt.Tooltip("captured_at:T", title="capturado"),
                ],
            )
        )
        layers += [pin_line, pin_points]

    # color independiente: books y Pinnacle son dos leyendas distintas (dos
    # escalas), no una sola paleta compartida.
    return alt.layer(*layers).resolve_scale(color="independent").properties(height=320)


def capture_growth_line(growth: pd.DataFrame) -> alt.Chart:
    """Snapshots crudos acumulados por día y deporte: la línea debe subir cada
    día que el daemon capturó; un tramo plano es un día sin capturas."""
    return (
        alt.Chart(growth)
        .mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60, filled=True))
        .encode(
            x=alt.X("day:T", title=None),
            y=alt.Y("cumulative_rows:Q", title="snapshots acumulados"),
            color=alt.Color("sport_key:N", scale=sport_scale(growth["sport_key"]), title="deporte"),
            tooltip=[
                alt.Tooltip("day:T", title="día"),
                alt.Tooltip("sport_key", title="deporte"),
                alt.Tooltip("n_rows", title="nuevas"),
                alt.Tooltip("cumulative_rows", title="acumulado"),
            ],
        )
        .properties(height=260)
    )


def clv_trajectory_chart(traj: pd.DataFrame) -> alt.Chart:
    """CLV del outcome a lo largo del tiempo (mismo eje X invertido que la
    trayectoria de cuotas): cuándo se pudo capturar edge en este evento."""
    scale = book_scale(traj["soft_book"])
    x = alt.X(
        "hours_to_commence:Q",
        title="horas hasta el kickoff (0 = cierre)",
        scale=alt.Scale(reverse=True),
    )
    lines = (
        alt.Chart(traj)
        .mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60, filled=True))
        .encode(
            x=x,
            y=alt.Y("clv:Q", title="CLV", axis=PCT_AXIS),
            color=alt.Color("soft_book:N", scale=scale, title="book"),
            tooltip=[
                alt.Tooltip("soft_book", title="book"),
                alt.Tooltip("clv", title="CLV", format=PCT_FMT),
                alt.Tooltip("hours_to_commence", title="h al kickoff", format=".1f"),
                alt.Tooltip("captured_at:T", title="capturado"),
            ],
        )
    )
    return (lines + _zero_rule()).properties(height=260)


def capture_heatmap(heat: pd.DataFrame) -> alt.Chart:
    """Polls por día x sport. Escala secuencial anclada a lo esperado
    (ratio 1.0 = cadencia completa); los días a 0 delatan gaps."""
    return (
        alt.Chart(heat)
        .mark_rect(stroke="#fcfcfb", strokeWidth=2)
        .encode(
            # Ordinal, no temporal: cada día es una celda discreta. Con eje T
            # continuo los rects se estiran hasta el siguiente dato y los gaps
            # desaparecen visualmente.
            x=alt.X(
                "yearmonthdate(day):O",
                title=None,
                axis=alt.Axis(format="%d %b", labelAngle=-45),
            ),
            y=alt.Y("sport_key:N", title=None),
            color=alt.Color(
                "ratio:Q",
                title="polls / esperado",
                scale=alt.Scale(range=SEQUENTIAL_BLUES, domain=[0, 1.2], clamp=True),
            ),
            tooltip=[
                alt.Tooltip("day:T", title="día"),
                alt.Tooltip("sport_key", title="deporte"),
                alt.Tooltip("polls", title="polls"),
                alt.Tooltip("rows", title="filas"),
                alt.Tooltip("ratio", title="vs esperado", format=".0%"),
            ],
        )
        .properties(height=140)
    )
