"""Tests sur les vraies données (ignorés si le dossier data/ est absent)."""
import json
import re

import numpy as np
import plotly.io as pio
import pytest

from tracker import config as C
from tracker.analysis import PHASE_AIR, PHASE_PRE, analyze_game, key_events
from tracker.data import load_tables, resolve_data_dir
from tracker.evaluation import VERDICT_BY_KEY
from tracker.field import build_field_figure, build_separation_figure, to_plot

try:
    resolve_data_dir()
    HAS_DATA = True
except FileNotFoundError:
    HAS_DATA = False

pytestmark = pytest.mark.skipif(not HAS_DATA, reason="données NFL absentes (dossier data/)")


@pytest.fixture(scope="module")
def tables():
    return load_tables()


@pytest.fixture(scope="module")
def game(tables):
    return analyze_game(tables, int(tables.games["gameId"].iloc[1]))


def test_game_summary_is_consistent(game):
    s = game.summary
    assert len(s) == len(game.plays) > 40 and game.skipped < 0.15 * game.attempts
    assert set(s["verdict"]) <= set(VERDICT_BY_KEY)
    assert (s["separation"] > 0).all() and (s["yac_potential"] >= 0).all()
    assert (s["release_frame"] > s["snap_frame"]).all()


def test_decision_matches_the_time_series(game):
    for a in game.plays.values():
        assert a.decision.separation == pytest.approx(a.sep[a.release_idx])
        assert a.phase_at(0) == PHASE_PRE and a.phase_at(a.release_idx) in (PHASE_AIR, "Réception / YAC")
        assert a.sep.shape == a.yac.shape == (len(a.frames),)


def test_key_events_are_chronological_and_inside_the_tracking(game):
    for a in game.plays.values():
        frames = [e.frame for e in key_events(a)]
        assert frames == sorted(frames) and a.frames[0] <= frames[0] and frames[-1] <= a.frames[-1]


def test_figures_render_for_key_frames(game):
    a = next(iter(game.plays.values()))
    for idx in (0, a.snap_idx, a.release_idx, a.last_idx):
        fig = build_field_figure(a, idx, show_options=True)
        assert {"Attaque", "Défense", "Receveur ciblé", "Ballon"} <= {t.name for t in fig.data}
        payload = json.loads(pio.to_json(fig))
        # un attribut scalaire sérialisé en binaire serait illisible pour Plotly.js (bug "NaN" déjà rencontré)
        assert all(not isinstance(an.get("x"), dict) and not isinstance(an.get("y"), dict)
                   for an in payload["layout"]["annotations"])
        assert build_separation_figure(a, idx).layout.yaxis.range[0] == 0


def test_field_orientation_matches_the_play_description(tables):
    """« pass deep right » : le point de réception doit tomber à droite du QB à l'écran (rotation sans miroir)."""
    agree = total = 0
    for a in analyze_game(tables, int(tables.games["gameId"].iloc[5])).plays.values():
        side = re.search(r"pass (?:incomplete |INTERCEPTED )?(?:short |deep )?(left|right)", a.meta["description"], re.I)
        if not side:
            continue
        qb_u, _ = to_plot(a.tracking.ball_xy[a.release_idx])
        land_u, _ = to_plot(np.array(a.landing.xy))
        total += 1
        agree += ("right" if land_u > qb_u else "left") == side.group(1).lower()
    assert total >= 15 and agree / total >= 0.9


def test_verdict_thresholds_are_ordered():
    assert C.DANGER_SEP < C.COVERED_SEP < C.OPEN_SEP


def test_player_page_embeds_every_frame_with_stable_traces(game):
    from tracker.player import build_player_html, player_height
    a = next(iter(game.plays.values()))
    page = build_player_html(a, int(a.frames[a.release_idx]))
    assert page.count('"fieldFrames"') == 1 and "Plotly.restyle" in page and player_height(a) > 400
    figures = [build_field_figure(a, i, True) for i in (0, a.release_idx, a.last_idx)]
    assert len({len(f.data) for f in figures}) == 1          # même nombre de traces à chaque image
