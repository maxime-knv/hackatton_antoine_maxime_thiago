"""Analyse d'une action et d'un match : métriques image par image + évaluation de la décision du QB.

`analyze_play`  : PlayTracking -> PlayAnalysis (séries temporelles du receveur ciblé + Decision).
`analyze_game`  : tous les lancers d'un match -> GameAnalysis (tableau récapitulatif + analyses).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from . import config as C
from .data import PlayTracking, Player, Tables, build_play_tracking, find_targeted_receiver, load_tracking
from .evaluation import Decision, SNAPSHOT_COLUMNS, evaluate_decision
from .metrics import (
    Landing, direct_defender, estimate_landing, route_separations, separation, space_ahead, yac_potential,
)

PHASE_PRE = "Pré-passe"
PHASE_AIR = "Ballon en l'air"
PHASE_YAC = "Réception / YAC"
PASS_RESULTS = ("C", "I", "IN")


@dataclass
class PlayAnalysis:
    tracking: PlayTracking
    meta: dict
    passer_id: int
    passer_name: str
    target_id: int
    target_name: str
    target_pos: str
    target_k: int                   # indice du receveur ciblé dans tracking.offense
    sep: np.ndarray                 # séparation du receveur ciblé, par image (yards)
    nearest_def: np.ndarray         # indice (dans defense) du défenseur le plus proche, par image
    space: np.ndarray               # espace libre devant le receveur, par image
    speed: np.ndarray               # vitesse du receveur (yards/s)
    yac: np.ndarray                 # YAC Potential instantané (yards)
    direct_k: int                   # défenseur direct (indice dans defense)
    route_sep: np.ndarray           # (images, receveurs éligibles) séparation de chaque option du QB
    landing: Landing
    decision: Decision
    view: tuple[float, float]       # fenêtre d'affichage le long du terrain (yards)

    # -- accès rapides
    @property
    def frames(self) -> np.ndarray:
        return self.tracking.frames

    @property
    def release_idx(self) -> int:
        return int(self.tracking.release_idx)

    @property
    def snap_idx(self) -> int:
        return self.tracking.snap_idx

    @property
    def last_idx(self) -> int:
        return len(self.frames) - 1

    def time_at(self, idx: int) -> float:
        """Secondes écoulées depuis le snap (négatif avant)."""
        return (idx - self.snap_idx) / C.TRACKING_FPS

    def phase_at(self, idx: int) -> str:
        if idx < self.release_idx:
            return PHASE_PRE
        arrival = self.tracking.arrival_idx
        return PHASE_YAC if arrival is not None and idx >= arrival else PHASE_AIR

    def phase_detail(self, idx: int) -> str:
        if idx < self.snap_idx:
            return "avant le snap"
        if idx < self.release_idx:
            return "le QB lit la défense"
        if self.phase_at(idx) == PHASE_YAC:
            return "ballon réceptionné"
        if idx == self.last_idx:
            return "fin du tracking (~0,5 s après le lancer)"
        return "passe lancée"


def snapshot_at(pt: PlayTracking, idx: int) -> pd.DataFrame:
    """Image des 22 joueurs à l'instant `idx`, au format attendu par evaluate_decision."""
    parts = []
    for side, squad in (("offense", pt.offense), ("defense", pt.defense)):
        is_route = np.zeros(len(squad.ids), dtype=bool)
        if side == "offense":
            is_route[pt.route_ks] = True
        parts.append(pd.DataFrame({
            "nflId": squad.ids, "side": side, "name": squad.shorts, "position": squad.positions,
            "is_route": is_route, "x": squad.xy[idx, :, 0], "y": squad.xy[idx, :, 1], "s": squad.speed[idx],
        }))
    return pd.concat(parts, ignore_index=True)[list(SNAPSHOT_COLUMNS)]


