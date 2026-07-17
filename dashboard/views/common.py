"""Utilidades compartidas por las páginas del dashboard."""

from contextlib import contextmanager

import streamlit as st

from config import load_config
from storage.db import get_connection

# Nombres cortos legibles para sport_keys; fallback al key crudo.
SPORT_LABELS = {
    "soccer_usa_mls": "MLS",
    "baseball_mlb": "MLB",
    "soccer_fifa_world_cup": "Mundial 2026",
}


def sport_label(sport_key: str) -> str:
    return SPORT_LABELS.get(sport_key, sport_key)


def chart_help(text: str) -> None:
    """Explicación plegada de cómo leer el gráfico anterior, para usuarios no
    familiarizados con las visualizaciones. La guía completa está en la página
    'Guía'."""
    with st.expander(":material/help: Cómo leer este gráfico"):
        st.markdown(text)


@contextmanager
def db_connection():
    """Conexión read-only a la BD del config, cerrada aunque la página falle."""
    config = load_config()
    con = get_connection(config.db_path, read_only=True)
    try:
        yield con
    finally:
        con.close()
