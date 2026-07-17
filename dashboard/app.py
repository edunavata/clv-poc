"""Dashboard local Streamlit: visualiza data/odds.duckdb.

Corre con `uv run streamlit run dashboard/app.py` desde la raíz del repo
(igual que scheduler/capture.py y analysis/report.py, que asumen cwd=repo root
para resolver el db_path relativo de config.yaml).

Cada página abre y cierra su conexión en cada rerun (Streamlit re-ejecuta la
página en cada interacción) en vez de cachearla, para que el dashboard siempre
lea el estado más reciente que vaya escribiendo el daemon.
"""

import sys
from pathlib import Path

# `streamlit run` ejecuta el binario del entry point directamente (no `python -m`),
# así que no añade la raíz del repo a sys.path como sí hace `-m scheduler.capture`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from config import load_dotenv
from dashboard.views import events, guide, operations, overview

st.set_page_config(page_title="CLV POC", layout="wide")

# La página de operaciones llama a get_events (necesita ODDS_API_KEY).
load_dotenv()

pages = [
    st.Page(overview.render, title="Go / No-Go", icon=":material/flag:", default=True),
    st.Page(events.render, title="Trayectorias", icon=":material/show_chart:", url_path="events"),
    st.Page(
        operations.render, title="Operaciones", icon=":material/monitor_heart:",
        url_path="operations",
    ),
    st.Page(guide.render, title="Guía", icon=":material/menu_book:", url_path="guide"),
]

st.navigation(pages).run()
