# 🏈 YAC Potential & QB Decision Tracker

> Rejouez chaque passe NFL, voyez **qui était ouvert** au moment du lancer et faites **noter la décision du quarterback** — comme une revue de partie d'échecs.

![Aperçu du tableau de bord](assets/screenshot.png)

## 🎯 À quoi ça sert à un coach ?

- 🔎 **Revoir une action en 30 secondes** : terrain 2D animé, trajectoires, ballon, distance receveur ↔ défenseur à chaque image.
- 🧠 **Juger la lecture du QB** : qui était ouvert quand il a lâché le ballon ? Fallait-il jouer un autre receveur ?
- ⚡ **Repérer les erreurs récurrentes** : filtrez par match, quart-temps, down & distance, passeur, receveur ; le tableau classe chaque passe en *Meilleur coup / Bon coup / Erreur / Gaffe*.
- 🏃 **Estimer le gain potentiel** : le *YAC Potential* dit combien de yards le receveur peut espérer **après** la réception.

## 🚀 Quick Start

```bash
python -m venv .venv && source .venv/bin/activate     # Windows : .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py                                  # → http://localhost:8501
```

- Python 3.10+ (testé en 3.12). Les CSV du Big Data Bowl doivent être dans `data/` (`games`, `plays`, `players`, `pffScoutingData`, `tracking/`) — ou pointez-les avec `NFL_DATA_DIR=/chemin/vers/data`.
- Tests : `pytest` · Recalibrage du modèle : `python scripts/calibrate.py`

## 🖱️ Utilisation

| Section | Ce qu'on y fait |
|---|---|
| **1 · Menu & contrôles** | Choisir match, quart-temps, down, distance, passeur, receveur, puis l'action. ▶ Lecture / ⏸ Pause, ◀ ▶ image par image, 🎯 saut au lancer, vitesse ×0,25 / ×0,5 / ×1, curseur sur le `frameId`. |
| **2 · Visualisation** | À gauche le terrain (attaque 🔵, défense 🟠, receveur ciblé 🟡, ballon 🟤, trajectoires, lien pointillé vers le défenseur le plus proche). À droite la télémétrie : séparation, vitesse, phase de jeu, YAC Potential et courbe de séparation avec barre verticale à l'instant présent. « Options du QB » affiche la séparation de chaque receveur éligible. |
| **3 · Analyse décisionnelle** | Une ligne par passe (ou, en vue « Action sélectionnée », par moment clé). **Un clic sur une ligne recharge la section 2 à l'image exacte.** |

## 🧮 Les métriques, en clair

**Séparation** = distance (yards) entre le receveur et le défenseur le plus proche.

**🏃 YAC Potential** = yards qu'on peut espérer gagner *après* la réception. Trois ingrédients : la séparation, l'**espace libre devant** le receveur (distance au premier défenseur situé devant lui) et sa **vitesse**.
`≈ −0,77 + 0,24 × séparation + 0,27 × espace devant + 0,48 × vitesse`, plafonné à la distance jusqu'à la ligne de but. Les coefficients sont calibrés sur 4 344 réceptions : le quart des passes au plus fort potentiel gagne **6,8 yd** après réception en moyenne, contre **2,6 yd** pour le quart le plus faible.

**🏅 Évaluation** — la passe est jugée à l'image du lancer (`pass_forward`), avec ce que le QB avait sous les yeux :

| Évaluation | Règle | Passes complétées* |
|---|---|---|
| 💎 **Meilleur coup** `!!` | receveur ouvert (> 3 yd) **et** YAC Potential ≥ 6 yd | 78 % |
| ✅ **Bon coup** | tout le reste | 66 % |
| ⚠️ **Erreur** `?` | receveur couvert (< 1 yd) alors qu'un autre WR/TE était ouvert (> 3 yd) | 22 % |
| ❌ **Gaffe** `??` | séparation < 0,5 yd, **ou** défenseur à ≤ 2 yd du point de réception estimé, **ou** interception | 26 % |

<sub>* sur 7 284 passes (122 matchs) ; moyenne générale : 63 %. En cas de cumul : Gaffe > Erreur > Meilleur coup > Bon coup. Seuils modifiables dans `tracker/config.py`.</sub>

## 📚 Les données (et leurs limites)

- **Big Data Bowl 2023** : saison 2021, semaines 1 à 8, tracking à 10 images/s, scouting PFF.
- ⏱️ **Le tracking s'arrête ~0,5 s après le lancer** : la réception et le YAC ne sont pas mesurés. Le YAC Potential est donc un *modèle*, et le point de réception (✕ sur le terrain) est *estimé* en prolongeant la trajectoire du ballon. La phase « Réception / YAC » n'apparaît que sur les passes très courtes (≈ 4 %).
- 🎯 **Le receveur ciblé n'est pas fourni** : il est retrouvé en croisant `playDescription` et les receveurs de l'action (≈ 96 % des passes). Les passes jetées ou sans cible nommée sont écartées.
- 🖼️ Photos : nflverse (`assets/headshots_2021.csv`, régénérable avec `scripts/fetch_headshots.py`). Pas de photo ? Une icône par défaut s'affiche, sans erreur.
- 📐 Vue 2D : la hauteur de la balle est inconnue — un défenseur « sur la trajectoire » peut être battu par un lancer haut.

## ✅ Vérifications

- Orientation du terrain : sur 934 passes dont la description dit « left » ou « right », le point de réception tombe du bon côté dans **98 %** des cas.
- 50 tests (`pytest`) : géométrie, règles d'évaluation, chargement, parcours utilisateur Streamlit.
- Testé de bout en bout dans un navigateur : lecture/pause, pas à pas, filtres en cascade, clic sur le tableau.

## 🗂️ Structure

```
app.py                  (3) UI Streamlit : menu, visualisation, analyse décisionnelle
tracker/
  data.py               (1) chargement & nettoyage, receveur ciblé, normalisation du terrain
  evaluation.py         (2) évaluation « Chess.com » : evaluate_decision()
  metrics.py            séparation, espace devant, point de réception, YAC Potential (numpy)
  analysis.py           analyse image par image d'une action / d'un match, moments clés
  field.py              figures Plotly : terrain 2D et courbe de séparation
  config.py             seuils, coefficients, palette
scripts/                calibrate.py (recalibrage) · fetch_headshots.py (photos)
tests/                  pytest
```
