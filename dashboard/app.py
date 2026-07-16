"""Dashboard local Streamlit: visualiza data/odds.duckdb.

Corre con `uv run streamlit run dashboard/app.py` desde la raíz del repo
(igual que scheduler/capture.py y analysis/report.py, que asumen cwd=repo root
para resolver el db_path relativo de config.yaml).

La conexión se abre y cierra en cada rerun del script (Streamlit re-ejecuta
todo el archivo en cada interacción) en vez de cachearse, para que el
dashboard siempre lea el estado más reciente que vaya escribiendo el daemon.
"""

import sys
from pathlib import Path

# `streamlit run` ejecuta el binario del entry point directamente (no `python -m`),
# así que no añade la raíz del repo a sys.path como sí hace `-m scheduler.capture`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from config import load_config, load_dotenv
from dashboard.queries import (
    capture_health,
    clv_by_soft_book,
    events,
    raw_clv_snapshots,
    trajectory_for_event,
)
from storage.db import get_connection

st.set_page_config(page_title="CLV POC", layout="wide")

# La sección "Próximas capturas" llama a get_events (necesita ODDS_API_KEY).
load_dotenv()

config = load_config()
con = get_connection(config.db_path, read_only=True)


@st.cache_data(ttl=300)
def _upcoming_schedule():
    """Recompute del schedule del daemon (get_events, 0 créditos). Cacheado 5 min
    para no llamar a la red en cada rerun de Streamlit."""
    from client.odds_api import OddsApiClient
    from scheduler.preview import build_schedule_rows

    return build_schedule_rows(OddsApiClient(), load_config())

st.title("CLV POC — Edge A")

st.header("Go / No-Go: CLV medio por soft book")
st.caption(
    "Criterio del proyecto (notas/como-funciona-la-poc.md §7): tras 1-2 semanas de "
    "captura continua, ¿el CLV medio es consistentemente positivo? Solo cuenta "
    "benchmarks de cierre válidos (is_valid_closing_benchmark)."
)

clv_rows = clv_by_soft_book(con)
if clv_rows:
    clv_df = pd.DataFrame(
        clv_rows, columns=["soft_book", "n", "avg_clv", "min_clv", "max_clv"]
    ).set_index("soft_book")
    total_n = int(clv_df["n"].sum())
    if total_n < 100:
        st.warning(f"Muestra pequeña: {total_n} filas válidas en total. No sacar conclusiones todavía.")
    st.bar_chart(clv_df["avg_clv"])
    st.dataframe(clv_df)
else:
    st.info("Todavía no hay benchmarks de cierre válidos en clv_snapshots.")

st.header("Trayectoria por evento")
event_rows = events(con)
if event_rows:
    options = {
        f"{home} vs {away} ({commence:%Y-%m-%d %H:%M})": event_id
        for event_id, home, away, commence in event_rows
    }
    label = st.selectbox("Evento", list(options.keys()))
    selected_event_id = options[label]

    traj_rows = trajectory_for_event(con, selected_event_id)
    traj_df = pd.DataFrame(
        traj_rows,
        columns=[
            "soft_book",
            "hours_to_commence",
            "soft_odds",
            "pinnacle_closing_odds",
            "snapshot_role",
            "captured_at",
        ],
    )
    pivot = traj_df.pivot_table(index="hours_to_commence", columns="soft_book", values="soft_odds")
    pivot["pinnacle_closing"] = traj_df.groupby("hours_to_commence")["pinnacle_closing_odds"].first()
    st.line_chart(pivot)
    st.caption("Eje X: horas hasta el inicio del partido (baja hacia 0 = cierre).")
else:
    st.info("Todavía no hay eventos en clv_snapshots.")

st.header("Próximas capturas programadas")
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
    sched_df = pd.DataFrame(schedule_rows)
    sched_df["run_at"] = pd.to_datetime(sched_df["run_at"])
    view = sched_df[["target", "run_at", "role", "events_desc"]].rename(
        columns={"run_at": "run_at (UTC)", "events_desc": "evento(s)"}
    )
    st.dataframe(view, width="stretch")
    n_closing = int(sched_df["is_closing"].sum())
    st.caption(
        f"{len(sched_df)} capturas ({n_closing} cierre, {len(sched_df) - n_closing} "
        "trayectoria) · coste 0 créditos."
    )
else:
    st.info("Sin capturas próximas (o no se pudo consultar la API).")

st.header("Salud de captura")
health_rows = capture_health(con)
if health_rows:
    health_df = pd.DataFrame(health_rows, columns=["day", "sport_key", "n"])
    health_pivot = health_df.pivot_table(index="day", columns="sport_key", values="n", fill_value=0)
    st.bar_chart(health_pivot)
else:
    st.info("Todavía no hay filas en snapshots.")

st.header("Tabla cruda (clv_snapshots)")
raw_df = raw_clv_snapshots(con)
soft_book_filter = st.multiselect("soft_book", sorted(raw_df["soft_book"].unique()))
role_filter = st.multiselect("snapshot_role", sorted(raw_df["snapshot_role"].unique()))
filtered = raw_df
if soft_book_filter:
    filtered = filtered[filtered["soft_book"].isin(soft_book_filter)]
if role_filter:
    filtered = filtered[filtered["snapshot_role"].isin(role_filter)]
st.dataframe(filtered, width="stretch")

con.close()
