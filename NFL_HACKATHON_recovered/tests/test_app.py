"""Parcours utilisateur de l'application Streamlit (AppTest, sans navigateur)."""
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tracker.data import resolve_data_dir

try:
    resolve_data_dir()
    HAS_DATA = True
except FileNotFoundError:
    HAS_DATA = False

pytestmark = pytest.mark.skipif(not HAS_DATA, reason="données NFL absentes (dossier data/)")
APP = str(Path(__file__).resolve().parent.parent / "app.py")


def plays_in(at: AppTest) -> int:
    return len(at.selectbox(key="sel_play").options)


@pytest.fixture()
def app():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    return at


def test_app_renders_the_three_sections(app):
    labels = [s.label for s in app.selectbox]
    assert labels[:6] == ["Match", "Quart-temps", "Down", "Distance", "Passeur", "Receveur"]
    assert labels[6].startswith("Action")
    metrics = {m.label: m.value for m in app.metric}
    assert {"Séparation actuelle", "Vitesse du receveur", "Phase de jeu", "YAC Potential"} <= set(metrics)
    assert sum(1 for label in metrics if label.endswith(("!!", "?", "??")) or label.endswith("Bon coup")) == 4
    assert [b.label for b in app.button][:5] == ["▶ Lecture", "⏮", "◀", "▶", "🎯 Lancer"]
    assert len(app.slider) == 1 and len(app.dataframe) == 1


def test_filters_narrow_the_action_list_and_cascade(app):
    total = plays_in(app)
    app.selectbox(key="f_quarter").select("Q2").run()
    assert not app.exception and 0 < plays_in(app) < total
    receivers_before = len(app.selectbox(key="f_receiver").options)
    passers = app.selectbox(key="f_passer").options
    app.selectbox(key="f_passer").select(passers[1]).run()
    assert not app.exception and plays_in(app) > 0
    assert 1 < len(app.selectbox(key="f_receiver").options) <= receivers_before      # facettes : seuls ses receveurs


def test_changing_the_action_goes_back_to_the_first_frame(app):
    app.button(key="btn_release").click().run()                     # on s'éloigne de la première image
    other_play = app.session_state["table_targets"][3][0]            # (playId, image du lancer) de la 4e passe
    app.session_state["sel_play"] = other_play
    app.run()
    assert not app.exception
    assert app.session_state["pos"] == app.slider(key="frame").min


def test_stepping_and_jumping(app):
    first = app.slider(key="frame").value
    app.button(key="btn_next").click().run()
    assert app.slider(key="frame").value == first + 1
    app.button(key="btn_release").click().run()
    assert app.slider(key="frame").value > first + 20
    app.button(key="btn_start").click().run()
    assert app.slider(key="frame").value == first


def test_playback_runs_to_the_last_frame_then_stops(app):
    app.session_state["speed_label"] = "1×"
    app.button(key="btn_release").click().run()                # on part du lancer : lecture courte
    app.button(key="btn_play").click().run()
    assert not app.exception
    assert app.session_state["playing"] is False
    assert app.slider(key="frame").value == app.slider(key="frame").max
    assert app.button(key="btn_play").label == "▶ Lecture"


def test_table_can_switch_to_the_events_of_the_selected_action(app):
    app.segmented_control(key="table_mode").set_value("Action sélectionnée").run()
    assert not app.exception
    table = app.dataframe[0].value
    assert list(table["Situation"])[0] == "Snap" and "Lancer" in list(table["Situation"])
