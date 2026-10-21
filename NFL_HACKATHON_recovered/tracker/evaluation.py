"""Évaluation "façon Chess.com" de la décision du quarterback au moment du lancer.

Une passe est jugée sur ce que le QB *voyait* à l'instant du lancer (image `pass_forward`) :
qui était ouvert, à quelle distance étaient les défenseurs, quel espace s'offrait au receveur.

    💎 Meilleur coup  (!!)  receveur ouvert (> 3 yd) ET YAC Potential élevé
    ✅ Bon coup             tout le reste
    ⚠️ Erreur         (?)   receveur couvert (< 1 yd) alors qu'un autre receveur primaire était ouvert (> 3 yd)
    ❌ Gaffe         (??)   séparation < 0,5 yd, défenseur déjà au point de réception, ou interception

Seuils : tracker/config.py. Priorité en cas de cumul : Gaffe > Erreur > Meilleur coup > Bon coup.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config as C
from .metrics import nearest_to_point, route_separations, space_ahead, yac_potential

# Colonnes attendues par evaluate_decision pour une "image" (snapshot) de l'action
SNAPSHOT_COLUMNS = ("nflId", "side", "name", "position", "is_route", "x", "y", "s")


@dataclass(frozen=True)
class Verdict:
    key: str
    label: str
    icon: str
    symbol: str   # annotation d'échecs (!!, ?, ??)
    color: str

    @property
    def badge(self) -> str:
        """Libellé avec icône ET texte : l'information ne repose jamais sur la couleur seule."""
        return f"{self.icon} {self.label}" + (f" {self.symbol}" if self.symbol else "")


BRILLIANT = Verdict("brilliant", "Meilleur coup", "💎", "!!", "#1BACA6")
GOOD = Verdict("good", "Bon coup", "✅", "", "#7FA650")
MISTAKE = Verdict("mistake", "Erreur", "⚠️", "?", "#E58F2A")
BLUNDER = Verdict("blunder", "Gaffe", "❌", "??", "#CA3431")
VERDICTS = (BRILLIANT, GOOD, MISTAKE, BLUNDER)
VERDICT_BY_KEY = {v.key: v for v in VERDICTS}


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    separation: float            # yards, au lancer
    yac_potential: float         # yards
    space_ahead: float           # yards
    alt_name: str | None         # meilleure option primaire ouverte (> 3 yd), s'il y en a une
    alt_separation: float | None
    catch_distance: float        # défenseur le plus proche du point de réception estimé
    reasons: tuple[str, ...]     # raisons de la Gaffe : separation / catch_point / interception
    text: str                    # explication complète (en-tête de la visualisation)
    short: str                   # version compacte (tableau)


def outcome_text(pass_result: str | None, play_result: float | None) -> str:
    if pass_result == "C":
        gain = "" if play_result is None or pd.isna(play_result) else f" ({play_result:+.0f} yd)"
        return f"Complète{gain}."
    if pass_result == "IN":
        return "Interceptée."
    if pass_result == "I":
        return "Incomplète."
    return ""


def outcome_short(pass_result: str | None, play_result: float | None) -> str:
    if pass_result == "C":
        return "complète" if play_result is None or pd.isna(play_result) else f"complète {play_result:+.0f} yd"
    return {"IN": "interceptée", "I": "incomplète"}.get(pass_result, "")


