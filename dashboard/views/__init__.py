"""Páginas del dashboard: una función render() por página.

Cada página abre y cierra su propia conexión read-only en cada rerun
(Streamlit re-ejecuta la página en cada interacción) para leer siempre el
último estado que escriba el daemon, y solo lanza las queries que necesita.
"""
