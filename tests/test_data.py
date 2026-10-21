"""Chargement/nettoyage : noms, receveur ciblé, normalisation du terrain, tracking d'une action."""
import base64

import numpy as np
import pandas as pd
import pytest

from tracker import config as C
from tracker import data


# ----------------------------------------------------------------------------- noms
def test_short_name():
    assert data.short_name("Tom Brady") == "T.Brady"
    assert data.short_name("Amon-Ra St. Brown") == "A.St. Brown"
    assert data.short_name("Madonna") == "Madonna"


def test_name_variants_cover_nfl_description_styles():
    assert "O.Beckham" in data.name_variants("Odell Beckham Jr.")          # suffixe supprimé
    assert "A.St. Brown" in data.name_variants("Amon-Ra St. Brown")
    assert "Dj.Moore" in data.name_variants("D.J. Moore")                  # deux initiales


def candidates(*names):
    return {i + 1: data.name_variants(n) for i, n in enumerate(names)}


@pytest.mark.parametrize("description, names, expected", [
    ("(13:18) (Shotgun) D.Prescott pass deep left to A.Cooper pushed ob at DAL 30 for 28 yards (A.Winfield).",
     ["Amari Cooper", "CeeDee Lamb"], 1),
    ("(3:45) (Shotgun) J.Goff pass short middle to A.St. Brown to DET 31 for 6 yards (D.Campbell).",
     ["Amon-Ra St. Brown", "T.J. Hockenson"], 1),
    ("(:17) (Shotgun) T.Bridgewater pass short left intended for C.Sutton INTERCEPTED by J.Pierre at PIT -8.",
     ["Courtland Sutton", "Noah Fant"], 1),
    ("(14:21) (Shotgun) S.Darnold pass deep right to Dj.Moore pushed ob at NYJ 45 for 26 yards (S.Redwine).",
     ["Jamison Crowder", "D.J. Moore"], 2),
    ("(2:09) (Shotgun) P.Mahomes pass short middle to T.Kelce to KC 26 for 5 yards. Lateral to J.McKinnon pushed ob.",
     ["Jerick McKinnon", "Travis Kelce"], 2),                                # passe latérale : la 1re mention est la cible
    ("(5:56) K.Cousins pass incomplete short right [L.Wilson].", ["Luke Wilson", "Justin Jefferson"], None),
])
def test_find_targeted_receiver(description, names, expected):
    assert data.find_targeted_receiver(description, candidates(*names)) == expected


# ----------------------------------------------------------------------------- avatars
def test_placeholder_avatar_is_a_valid_svg_data_uri_with_initials():
    uri = data.placeholder_avatar("Tom Brady")
    assert uri.startswith("data:image/svg+xml;base64,")
    svg = base64.b64decode(uri.split(",", 1)[1]).decode()
    assert "<svg" in svg and ">TB<" in svg


def test_avatar_falls_back_to_placeholder_when_no_photo(tmp_path):
    tables = data.Tables(tmp_path, pd.DataFrame(), pd.DataFrame(), {}, pd.DataFrame(), {7: "https://example.org/p.png"})
    assert data.avatar_url(tables, 7, "Someone") == "https://example.org/p.png"
    assert data.avatar_url(tables, 8, "Someone Else").startswith("data:image/svg+xml")
    assert data.avatar_url(tables, None, "Nobody").startswith("data:image/svg+xml")


def test_headshots_are_resized_and_missing_file_is_harmless(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "HEADSHOTS_CSV", tmp_path / "missing.csv")
    assert data.load_headshots() == {}
    csv = tmp_path / "h.csv"
    csv.write_text('nflId,headshot_url\n1,"https://static.www.nfl.com/image/private/f_auto,q_auto/league/abc"\n')
    monkeypatch.setattr(C, "HEADSHOTS_CSV", csv)
    assert "w_96,h_96" in data.load_headshots()[1]