def evaluate_decision(
    frame: pd.DataFrame,
    targeted_receiver_id: int,
    *,
    landing_xy=None,
    pass_result: str | None = None,
    play_result: float | None = None,
) -> Decision:
    """Évalue la passe à partir de l'image du lancer.

    `frame` : un enregistrement par joueur à l'image `pass_forward` (colonnes : SNAPSHOT_COLUMNS),
    avec side ∈ {"offense", "defense"}. `landing_xy` : point de réception estimé (par défaut, la
    position du receveur). Toutes les distances sont des distances euclidiennes vectorisées.
    """
    offense = frame[frame["side"] == "offense"]
    defenders = frame[frame["side"] == "defense"]
    routes = offense[offense["is_route"]].reset_index(drop=True)
    hits = np.flatnonzero(routes["nflId"].to_numpy() == targeted_receiver_id)
    if hits.size == 0 or defenders.empty:
        raise ValueError("Receveur ciblé ou défenseurs absents de l'image du lancer.")
    t = int(hits[0])

    route_xy = routes[["x", "y"]].to_numpy(float)
    def_xy = defenders[["x", "y"]].to_numpy(float)
    seps = route_separations(route_xy, def_xy)                     # (receveurs,)

    sep = float(seps[t])
    space = float(space_ahead(route_xy[t], def_xy))
    yac = float(yac_potential(sep, space, float(routes["s"].iloc[t]), route_xy[t, 0]))

    # Autres receveurs primaires (WR/TE) réellement ouverts : candidats pour "ce qu'il fallait jouer"
    primary = np.array(routes["position"].isin(C.PRIMARY_POSITIONS))   # copie modifiable
    primary[t] = False
    open_alts = np.flatnonzero(primary & (seps > C.OPEN_SEP))
    best = int(open_alts[seps[open_alts].argmax()]) if open_alts.size else None

    # Défenseur déjà posté sur la trajectoire / au point de réception
    catch_xy = np.asarray(landing_xy if landing_xy is not None else route_xy[t], dtype=float)
    catch_dist, catch_k = nearest_to_point(def_xy, catch_xy)

    reasons = []
    if sep < C.DANGER_SEP:
        reasons.append("separation")
    if catch_dist <= C.CATCH_POINT_RADIUS:
        reasons.append("catch_point")
    if pass_result == "IN":
        reasons.append("interception")

    if reasons:
        verdict = BLUNDER
    elif sep < C.COVERED_SEP and best is not None:
        verdict = MISTAKE
    elif sep > C.OPEN_SEP and yac >= C.HIGH_YAC:
        verdict = BRILLIANT
    else:
        verdict = GOOD

    target_name = str(routes["name"].iloc[t])
    alt_name = str(routes["name"].iloc[best]) if best is not None else None
    text = _describe(
        verdict, target_name, str(routes["position"].iloc[t]), sep, yac, space,
        alt_name, None if best is None else str(routes["position"].iloc[best]),
        None if best is None else float(seps[best]),
        str(defenders["name"].iloc[catch_k]), catch_dist, reasons,
        outcome_text(pass_result, play_result),
    )
    short = _short(
        verdict, target_name, sep, yac, space, alt_name, None if best is None else float(seps[best]),
        catch_dist, reasons, outcome_short(pass_result, play_result),
    )
    return Decision(
        verdict=verdict, separation=sep, yac_potential=yac, space_ahead=space,
        alt_name=alt_name, alt_separation=None if best is None else float(seps[best]),
        catch_distance=catch_dist, reasons=tuple(reasons), text=text, short=short,
    )


def _short(verdict, target, sep, yac, space, alt, alt_sep, catch_dist, reasons, outcome) -> str:
    """Commentaire d'une ligne (~70 caractères) pour la liste des coups."""
    if verdict is BLUNDER:
        parts = []
        if "separation" in reasons:
            parts.append(f"collé ({sep:.1f} yd)")
        if "catch_point" in reasons:
            parts.append(f"défenseur au point de réception ({catch_dist:.1f} yd)")
        if "interception" in reasons:
            parts.append("interceptée")
        return f"{target} · " + " · ".join(parts)
    if verdict is MISTAKE:
        return f"{target} couvert ({sep:.1f} yd) · {alt} ouvert ({alt_sep:.1f} yd) · {outcome}"
    if verdict is BRILLIANT:
        return f"{target} ouvert ({sep:.1f} yd) · YAC pot. {yac:.1f} · {outcome}"
    return f"{target} · sép. {sep:.1f} yd · YAC pot. {yac:.1f} · {outcome}"


def _describe(verdict, target, pos, sep, yac, space, alt, alt_pos, alt_sep, catch_def, catch_dist, reasons, outcome):
    if verdict is BLUNDER:
        parts = []
        if "separation" in reasons:
            parts.append(f"{target} est quasiment collé par la défense ({sep:.1f} yd)")
        if "catch_point" in reasons:
            parts.append(f"{catch_def} est déjà au point de réception ({catch_dist:.1f} yd)")
        if "interception" in reasons:
            parts.append("la passe est interceptée")
        return f"Passe dangereuse vers {target} : {' ; '.join(parts)}. {outcome}".strip()
    if verdict is MISTAKE:
        return (
            f"{target} ({pos}) était couvert à {sep:.1f} yd alors que {alt} ({alt_pos}) "
            f"était ouvert à {alt_sep:.1f} yd. {outcome}"
        ).strip()
    if verdict is BRILLIANT:
        return (
            f"Lecture parfaite : {target} ({pos}) ouvert à {sep:.1f} yd, {space:.0f} yd d'espace devant lui "
            f"→ YAC potentiel {yac:.1f} yd. {outcome}"
        ).strip()
    tight = " Fenêtre serrée, mais aucune meilleure option primaire." if sep < C.COVERED_SEP else ""
    return f"Passe vers {target} ({pos}), séparation {sep:.1f} yd, YAC potentiel {yac:.1f} yd.{tight} {outcome}".strip()
