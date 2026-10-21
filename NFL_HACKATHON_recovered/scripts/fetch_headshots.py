"""Régénère assets/headshots_2021.csv (nflId -> URL de photo) depuis le roster public nflverse.

    python scripts/fetch_headshots.py

Le `nflId` du Big Data Bowl correspond à `gsis_it_id` dans les rosters nflverse. Le fichier produit est
versionné : l'application n'a donc besoin d'aucun accès réseau côté serveur (seul le navigateur charge
les images).
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

import pandas as pd

URL = "https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_2021.csv"
OUT = Path(__file__).resolve().parent.parent / "assets" / "headshots_2021.csv"


def main() -> int:
    with urllib.request.urlopen(URL, timeout=60) as response:
        roster = pd.read_csv(io.BytesIO(response.read()), low_memory=False)
    roster = roster.dropna(subset=["gsis_it_id", "headshot_url"]).drop_duplicates("gsis_it_id", keep="last")
    out = pd.DataFrame({"nflId": roster["gsis_it_id"].astype("int64"), "headshot_url": roster["headshot_url"]})
    OUT.parent.mkdir(exist_ok=True)
    out.sort_values("nflId").to_csv(OUT, index=False)
    print(f"{len(out)} photos -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