def test_resolve_data_dir_honours_environment(tmp_path, monkeypatch):
    (tmp_path / "plays.csv").write_text("gameId\n")
    monkeypatch.setenv("NFL_DATA_DIR", str(tmp_path))
    assert data.resolve_data_dir() == tmp_path


def test_resolve_data_dir_explains_what_is_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("NFL_DATA_DIR", raising=False)
    monkeypatch.setattr(C, "ROOT", tmp_path)                           # ni data/ ni datas/data/
    with pytest.raises(FileNotFoundError, match="NFL_DATA_DIR"):
        data.resolve_data_dir()


# ----------------------------------------------------------------------------- tracking
def tracking_csv(tmp_path):
    rows = []
    for direction, play in (("right", 1), ("left", 2)):
        for frame in (1, 2, 3):
            ev = {1: "ball_snap", 3: "pass_forward"}.get(frame)
            rows += [
                dict(playId=play, nflId=1.0, frameId=frame, jerseyNumber=12, team="AAA", playDirection=direction,
                     x=30.0 + frame, y=20.0, s=1.0, event=ev),
                dict(playId=play, nflId=2.0, frameId=frame, jerseyNumber=80, team="AAA", playDirection=direction,
                     x=40.0 + frame, y=30.0, s=5.0, event=ev),
                dict(playId=play, nflId=3.0, frameId=frame, jerseyNumber=24, team="BBB", playDirection=direction,
                     x=42.0 + frame, y=31.0, s=4.0, event=ev),
                dict(playId=play, nflId=np.nan, frameId=frame, jerseyNumber=np.nan, team="football",
                     playDirection=direction, x=30.0 + frame, y=20.0, s=0.0, event=ev),
            ]
    (tmp_path / "tracking").mkdir()
    pd.DataFrame(rows).to_csv(tmp_path / "tracking" / "tracking_99.csv", index=False)
    return tmp_path


def test_load_tracking_rotates_left_plays_so_offence_always_goes_right(tmp_path):
    tr = data.load_tracking(tracking_csv(tmp_path), 99)
    right = tr[(tr.playId == 1) & (tr.nflId == 2) & (tr.frameId == 1)].iloc[0]
    left = tr[(tr.playId == 2) & (tr.nflId == 2) & (tr.frameId == 1)].iloc[0]
    assert (right.x, right.y) == (41.0, 30.0)
    assert left.x == pytest.approx(C.FIELD_LENGTH - 41.0) and left.y == pytest.approx(C.FIELD_WIDTH - 30.0)


def test_build_play_tracking_splits_teams_and_finds_events(tmp_path):
    tr = data.load_tracking(tracking_csv(tmp_path), 99)
    players = {i: data.Player(i, n, data.short_name(n), pos, data.name_variants(n))
               for i, n, pos in ((1, "Pat Mahomes", "QB"), (2, "Tyreek Hill", "WR"), (3, "Marlon Humphrey", "CB"))}
    roles = {1: "Pass", 2: "Pass Route", 3: "Coverage"}
    play = dict(playId=1, possessionTeam="AAA", defensiveTeam="BBB")
    pt = data.build_play_tracking(tr[tr.playId == 1], play, roles, players, 99)
    assert pt.offense.xy.shape == (3, 2, 2) and pt.defense.xy.shape == (3, 1, 2) and pt.ball_xy.shape == (3, 2)
    assert (pt.snap_idx, pt.release_idx, pt.arrival_idx) == (0, 2, None)
    assert pt.qb_k == 0 and pt.route_ks == [1] and pt.offense.shorts[1] == "T.Hill"
    assert pt.los_x == pytest.approx(31.0) and pt.index_of(2) == 1


def test_incomplete_tracking_is_rejected(tmp_path):
    tr = data.load_tracking(tracking_csv(tmp_path), 99)
    broken = tr[~((tr.nflId == 3) & (tr.frameId == 2))]                 # un défenseur perd une image
    play = dict(playId=1, possessionTeam="AAA", defensiveTeam="BBB")
    assert data.build_play_tracking(broken[broken.playId == 1], play, {}, {}, 99) is None
