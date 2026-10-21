"""Géométrie vectorisée (numpy) : séparation, défenseur le plus proche, espace devant,
point de réception estimé et YAC Potential.

Convention : coordonnées normalisées, l'attaque va toujours vers x croissant (voir data.load_tracking).
Les tableaux de trajectoires ont la forme (frames, joueurs, 2).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config as C


# --------------------------------------------------------------------------- distances
def distances(points: np.ndarray, others: np.ndarray) -> np.ndarray:
    """Distance euclidienne de chaque point de `points` (..., 2) à chaque élément de `others` (..., k, 2).

    Les dimensions de tête (typiquement le temps) sont diffusées -> résultat (..., k).
    """
    return np.linalg.norm(others - points[..., None, :], axis=-1)


def pairwise_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Distances entre tous les couples de `a` (..., ka, 2) et `b` (..., kb, 2) -> (..., ka, kb)."""
    return np.linalg.norm(a[..., :, None, :] - b[..., None, :, :], axis=-1)


def separation(receiver_xy: np.ndarray, defenders_xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Séparation = distance (yards) au défenseur le plus proche, et indice de ce défenseur."""
    d = distances(receiver_xy, defenders_xy)
    return d.min(axis=-1), d.argmin(axis=-1)


def route_separations(routes_xy: np.ndarray, defenders_xy: np.ndarray) -> np.ndarray:
    """Séparation de chaque receveur (..., kr, 2) face aux défenseurs (..., kd, 2) -> (..., kr)."""
    return pairwise_distances(routes_xy, defenders_xy).min(axis=-1)


def space_ahead(receiver_xy: np.ndarray, defenders_xy: np.ndarray, cap: float = C.SPACE_CAP) -> np.ndarray:
    """Distance au défenseur le plus proche situé *devant* le receveur (côté en-but adverse).

    Mesure l'espace libre pour courir après la réception. Plafonnée à `cap` (aucun défenseur devant).
    """
    d = distances(receiver_xy, defenders_xy)
    ahead = defenders_xy[..., 0] > receiver_xy[..., 0][..., None] + 0.5
    return np.minimum(np.where(ahead, d, np.inf).min(axis=-1), cap)


def direct_defender(receiver_xy: np.ndarray, defenders_xy: np.ndarray, start: int, stop: int) -> int:
    """Défenseur direct = celui qui reste le plus près du receveur entre les images `start` et `stop`."""
    window = slice(start, stop + 1)
    return int(distances(receiver_xy[window], defenders_xy[window]).mean(axis=0).argmin())


def nearest_to_point(defenders_xy: np.ndarray, point_xy: np.ndarray) -> tuple[float, int]:
    """Distance et indice du défenseur le plus proche d'un point fixe (défenseurs (k, 2), point (2,))."""
    d = np.linalg.norm(defenders_xy - np.asarray(point_xy), axis=-1)
    return float(d.min()), int(d.argmin())


# --------------------------------------------------------------------------- point de réception
@dataclass(frozen=True)
class Landing:
    """Point de réception du ballon. `observed` = mesuré (événement pass_arrived) ou extrapolé."""

    xy: tuple[float, float]
    seconds: float | None   # délai lancer -> réception
    observed: bool


def estimate_landing(
    ball_xy: np.ndarray,
    receiver_xy: np.ndarray,
    release_idx: int,
    last_idx: int,
    arrival_idx: int | None = None,
    fps: int = C.TRACKING_FPS,
) -> Landing:
    """Estime où le ballon va rencontrer le receveur.

    Le tracking s'arrête ~0,5 s après le lancer : on prolonge en ligne droite la trajectoire du ballon
    (direction et vitesse mesurées juste après le lancer) et on cherche l'instant où elle recoupe la
    trajectoire du receveur prolongée à vitesse constante. Si la réception est observée
    (`pass_arrived`), on utilise la mesure directe.
    """
    dt = 1.0 / fps
    if arrival_idx is not None and arrival_idx > release_idx:
        x, y = ball_xy[arrival_idx]
        return Landing((float(x), float(y)), (arrival_idx - release_idx) * dt, True)

    last_xy = receiver_xy[last_idx]
    fallback = Landing((float(last_xy[0]), float(last_xy[1])), None, False)
    n_after = last_idx - release_idx
    if n_after < 2:
        return fallback

    t_after = n_after * dt
    ball_velocity = (ball_xy[last_idx] - ball_xy[release_idx]) / t_after
    if np.linalg.norm(ball_velocity) < 5.0:   # ballon quasi immobile (passe détournée, etc.)
        return fallback

    k0 = max(release_idx, last_idx - 3)
    receiver_velocity = (last_xy - receiver_xy[k0]) / ((last_idx - k0) * dt)
    taus = np.arange(t_after, t_after + 5.0, 0.02)
    ball_path = ball_xy[release_idx] + ball_velocity * taus[:, None]
    receiver_path = last_xy + receiver_velocity * (taus - t_after)[:, None]
    j = int(np.linalg.norm(ball_path - receiver_path, axis=1).argmin())
    return Landing((float(ball_path[j, 0]), float(ball_path[j, 1])), float(taus[j]), False)


# --------------------------------------------------------------------------- YAC Potential
def yac_potential(sep, space, speed, x):
    """YAC Potential : yards qu'un receveur peut espérer gagner *après* la réception.

    Trois ingrédients simples : la séparation, l'espace libre devant lui et sa vitesse.
    Borné entre 0 et la distance restante jusqu'à la ligne de but.
    """
    m = C.YAC_MODEL
    raw = (
        m["intercept"]
        + m["sep"] * np.minimum(sep, C.SEP_CAP)
        + m["space"] * np.minimum(space, C.SPACE_CAP)
        + m["speed"] * speed
    )
    return np.clip(raw, 0.0, np.maximum(C.GOAL_LINE_X - np.asarray(x), 0.0))
