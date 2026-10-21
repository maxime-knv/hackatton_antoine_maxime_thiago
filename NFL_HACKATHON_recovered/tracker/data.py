"""(1) Chargement et nettoyage des données NFL Big Data Bowl 2023 (saison 2021, semaines 1-8).

Fichiers : games.csv, plays.csv, players.csv, pffScoutingData.csv, tracking/tracking_<gameId>.csv.

Points d'attention (le dataset diffère d'un "plays.csv" idéal) :
  * il n'y a pas de colonne passeur/receveur : le passeur vient du rôle PFF "Pass", le receveur ciblé est
    retrouvé en croisant `playDescription` ("... to C.Godwin") avec les receveurs de l'action ;
  * le tracking s'arrête ~0,5 s après le lancer : pas de réception ni de YAC mesurés (d'où le YAC Potential) ;
  * les coordonnées sont normalisées pour que l'attaque aille toujours vers x croissant.
"""
from __future__ import annotations

import base64
import html
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

TRACKING_COLUMNS = ["playId", "nflId", "frameId", "jerseyNumber", "team", "playDirection", "x", "y", "s", "event"]
PLAY_COLUMNS = [
    "gameId", "playId", "playDescription", "quarter", "down", "yardsToGo", "possessionTeam", "defensiveTeam",
    "gameClock", "passResult", "prePenaltyPlayResult", "playResult", "offenseFormation", "personnelO",
    "personnelD", "defendersInBox", "pff_passCoverage", "pff_passCoverageType",
]
ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}


# --------------------------------------------------------------------------- dossier de données
def resolve_data_dir() -> Path:
    """`NFL_DATA_DIR`, sinon `data/`, sinon `datas/data/` (le dossier doit contenir plays.csv)."""
    candidates = [os.environ.get("NFL_DATA_DIR"), C.ROOT / "data", C.ROOT / "datas" / "data"]
    for candidate in candidates:
        if candidate and (Path(candidate) / "plays.csv").exists():
            return Path(candidate)
    raise FileNotFoundError(
        "Données introuvables : placez les CSV dans ./data (games, plays, players, pffScoutingData, tracking/) "
        "ou définissez NFL_DATA_DIR."
    )


# --------------------------------------------------------------------------- noms de joueurs
_SUFFIX = re.compile(r"\s+(Jr\.?|Sr\.?|II|III|IV|V)$", re.IGNORECASE)


def short_name(display_name: str) -> str:
    """'Tom Brady' -> 'T.Brady' (notation des descriptions NFL)."""
    first, _, last = display_name.strip().partition(" ")
    return f"{first[0]}.{last}" if last else display_name.strip()


def name_variants(display_name: str) -> frozenset[str]:
    """Écritures possibles dans playDescription : 'A.St. Brown', 'O.Beckham' (sans Jr.), 'Dj.Moore'."""
    first, _, last = display_name.strip().partition(" ")
    if not last:
        return frozenset({display_name.strip()})
    initials = first.replace(".", "") or first
    bare = _SUFFIX.sub("", last)
    return frozenset({f"{initials[0]}.{last}", f"{initials[0]}.{bare}", f"{initials[:2].capitalize()}.{bare}"})


@lru_cache(maxsize=8192)
def _target_pattern(variant: str) -> re.Pattern:
    return re.compile(r"(?:\bto|\bfor) " + re.escape(variant) + r"(?=[\s.,\[(]|$)")


def find_targeted_receiver(description: str, candidates: Mapping[int, Iterable[str]]) -> int | None:
    """Receveur ciblé = candidat dont le nom apparaît après 'to' / 'intended for' dans la description.

    En cas de plusieurs mentions (passe latérale), la première est la cible. None si aucun ne correspond
    (passe jetée, cible non précisée...).
    """
    best_id, best_pos = None, None
    for nfl_id, variants in candidates.items():
        for variant in variants:
            match = _target_pattern(variant).search(description)
            if match and (best_pos is None or match.start() < best_pos):
                best_id, best_pos = int(nfl_id), match.start()
    return best_id


# --------------------------------------------------------------------------- tables de référence
@dataclass(frozen=True)
class Player:
    nfl_id: int
    name: str
    short: str
    position: str
    variants: frozenset[str]


