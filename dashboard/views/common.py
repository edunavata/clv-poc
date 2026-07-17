"""Utilidades compartidas por las páginas del dashboard."""

from contextlib import contextmanager

from config import load_config
from storage.db import get_connection


@contextmanager
def db_connection():
    """Conexión read-only a la BD del config, cerrada aunque la página falle."""
    config = load_config()
    con = get_connection(config.db_path, read_only=True)
    try:
        yield con
    finally:
        con.close()
