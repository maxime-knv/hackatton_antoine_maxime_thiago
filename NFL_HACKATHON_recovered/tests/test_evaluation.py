"""Évaluation façon Chess.com : Meilleur coup / Bon coup / Erreur / Gaffe."""
import pandas as pd
import pytest

from tracker.evaluation import (
    BLUNDER, BRILLIANT, GOOD, MISTAKE, SNAPSHOT_COLUMNS, VERDICTS, evaluate_decision, outcome_short, outcome_text,
)


def frame(receivers, defenders):
    """receivers : (id, nom, poste, x, y, vitesse) ; defenders : (x, y). Le QB est à (20, 26)."""
    rows = [dict(nflId=nfl_id, side="offense", name=name, position=pos, is_route=True, x=x, y=y, s=s)
            for nfl_id, name, pos, x, y, s in receivers]
    rows.append(dict(nflId=1, side="offense", name="T.Brady", position="QB", is_route=False, x=20.0, y=26.0, s=0.0))
    rows += [dict(nflId=100 + i, side="defense", name=f"D.{i}", position="CB", is_route=False, x=x, y=y, s=0.0)
             for i, (x, y) in enumerate(defenders)]
    return pd.DataFrame(rows)[list(SNAPSHOT_COLUMNS)]


TARGET = (10, "C.Godwin", "WR", 40.0, 26.0, 7.0)
BEHIND = [(36.0, 26.0), (25.0, 10.0), (25.0, 40.0)]      # défenseurs derrière le receveur : 4 yd de séparation


def test_open_fast_receiver_with_space_is_a_brilliant_move():
    d = evaluate_decision(frame([TARGET], BEHIND), 10, pass_result="C", play_result=14)
    assert d.verdict is BRILLIANT
    assert d.separation == pytest.approx(4.0) and d.yac_potential >= 6.0 and d.reasons == ()
    assert "C.Godwin" in d.text and "Complète" in d.text


def test_open_but_slow_receiver_is_only_a_good_move():
    slow = (10, "C.Godwin", "WR", 40.0, 26.0, 0.0)
    assert evaluate_decision(frame([slow], BEHIND), 10).verdict is GOOD


def test_covered_receiver_while_a_primary_receiver_is_open_is_a_mistake():
    covered = [(40.0, 26.8), (25.0, 10.0)]
    open_te = (11, "T.Kelce", "TE", 38.0, 45.0, 3.0)
    d = evaluate_decision(frame([TARGET, open_te], covered), 10, landing_xy=(55.0, 26.0), pass_result="I")
    assert d.verdict is MISTAKE
    assert d.alt_name == "T.Kelce" and d.alt_separation > 3.0
    assert "couvert" in d.text and "T.Kelce" in d.text


def test_an_open_running_back_is_not_a_primary_alternative():
    covered = [(40.0, 26.8), (25.0, 10.0)]
    open_rb = (12, "L.Fournette", "RB", 25.0, 35.0, 2.0)
    d = evaluate_decision(frame([TARGET, open_rb], covered), 10, landing_xy=(55.0, 26.0))
    assert d.verdict is GOOD and d.alt_name is None
    assert "aucune meilleure option" in d.text


def test_blunder_when_the_receiver_is_glued_to_a_defender():
    d = evaluate_decision(frame([TARGET], [(40.0, 26.3)]), 10, landing_xy=(55.0, 26.0))
    assert d.verdict is BLUNDER and "separation" in d.reasons


def test_blunder_when_a_defender_already_sits_at_the_catch_point():
    d = evaluate_decision(frame([TARGET], BEHIND + [(52.0, 26.5)]), 10, landing_xy=(52.0, 26.0))
    assert d.verdict is BLUNDER and d.reasons == ("catch_point",)
    assert d.catch_distance == pytest.approx(0.5) and "point de réception" in d.text


def test_an_interception_is_always_a_blunder():
    d = evaluate_decision(frame([TARGET], BEHIND), 10, pass_result="IN")
    assert d.verdict is BLUNDER and d.reasons == ("interception",) and "interceptée" in d.text


def test_blunder_takes_priority_over_mistake():
    open_te = (11, "T.Kelce", "TE", 38.0, 45.0, 3.0)
    d = evaluate_decision(frame([TARGET, open_te], [(40.0, 26.3)]), 10, landing_xy=(55.0, 26.0))
    assert d.verdict is BLUNDER


def test_missing_receiver_raises():
    with pytest.raises(ValueError):
        evaluate_decision(frame([TARGET], BEHIND), 999)


def test_every_decision_has_a_short_comment_that_fits_a_table_cell():
    for result in ("C", "I", "IN"):
        d = evaluate_decision(frame([TARGET], BEHIND), 10, pass_result=result, play_result=9)
        assert 0 < len(d.short) <= 90 and "C.Godwin" in d.short


def test_outcome_helpers():
    assert outcome_text("C", 12) == "Complète (+12 yd)." and outcome_text("I", 0) == "Incomplète."
    assert outcome_short("IN", 0) == "interceptée" and outcome_short("C", float("nan")) == "complète"


def test_verdict_badges_carry_an_icon_and_a_label():
    assert [v.badge for v in VERDICTS] == ["💎 Meilleur coup !!", "✅ Bon coup", "⚠️ Erreur ?", "❌ Gaffe ??"]