@dataclass
class Tables:
    data_dir: Path
    games: pd.DataFrame
    plays: pd.DataFrame
    players: dict[int, Player]
    pff: pd.DataFrame
    headshots: dict[int, str]


def load_games(data_dir: Path) -> pd.DataFrame:
    games = pd.read_csv(data_dir / "games.csv")
    day = pd.to_datetime(games["gameDate"], format="%m/%d/%Y").dt.strftime("%d/%m")
    games["label"] = (
        "Sem. " + games["week"].astype(str) + " · " + games["visitorTeamAbbr"] + " @ " + games["homeTeamAbbr"] + " · " + day
    )
    return games.sort_values("gameId").reset_index(drop=True)


def load_plays(data_dir: Path) -> pd.DataFrame:
    plays = pd.read_csv(data_dir / "plays.csv", usecols=PLAY_COLUMNS)
    plays["quarter_label"] = plays["quarter"].map(lambda q: "OT" if q > 4 else f"Q{q}")
    plays["situation"] = [
        f"{ORDINALS[d]} & {y}" if d in ORDINALS else "—" for d, y in zip(plays["down"], plays["yardsToGo"])
    ]
    return plays


def load_players(data_dir: Path) -> dict[int, Player]:
    df = pd.read_csv(data_dir / "players.csv", usecols=["nflId", "displayName", "officialPosition"])
    return {
        int(r.nflId): Player(
            int(r.nflId), r.displayName, short_name(r.displayName),
            "" if pd.isna(r.officialPosition) else str(r.officialPosition), name_variants(r.displayName),
        )
        for r in df.itertuples(index=False)
    }


def load_pff_roles(data_dir: Path) -> pd.DataFrame:
    return pd.read_csv(data_dir / "pffScoutingData.csv", usecols=["gameId", "playId", "nflId", "pff_role"])


def load_headshots() -> dict[int, str]:
    """nflId -> URL de photo (nflverse, redimensionnée 96 px). Vide si le fichier est absent."""
    try:
        df = pd.read_csv(C.HEADSHOTS_CSV)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return {}
    small = "f_auto,q_auto,w_96,h_96,c_fill,g_face"
    return {int(r.nflId): r.headshot_url.replace("f_auto,q_auto", small, 1) for r in df.itertuples(index=False)}


def load_tables(data_dir: Path | None = None) -> Tables:
    data_dir = data_dir or resolve_data_dir()
    return Tables(
        data_dir=data_dir,
        games=load_games(data_dir),
        plays=load_plays(data_dir),
        players=load_players(data_dir),
        pff=load_pff_roles(data_dir),
        headshots=load_headshots(),
    )


def placeholder_avatar(name: str) -> str:
    """Icône par défaut (initiales sur disque gris) en data-URI : aucune erreur si la photo manque."""
    initials = "".join(w[0] for w in name.replace(".", " ").split()[:2]).upper() or "?"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">'
        '<circle cx="48" cy="48" r="48" fill="#30363D"/>'
        '<text x="48" y="61" font-family="Arial,Helvetica,sans-serif" font-size="38" font-weight="700" '
        f'text-anchor="middle" fill="#C9D1D9">{html.escape(initials)}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def avatar_url(tables: Tables, nfl_id: int | None, name: str) -> str:
    return (tables.headshots.get(int(nfl_id)) if nfl_id is not None else None) or placeholder_avatar(name)


# --------------------------------------------------------------------------- tracking
def load_tracking(data_dir: Path, game_id: int) -> pd.DataFrame:
    """Tracking d'un match, avec coordonnées normalisées : l'attaque va toujours vers x croissant.

    Une action jouée vers la gauche subit une rotation de 180° (x -> 120 - x, y -> 53,3 - y) :
    pas de symétrie miroir, la gauche et la droite de l'attaque restent justes.
    """
    df = pd.read_csv(data_dir / "tracking" / f"tracking_{game_id}.csv", usecols=TRACKING_COLUMNS)
    left = df["playDirection"].eq("left").to_numpy()
    df["x"] = np.where(left, C.FIELD_LENGTH - df["x"], df["x"])
    df["y"] = np.where(left, C.FIELD_WIDTH - df["y"], df["y"])
    return df


@dataclass
class Squad:
    """Une équipe sur l'action : identités + trajectoires (frames, joueurs, 2)."""

    ids: np.ndarray
    names: list[str]
    shorts: list[str]
    positions: list[str]
    jerseys: np.ndarray
    roles: list[str]
    xy: np.ndarray
    speed: np.ndarray