def field_window(pt: PlayTracking, landing: Landing) -> tuple[float, float]:
    """Fenêtre d'affichage le long du terrain : tous les joueurs, tout le tracking, le point de réception."""
    xs = np.concatenate([
        pt.offense.xy[..., 0].ravel(), pt.defense.xy[..., 0].ravel(), pt.ball_xy[:, 0], [landing.xy[0]],
    ])
    lo, hi = float(xs.min()) - 3.0, float(xs.max()) + 4.0
    if hi - lo < 38.0:                       # fenêtre minimale pour garder de la lisibilité
        pad = (38.0 - (hi - lo)) / 2
        lo, hi = lo - pad, hi + pad
    if hi - lo > 72.0:                       # bombe + sécurité très profonde : on garde l'action côté QB
        hi = lo + 72.0
    lo = max(lo, 0.0)
    return lo, min(max(hi, lo + 38.0), C.FIELD_LENGTH)


def analyze_play(pt: PlayTracking, play: Mapping, players: Mapping[int, Player]) -> PlayAnalysis | None:
    """Analyse une passe. None si on ne peut pas juger la décision (pas de lancer ni de cible identifiée)."""
    if pt.release_idx is None or pt.qb_k is None or not pt.route_ks:
        return None
    off, dfn = pt.offense, pt.defense
    candidates = {int(off.ids[k]): players[int(off.ids[k])].variants for k in pt.route_ks if int(off.ids[k]) in players}
    target_id = find_targeted_receiver(str(play["playDescription"]), candidates)
    if target_id is None:
        return None

    t = int(np.flatnonzero(off.ids == target_id)[0])
    receiver_xy = off.xy[:, t]
    sep, nearest = separation(receiver_xy, dfn.xy)
    space = space_ahead(receiver_xy, dfn.xy)
    speed = off.speed[:, t]
    yac = yac_potential(sep, space, speed, receiver_xy[:, 0])

    last_idx = len(pt.frames) - 1
    landing = estimate_landing(pt.ball_xy, receiver_xy, pt.release_idx, last_idx, pt.arrival_idx)
    decision = evaluate_decision(
        snapshot_at(pt, pt.release_idx), target_id,
        landing_xy=landing.xy, pass_result=play["passResult"], play_result=play["prePenaltyPlayResult"],
    )
    meta = {
        "quarter": play["quarter_label"], "clock": play["gameClock"], "situation": play["situation"],
        "down": int(play["down"]), "yards_to_go": int(play["yardsToGo"]),
        "possession": play["possessionTeam"], "defense": play["defensiveTeam"],
        "pass_result": play["passResult"], "play_result": play["prePenaltyPlayResult"],
        "description": str(play["playDescription"]).strip(),
        "formation": play["offenseFormation"], "personnel_o": play["personnelO"], "personnel_d": play["personnelD"],
        "coverage": play["pff_passCoverage"], "coverage_type": play["pff_passCoverageType"],
    }
    return PlayAnalysis(
        tracking=pt, meta=meta,
        passer_id=int(off.ids[pt.qb_k]), passer_name=off.names[pt.qb_k],
        target_id=target_id, target_name=off.names[t], target_pos=off.positions[t], target_k=t,
        sep=sep, nearest_def=nearest, space=space, speed=speed, yac=yac,
        direct_k=direct_defender(receiver_xy, dfn.xy, pt.snap_idx, pt.release_idx),
        route_sep=route_separations(off.xy[:, pt.route_ks], dfn.xy),
        landing=landing, decision=decision, view=field_window(pt, landing),
    )


# --------------------------------------------------------------------------- match
@dataclass
class GameAnalysis:
    game_id: int
    plays: dict[int, PlayAnalysis]
    summary: pd.DataFrame           # une ligne par passe analysée (ordre chronologique)
    skipped: int = 0                # passes écartées (pas de cible identifiée : jetées, balles détournées...)
    attempts: int = 0               # passes jouées dans le match (avec ou sans cible identifiée)


def summary_row(a: PlayAnalysis, play_id: int) -> dict:
    t, m, d = a.tracking, a.meta, a.decision
    return {
        "playId": play_id, "quarter": m["quarter"], "clock": m["clock"], "situation": m["situation"],
        "down": m["down"], "yardsToGo": m["yards_to_go"],
        "passer_id": a.passer_id, "passer": a.passer_name, "target_id": a.target_id, "target": a.target_name,
        "target_pos": a.target_pos, "pass_result": m["pass_result"], "play_result": m["play_result"],
        "separation": d.separation, "yac_potential": d.yac_potential,
        "verdict": d.verdict.key, "decision": d.text, "short": d.short,
        "snap_frame": int(t.frames[t.snap_idx]), "release_frame": int(t.frames[a.release_idx]),
        "first_frame": int(t.frames[0]), "last_frame": int(t.frames[-1]),
    }


