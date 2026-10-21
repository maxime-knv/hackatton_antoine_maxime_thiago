"""Constantes du projet : chemins, géométrie du terrain, seuils d'évaluation, palette.

Tout ce qu'un coach (ou un développeur pressé) voudrait ajuster est ici.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADSHOTS_CSV = ROOT / "assets" / "headshots_2021.csv"

# --------------------------------------------------------------------------- terrain
FIELD_LENGTH = 120.0   # yards, zones d'en-but comprises (0-10 et 110-120)
FIELD_WIDTH = 53.3
GOAL_LINE_X = 110.0    # ligne de but adverse, une fois l'attaque orientée vers x croissant
TRACKING_FPS = 10      # le tracking NFL est échantillonné à 10 images par seconde

# --------------------------------------------------------------------------- évaluation
# Seuils du cahier des charges (en yards)
OPEN_SEP = 3.0             # receveur "ouvert"
COVERED_SEP = 1.0          # receveur "couvert"
DANGER_SEP = 0.5           # fenêtre de tir quasi inexistante
CATCH_POINT_RADIUS = 2.0   # défenseur déjà posté au point de réception estimé
HIGH_YAC = 5.0             # YAC Potential "élevé" (yards) : ~ la moyenne observée sur le dataset
PRIMARY_POSITIONS = ("WR", "TE")   # receveurs "primaires" (les RB sont des solutions de repli)

# --------------------------------------------------------------------------- YAC Potential
# YAC attendu (yards) = intercept + sep*min(sep, SEP_CAP) + space*min(espace, SPACE_CAP) + speed*vitesse,
# borné par la distance à la ligne de but. Coefficients calibrés par scripts/calibrate.py.
SEP_CAP = 8.0
SPACE_CAP = 15.0
YAC_MODEL = {"intercept": -0.989, "sep": 0.241, "space": 0.267, "speed": 0.506}

# --------------------------------------------------------------------------- palette
# Rôles imposés par le cahier des charges : attaque bleu, défense orange, cible jaune, ballon marron.
# Teintes issues de la palette catégorielle validée (dataviz) ; le ballon et la cible sont toujours
# cerclés de blanc pour garder un contraste suffisant sur le gazon.
COLORS = {
    "offense": "#3987E5",
    "defense": "#EB6834",
    "target": "#FFD60A",
    "ball": "#A8602A",
    "turf": "#2D6A3E",
    "turf_alt": "#2A6339",
    "endzone": "#1F4A2C",
    "line": "rgba(255,255,255,0.55)",
    "ink": "#E6EDF3",
    "muted": "#8B949E",
    "grid": "rgba(255,255,255,0.08)",
}
