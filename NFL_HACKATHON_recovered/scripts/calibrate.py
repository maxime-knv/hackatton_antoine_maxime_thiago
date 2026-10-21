"""Recalibre et audite le modèle sur les 122 matchs (~7 300 passes) :

    python scripts/calibrate.py            # rapport complet
    python scripts/calibrate.py --save out.pkl   # + sauvegarde du tableau détaillé

1. Ajuste les coefficients du YAC Potential (régression linéaire : séparation, espace devant, vitesse).
   Cible = yards gagnés après réception, estimés par  gain de l'action - profondeur de la passe
   (le tracking s'arrête avant la réception : le YAC n'est pas mesuré directement).
2. Vérifie que le YAC Potential classe bien les receveurs (quartiles) et que les verdicts
   ont un sens (taux de passes complétées / interceptées par verdict).

Les coefficients affichés sont à reporter dans tracker/config.py (YAC_MODEL).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracker import config as C                      # noqa: E402
from tracker.analysis import analyze_game            # noqa: E402
from tracker.data import load_tables                 # noqa: E402
from tracker.evaluation import VERDICTS              # noqa: E402

NOISE = "No Play|PENALTY|FUMBLE|Lateral|lateral"


def collect() -> pd.DataFrame:
    tables = load_tables()
    rows, start = [], time.time()
    for k, game_id in enumerate(tables.games["gameId"]):
        game = analyze_game(tables, int(game_id))
        for play_id, a in game.plays.items():
            t, r = a.tracking, a.release_idx
            rows.append({
                "gameId": game_id, "playId": play_id, "pass_result": a.meta["pass_result"],
                "play_result": a.meta["play_result"], "description": a.meta["description"],
                "verdict": a.decision.verdict.key, "target_pos": a.target_pos,
                "sep": a.sep[r], "space": a.space[r], "speed": a.speed[r],
                "x": t.offense.xy[r, a.target_k, 0], "los": t.los_x,
                "air_yards": a.landing.xy[0] - t.los_x, "yac_pot": a.decision.yac_potential,
                "catch_dist": a.decision.catch_distance, "alt_sep": a.decision.alt_separation,
            })
        if k % 20 == 0:
            print(f"  match {k + 1}/{len(tables.games)}  ({time.time() - start:.0f}s)", flush=True)
    return pd.DataFrame(rows)


def fit_yac(df: pd.DataFrame) -> pd.DataFrame:
    clean = df[(df["pass_result"] == "C") & ~df["description"].str.contains(NOISE, regex=True)].copy()
    clean["yac"] = (clean["play_result"] - clean["air_yards"]).clip(lower=0)
    design = np.column_stack([
        np.ones(len(clean)), clean["sep"].clip(upper=C.SEP_CAP), clean["space"].clip(upper=C.SPACE_CAP), clean["speed"],
    ])
    beta, *_ = np.linalg.lstsq(design, clean["yac"].to_numpy(), rcond=None)
    pred = design @ beta
    r2 = 1 - ((clean["yac"] - pred) ** 2).sum() / ((clean["yac"] - clean["yac"].mean()) ** 2).sum()
    print(f"\n== YAC Potential ({len(clean)} réceptions) ==")
    print("YAC_MODEL = " + str({k: round(float(v), 3) for k, v in zip(["intercept", "sep", "space", "speed"], beta)}))
    print(f"R² = {r2:.3f}   YAC moyen estimé = {clean['yac'].mean():.2f} yd (médiane {clean['yac'].median():.2f})")
    quartile = pd.qcut(pd.Series(pred, index=clean.index), 4, labels=["Q1 (bas)", "Q2", "Q3", "Q4 (haut)"])
    print("YAC réel estimé selon le quartile du potentiel :")
    print(clean.groupby(quartile, observed=True)["yac"].agg(["size", "mean", "median"]).round(2).to_string())
    return clean


def audit_verdicts(df: pd.DataFrame) -> None:
    df = df.assign(comp=(df["pass_result"] == "C"), intercepted=(df["pass_result"] == "IN"))
    print(f"\n== Verdicts sur {len(df)} passes (seuils : ouvert > {C.OPEN_SEP}, couvert < {C.COVERED_SEP}, "
          f"danger < {C.DANGER_SEP}, YAC élevé >= {C.HIGH_YAC}) ==")
    table = df.groupby("verdict").agg(
        n=("comp", "size"), complétées=("comp", "mean"), interceptées=("intercepted", "mean"),
        sep_moy=("sep", "mean"), yac_pot_moy=("yac_pot", "mean"),
    )
    table.insert(1, "part", table["n"] / len(df))
    print(table.reindex([v.key for v in VERDICTS]).round(3).to_string())
    print("\nYAC Potential au lancer, quantiles :", df["yac_pot"].quantile([.25, .5, .75, .9]).round(2).to_dict())
    for threshold in (4, 5, 6, 7):
        share = ((df["sep"] > C.OPEN_SEP) & (df["yac_pot"] >= threshold)).mean()
        print(f"  part sep > {C.OPEN_SEP} et YAC Potential >= {threshold} : {share:.1%}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", help="chemin d'un .pkl pour garder le tableau détaillé")
    args = parser.parse_args()
    data = collect()
    if args.save:
        data.to_pickle(args.save)
    fit_yac(data)
    audit_verdicts(data)
