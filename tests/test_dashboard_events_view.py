"""Regresión de la página de Trayectorias (dashboard/views/events.py).

Guarda el bug del selector de eventos: sin key= estable en el st.selectbox
"Evento", la primera interacción con el filtro de arriba reconstruía las
opciones y Streamlit devolvía la selección al índice 0, así que no se podía
abrir un evento "sin cierre" (sin CLV válido).

No se reproduce el comportamiento stateful de Streamlit (frágil y no
determinista con datasets pequeños): se afirma directamente que el widget
renderizado lleva su key — que es exactamente lo que arregla el bug — y que un
evento sin cierre fiable se pinta sin excepción.
"""

from datetime import datetime
from types import SimpleNamespace

import duckdb
import pytest
from streamlit.testing.v1 import AppTest

from storage.db import CLV_SNAPSHOTS_SCHEMA


def _seed_row(con, *, event_id, home, valid, outcome, soft_odds, clv):
    """Una fila de clv_snapshots; valid controla is_valid_closing_benchmark."""
    con.execute(
        """
        INSERT INTO clv_snapshots (
            sport_key, event_id, home_team, away_team, market, outcome,
            soft_book, commence_time, captured_at, hours_to_commence,
            soft_odds, pinnacle_closing_odds, pinnacle_closing_last_update,
            hours_before_commence, pinnacle_fair_prob, clv,
            is_valid_closing_benchmark, snapshot_role
        ) VALUES (?, ?, ?, 'Away FC', 'h2h', ?, 'bookA', ?, ?, ?, ?, 2.0, ?, ?, 0.5, ?, ?, 'closing')
        """,
        [
            "soccer_usa_mls", event_id, home, outcome,
            datetime(2026, 7, 20, 0, 0), datetime(2026, 7, 19, 23, 0),
            1.0, soft_odds, datetime(2026, 7, 19, 23, 0), 1.0, clv, valid,
        ],
    )


@pytest.fixture
def events_db(tmp_path):
    """BD temporal con un evento con CLV válido y otro sin cierre fiable."""
    db = tmp_path / "odds.duckdb"
    con = duckdb.connect(str(db))
    con.execute(CLV_SNAPSHOTS_SCHEMA)
    _seed_row(con, event_id="valid1", home="Valid Home", valid=True,
              outcome="Valid Home", soft_odds=2.10, clv=0.05)
    _seed_row(con, event_id="nocierre1", home="Pending Home", valid=False,
              outcome="Pending Home", soft_odds=1.95, clv=None)
    con.close()
    return str(db)


def _run_events_page(db_path, monkeypatch):
    """AppTest de events.render con la BD temporal inyectada vía load_config."""
    import dashboard.views.common as common

    monkeypatch.setattr(common, "load_config", lambda: SimpleNamespace(db_path=db_path))

    def script():
        from dashboard.views import events

        events.render()

    return AppTest.from_function(script, default_timeout=30).run()


def test_event_selectbox_has_stable_key(events_db, monkeypatch):
    """Sin key, la selección se pierde al tocar el filtro. Guarda que sigue ahí."""
    at = _run_events_page(events_db, monkeypatch)

    assert not at.exception
    event_box = next(sb for sb in at.selectbox if sb.label == "Evento")
    assert event_box.key == "event_select"


def test_event_without_valid_clv_renders(events_db, monkeypatch):
    """Un evento sin cierre fiable (clv NULL) se pinta sin excepción."""
    at = _run_events_page(events_db, monkeypatch)

    at.segmented_control[0].set_value("Todos").run()
    nocierre = next(o for o in at.selectbox[0].options if "Pending Home" in o)
    at.selectbox[0].set_value(nocierre).run()

    assert not at.exception