@dataclass
class PlayTracking:
    game_id: int
    play_id: int
    frames: np.ndarray              # frameId de chaque image
    offense: Squad
    defense: Squad
    ball_xy: np.ndarray             # (frames, 2)
    events: dict[str, int]          # événement -> frameId (première occurrence)
    snap_idx: int
    release_idx: int | None
    arrival_idx: int | None
    los_x: float
    qb_k: int | None                # indice du QB dans offense
    route_ks: list[int]             # indices des receveurs éligibles (rôle PFF "Pass Route")

    def index_of(self, frame_id: int) -> int:
        return int(np.clip(np.searchsorted(self.frames, frame_id), 0, len(self.frames) - 1))


def _squad(mask: np.ndarray, ids, jerseys, xy, speed, roles: Mapping[int, str], players: Mapping[int, Player]) -> Squad:
    sel = np.flatnonzero(mask)
    people = [players.get(int(ids[k])) for k in sel]
    return Squad(
        ids=ids[sel],
        names=[p.name if p else f"Joueur {int(ids[k])}" for p, k in zip(people, sel)],
        shorts=[p.short if p else f"#{int(jerseys[k])}" for p, k in zip(people, sel)],
        positions=[p.position if p else "" for p in people],
        jerseys=jerseys[sel],
        roles=[roles.get(int(ids[k]), "") for k in sel],
        xy=xy[:, sel],
        speed=speed[:, sel],
    )


def build_play_tracking(
    rows: pd.DataFrame,
    play: Mapping,
    roles: Mapping[int, str],
    players: Mapping[int, Player],
    game_id: int,
) -> PlayTracking | None:
    """Convertit les lignes de tracking d'UNE action en tableaux numpy. None si le tracking est incomplet."""
    frames = np.sort(rows["frameId"].unique())
    n = len(frames)
    ball = rows[rows["nflId"].isna()].sort_values("frameId")
    people = rows[rows["nflId"].notna()].sort_values(["nflId", "frameId"])
    if n == 0 or len(ball) != n or people.empty or (people.groupby("nflId").size() != n).any():
        return None

    ids = people["nflId"].to_numpy()[::n].astype(int)
    team = people["team"].to_numpy()[::n]
    jerseys = np.nan_to_num(people["jerseyNumber"].to_numpy(float)[::n], nan=-1).astype(int)
    xy = np.stack([people["x"].to_numpy(float).reshape(-1, n), people["y"].to_numpy(float).reshape(-1, n)], axis=-1)
    xy = xy.transpose(1, 0, 2)                                            # (frames, joueurs, 2)
    speed = people["s"].to_numpy(float).reshape(-1, n).T                  # (frames, joueurs)

    offense = _squad(team == play["possessionTeam"], ids, jerseys, xy, speed, roles, players)
    defense = _squad(team == play["defensiveTeam"], ids, jerseys, xy, speed, roles, players)
    if not len(offense.ids) or not len(defense.ids):
        return None

    events = {str(k): int(v) for k, v in rows.loc[rows["event"].notna()].groupby("event")["frameId"].min().items()}
    snap_frame = events.get("ball_snap", events.get("autoevent_ballsnap", int(frames[0])))
    release_frame = events.get("pass_forward", events.get("autoevent_passforward"))
    arrival_frame = events.get("pass_arrived")
    index_of = lambda f: int(np.searchsorted(frames, f))   # noqa: E731

    ball_xy = np.column_stack([ball["x"].to_numpy(float), ball["y"].to_numpy(float)])
    snap_idx = index_of(snap_frame)
    return PlayTracking(
        game_id=game_id,
        play_id=int(play["playId"]),
        frames=frames,
        offense=offense,
        defense=defense,
        ball_xy=ball_xy,
        events=events,
        snap_idx=snap_idx,
        release_idx=None if release_frame is None else index_of(release_frame),
        arrival_idx=None if arrival_frame is None else index_of(arrival_frame),
        los_x=float(ball_xy[snap_idx, 0]),
        qb_k=next((k for k, r in enumerate(offense.roles) if r == "Pass"), None),
        route_ks=[k for k, r in enumerate(offense.roles) if r == "Pass Route"],
    )
