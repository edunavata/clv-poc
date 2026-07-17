"""Transformaciones pandas puras para el dashboard.

Sin Streamlit, sin Altair y sin DB: DataFrames entran, DataFrames salen,
para que cada shaping sea testable sin levantar la UI.
"""

import numpy as np
import pandas as pd

# Buckets de horas hasta el kickoff. El edge de las soft books puede depender
# de a qué distancia del cierre se captura el precio.
HOUR_BUCKET_EDGES = [0, 1, 3, 6, 12, 24, float("inf")]
HOUR_BUCKET_LABELS = ["0-1h", "1-3h", "3-6h", "6-12h", "12-24h", "24h+"]

# z para un intervalo de confianza del 95% sobre la media (aprox normal).
Z_95 = 1.96

SAMPLE_TARGET = 100


def _add_ci(df: pd.DataFrame) -> pd.DataFrame:
    """Añade stderr y ci_low/ci_high (95%) a un frame con avg_clv, std_clv, n.

    stddev_samp con n=1 devuelve NULL en DuckDB; el CI queda NaN y el chart
    simplemente no pinta la barra de error.
    """
    df = df.copy()
    df["stderr"] = df["std_clv"] / np.sqrt(df["n"])
    df["ci_low"] = df["avg_clv"] - Z_95 * df["stderr"]
    df["ci_high"] = df["avg_clv"] + Z_95 * df["stderr"]
    return df


def book_stats_frame(stats: pd.DataFrame) -> pd.DataFrame:
    """Stats por book (de clv_stats_by_book) con intervalo de confianza 95%."""
    return _add_ci(stats)


def bucket_hours(values: pd.DataFrame) -> pd.DataFrame:
    """Agrega CLVs individuales (de clv_values) por bucket de horas al kickoff x book.

    Devuelve columnas: bucket (categoría ordenada), soft_book, n, avg_clv,
    std_clv, stderr, ci_low, ci_high.
    """
    df = values.copy()
    df["bucket"] = pd.cut(
        df["hours_to_commence"],
        bins=HOUR_BUCKET_EDGES,
        labels=HOUR_BUCKET_LABELS,
        right=False,
    )
    grouped = (
        df.groupby(["bucket", "soft_book"], observed=True)["clv"]
        .agg(n="count", avg_clv="mean", std_clv="std")
        .reset_index()
    )
    return _add_ci(grouped)


def detect_gaps(
    timestamps: pd.DataFrame, expected_interval_hours: dict[str, float]
) -> pd.DataFrame:
    """Gaps de captura por sport: huecos > 2x el intervalo de poll esperado.

    timestamps: frame (sport_key, captured_at) de poll_timestamps.
    expected_interval_hours: sport_key -> poll_interval_hours de config.yaml;
    sports sin entrada usan el peor intervalo conocido (conservador).
    """
    fallback = max(expected_interval_hours.values(), default=3.0)
    out = []
    for sport, group in timestamps.groupby("sport_key"):
        threshold = 2 * expected_interval_hours.get(sport, fallback)
        ts = group["captured_at"].sort_values().reset_index(drop=True)
        deltas = ts.diff().dt.total_seconds() / 3600
        for i in np.flatnonzero(deltas > threshold):
            out.append(
                {
                    "sport_key": sport,
                    "gap_start": ts[i - 1],
                    "gap_end": ts[i],
                    "gap_hours": round(deltas[i], 1),
                }
            )
    return pd.DataFrame(out, columns=["sport_key", "gap_start", "gap_end", "gap_hours"])


def heatmap_frame(polls: pd.DataFrame, expected_per_day: dict[str, float]) -> pd.DataFrame:
    """Prepara el frame del heatmap día x sport con días vacíos materializados a 0.

    Sin este relleno, los días sin captura no existen como filas y los gaps
    quedan invisibles en el chart. Rango: del primer día de captura de cada
    sport hasta el último día global.
    """
    if polls.empty:
        return polls.assign(ratio=pd.Series(dtype=float))
    df = polls.copy()
    df["day"] = pd.to_datetime(df["day"])
    last_day = df["day"].max()
    filled = []
    for sport, group in df.groupby("sport_key"):
        days = pd.date_range(group["day"].min(), last_day, freq="D")
        base = pd.DataFrame({"day": days, "sport_key": sport})
        merged = base.merge(group, on=["day", "sport_key"], how="left")
        merged[["polls", "rows"]] = merged[["polls", "rows"]].fillna(0).astype(int)
        filled.append(merged)
    out = pd.concat(filled, ignore_index=True)
    expected = out["sport_key"].map(expected_per_day)
    out["ratio"] = np.where(expected > 0, out["polls"] / expected, np.nan)
    return out


def sample_progress(growth: pd.DataFrame) -> dict:
    """Resumen del tracker de muestra: N actual y % hacia SAMPLE_TARGET."""
    if growth.empty:
        return {"n": 0, "target": SAMPLE_TARGET, "pct": 0.0}
    n = int(growth["cumulative_n"].iloc[-1])
    return {"n": n, "target": SAMPLE_TARGET, "pct": min(n / SAMPLE_TARGET, 1.0)}