def analyze_game(tables: Tables, game_id: int) -> GameAnalysis:
    """Analyse toutes les passes d'un match (chargement du tracking + évaluation de chaque lancer)."""
    tracking = load_tracking(tables.data_dir, game_id)
    passes = tables.plays[(tables.plays["gameId"] == game_id) & tables.plays["passResult"].isin(PASS_RESULTS)]
    roles = {
        int(pid): dict(zip(g["nflId"].astype(int), g["pff_role"]))
        for pid, g in tables.pff[tables.pff["gameId"] == game_id].groupby("playId")
    }
    by_play = {int(pid): g for pid, g in tracking.groupby("playId", sort=False)}

    analyses: dict[int, PlayAnalysis] = {}
    rows = []
    for play in passes.to_dict("records"):
        pid = int(play["playId"])
        rows_p = by_play.get(pid)
        pt = None if rows_p is None else build_play_tracking(rows_p, play, roles.get(pid, {}), tables.players, game_id)
        a = None if pt is None else analyze_play(pt, play, tables.players)
        if a is None:
            continue
        analyses[pid] = a
        rows.append(summary_row(a, pid))
    summary = pd.DataFrame(rows)
    return GameAnalysis(game_id, analyses, summary, skipped=len(passes) - len(analyses), attempts=len(passes))


# --------------------------------------------------------------------------- événements clés d'une action
@dataclass(frozen=True)
class KeyEvent:
    frame: int
    title: str
    player_id: int
    player: str
    badge: str          # évaluation ("—" si l'événement n'est pas une décision)
    description: str


def _clean(value, fallback: str = "") -> str:
    return fallback if value is None or (isinstance(value, float) and np.isnan(value)) else str(value)


def key_events(a: PlayAnalysis) -> list[KeyEvent]:
    """Moments clés d'une action, chacun associé à son frameId (pour sauter à l'image exacte)."""
    t, m, d = a.tracking, a.meta, a.decision
    frame = lambda i: int(t.frames[i])   # noqa: E731

    setup = " · ".join(filter(None, [
        _clean(m["formation"]).title(), f"{_clean(m['personnel_o'])} face à {_clean(m['personnel_d'])}".strip(),
        f"{_clean(m['coverage'])} ({_clean(m['coverage_type'])})" if _clean(m["coverage"]) else "",
    ]))
    events = [KeyEvent(frame(t.snap_idx), "Snap", a.passer_id, a.passer_name, "—", setup or "Snap")]

    peak = t.snap_idx + int(a.sep[t.snap_idx: a.release_idx + 1].argmax())
    if peak != a.release_idx:
        events.append(KeyEvent(
            frame(peak), "Receveur le plus ouvert", a.target_id, a.target_name, "—",
            f"{a.target_name} atteint {a.sep[peak]:.1f} yd de séparation à {a.time_at(peak):+.1f} s "
            f"(YAC potentiel {a.yac[peak]:.1f} yd).",
        ))
    events.append(KeyEvent(frame(a.release_idx), "Lancer", a.passer_id, a.passer_name, d.verdict.badge, d.text))

    if t.arrival_idx is not None:
        i = t.arrival_idx
        events.append(KeyEvent(
            frame(i), "Ballon arrivé", a.target_id, a.target_name, "—",
            f"Séparation à l'arrivée : {a.sep[i]:.1f} yd, YAC potentiel {a.yac[i]:.1f} yd.",
        ))
    outcome = m["description"]
    if t.arrival_idx is None:
        outcome += (f"  ·  Le tracking s'arrête ~0,5 s après le lancer ; réception estimée à "
                    f"{a.landing.xy[0] - t.los_x:.0f} yd de la ligne de mêlée.")
    events.append(KeyEvent(frame(a.last_idx), "Fin du tracking", a.target_id, a.target_name, "—", outcome))
    return events
