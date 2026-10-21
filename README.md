# 🏈 YAC Potential & QB Decision Tracker

> Rejouez chaque passe NFL, voyez **qui était ouvert** au moment du lancer et faites **noter la décision du quarterback** — comme une revue de partie d'échecs.

![Aperçu du tableau de bord](assets/screenshot.png)

## 🎯 À quoi ça sert à un coach ?

- 🔎 **Revoir une action en 30 secondes** : terrain 2D animé, trajectoires, ballon, distance receveur ↔ défenseur à chaque image.
- 🧠 **Juger la lecture du QB** : qui était ouvert quand il a lâché le ballon ? Fallait-il jouer un autre receveur ?
- ⚡ **Repérer les erreurs récurrentes** : filtrez par match, quart-temps, down & distance, passeur, receveur ; le tableau classe chaque passe en *Meilleur coup / Bon coup / Erreur / Gaffe*.
- 🏃 **Estimer le gain potentiel** : le *YAC Potential* dit combien de yards le receveur peut espérer **après** la réception.

## 📦 Installation

**Prérequis** : Python 3.10+ (testé en 3.12), `git`, ~1 Go de disque pour les données.

### 1. Récupérer le projet

```bash
git clone git@github.com:maxime-knv/hackatton_antoine_maxime_thiago.git
cd hackatton_antoine_maxime_thiago
```

### 2. Environnement et dépendances

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```powershell
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Données

Les CSV du [Big Data Bowl 2023](https://www.kaggle.com/competitions/nfl-big-data-bowl-2023/data) doivent se trouver dans `data/` :

```
data/
├── games.csv
├── plays.csv
├── players.csv
├── pffScoutingData.csv
└── tracking/            # tracking_2021090900.csv, tracking_2021091200.csv, ...
```

Données ailleurs sur la machine ? Indiquez le dossier :

```bash
export NFL_DATA_DIR=/chemin/vers/data      # Windows : set NFL_DATA_DIR=C:\chemin\vers\data
```

## 🚀 Lancer le projet

```bash
source .venv/bin/activate        # si l'environnement n'est pas déjà actif
streamlit run app.py             # → http://localhost:8501
```

Autres commandes utiles :

```bash
streamlit run app.py --server.port 8080                 # changer de port
streamlit run app.py --server.address 0.0.0.0           # accessible depuis le réseau local
pytest                                                  # lancer les 50 tests
python scripts/calibrate.py                             # recalibrer le modèle YAC Potential
python scripts/fetch_headshots.py                       # régénérer les photos des joueurs
```

## ☁️ Déploiement

L'app lit **826 Mo de CSV** au démarrage : le choix de l'hébergeur dépend surtout de la place des données.

| Option | Données | Quand l'utiliser |
|---|---|---|
| **Docker sur un serveur / VPS** (recommandé) | volume monté, hors image | démo stable, contrôle total |
| **Hugging Face Spaces** (SDK Docker ou Streamlit) | dataset HF ou Git LFS | gratuit, simple à partager |
| **Streamlit Community Cloud** | dans le dépôt GitHub (limite 100 Mo/fichier, ~1 Go/repo) | uniquement avec un sous-ensemble des matchs |

### Option A — Docker (recommandé)

Créez un `Dockerfile` à la racine :

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV NFL_DATA_DIR=/data
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Puis, avec un `.dockerignore` contenant `data/`, `.venv/`, `.git/`, `__pycache__/` :

```bash
docker build -t yac-tracker .
docker run -d --name yac-tracker -p 8501:8501 -v "$(pwd)/data:/data:ro" --restart unless-stopped yac-tracker
# → http://IP_DU_SERVEUR:8501
```

Pour un nom de domaine en HTTPS, placez un reverse proxy (Caddy, par exemple : `caddy reverse-proxy --from demo.exemple.fr --to localhost:8501`). Streamlit utilise des WebSockets : le proxy doit les laisser passer (Caddy et nginx avec `Upgrade` le font).

### Option B — Streamlit Community Cloud (démo allégée)

1. Gardez dans `data/` un sous-ensemble (quelques fichiers `tracking_*.csv` + `games`, `plays`, `players`, `pffScoutingData`) pour rester sous les limites GitHub, ou passez par Git LFS.
2. Poussez sur GitHub : `git push origin main`.
3. Sur [share.streamlit.io](https://share.streamlit.io) → **New app** → choisissez le dépôt, la branche `main` et le fichier `app.py` → **Deploy**.

### Option C — Hugging Face Spaces

Créez un Space (SDK **Docker**), ajoutez le `Dockerfile` ci-dessus avec `EXPOSE 7860` et `--server.port=7860`, hébergez les CSV dans un dataset HF et téléchargez-les au build (`huggingface-cli download`) ou au démarrage vers `NFL_DATA_DIR`.

> ⚠️ Les données du Big Data Bowl sont soumises aux conditions de la compétition Kaggle : vérifiez que leur republication publique est autorisée avant de les mettre dans un dépôt ou un Space public.

## 🖱️ Utilisation

| Section | Ce qu'on y fait |
|---|---|
| **1 · Menu & contrôles** | Choisir match, quart-temps, down, distance, passeur, receveur, puis l'action. Lecteur fluide animé dans le navigateur : ▶ Lecture / ⏸ Pause (espace), ◀ ▶ image par image (flèches), 🎯 saut au lancer, vitesse ×0,25 / ×0,5 / ×1, curseur sur le `frameId`. |
| **2 · Visualisation** | À gauche le terrain (attaque 🔵, défense 🟠, receveur ciblé 🟡, ballon 🟤, trajectoires, lien pointillé vers le défenseur le plus proche). À droite la télémétrie : séparation, vitesse, phase de jeu, YAC Potential et courbe de séparation avec barre verticale à l'instant présent. « Options du QB » affiche la séparation de chaque receveur éligible. |
| **3 · Analyse décisionnelle** | Une ligne par passe (ou, en vue « Action sélectionnée », par moment clé). **Un clic sur un moment remonte au lecteur et le place à l'image exacte.** |

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
