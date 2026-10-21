# 🏈 YAC Potential & QB Decision Tracker

> Rejouez chaque passe NFL, voyez **qui était ouvert** au moment du lancer et faites **noter la décision du quarterback** — comme une revue de partie d'échecs.

**Le but : donner à un coach un outil clé en main pour analyser le jeu de passe et améliorer les performances de son équipe.** Au lieu de fouiller des heures de vidéo, il peut :

- **isoler des actions** précises (match, quart-temps, down & distance, passeur, receveur) et les rejouer image par image ;
- **prendre de la hauteur** sur le jeu : une ligne par passe, classée *Meilleur coup / Bon coup / Erreur / Gaffe*, pour voir les tendances d'un match ou d'une saison ;
- **identifier les erreurs typiques** de certains joueurs (un QB qui force vers un receveur couvert, un receveur souvent collé à son défenseur) **et leurs bonnes actions**, pour les corriger ou les renforcer ;
- **disposer de toutes les données clés** (séparation, espace libre, vitesse, YAC Potential, options du QB à chaque instant) sans aucun calcul à faire soi-même.

![Aperçu du tableau de bord](assets/screenshot.png)

## 🎯 À quoi ça sert à un coach ?

- 🔎 **Revoir une action en 30 secondes** : terrain 2D animé, trajectoires, ballon, distance receveur ↔ défenseur à chaque image.
- 🧠 **Juger la lecture du QB** : qui était ouvert quand il a lâché le ballon ? Fallait-il jouer un autre receveur ?
- ⚡ **Repérer les erreurs récurrentes** : filtrez par match, quart-temps, down & distance, passeur, receveur ; le tableau classe chaque passe en *Meilleur coup / Bon coup / Erreur / Gaffe*.
- ✅ **Valoriser les bonnes décisions** : retrouvez les « Meilleur coup » d'un joueur pour les montrer en exemple à l'équipe.
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

Pour changer de port ou ouvrir l'app au réseau local :

```bash
streamlit run app.py --server.port 8080
streamlit run app.py --server.address 0.0.0.0
```

## 🖱️ Utiliser l'application

La page se lit de haut en bas, en trois sections.

### 1 · Menu & contrôles

Choisissez un **match**, puis affinez avec les filtres : **quart-temps**, **down**, **distance**, **passeur**, **receveur**. Les filtres s'adaptent entre eux (seules les valeurs possibles sont proposées). Le menu **Action** liste ensuite les passes qui correspondent.

### 2 · Visualisation

Le lecteur rejoue l'action image par image (10 images par seconde).

| Contrôle | Effet |
|---|---|
| ▶ / ⏸ (ou `espace`) | Lecture / pause |
| ◀ ▶ (ou flèches) | Image précédente / suivante |
| ⏮ | Retour à la première image |
| 🎯 **Lancer** | Saute à l'image où le QB lâche le ballon |
| Vitesse | ×0,25 · ×0,5 · ×1 |
| Curseur | Navigation libre dans l'action (repères *snap* et *lancer*) |
| **Options du QB** | Affiche la séparation de chaque receveur éligible |

Au-dessus du lecteur, un bandeau résume l'action : moment, situation, QB → receveur ciblé, **évaluation** et explication en une phrase.

### 3 · Analyse décisionnelle

- Quatre compteurs donnent la répartition des évaluations (*Meilleur coup / Bon coup / Erreur / Gaffe*) sur les passes filtrées.
- Le tableau a deux vues :
  - **Match filtré** : une ligne par passe, avec le QB et son évaluation. C'est la vue pour repérer les tendances.
  - **Action sélectionnée** : les moments clés de l'action en cours (snap, receveur le plus ouvert, lancer, ballon arrivé, fin du tracking).
- **Un clic sur une ligne remonte au lecteur et le place à l'image exacte.**

## 🧮 Comprendre ce qui est affiché

### Sur le terrain

| Élément | Signification |
|---|---|
| 🔵 Points bleus | Joueurs de l'attaque |
| 🟠 Points oranges | Joueurs de la défense |
| 🟡 Point jaune | Receveur ciblé par la passe |
| 🟤 Point marron | Ballon |
| Traînées | Trajectoires récentes des joueurs |
| Lien pointillé | Relie le receveur ciblé au défenseur le plus proche |
| ✕ | Point de réception **estimé** (voir les limites plus bas) |

Le terrain est toujours orienté pour que l'attaque aille vers la droite.

### Les indicateurs du panneau de droite

Chaque indicateur se met à jour à chaque image ; la petite pastille à côté de la valeur indique la variation par rapport à l'image précédente (vert : hausse, rouge : baisse).

- **Séparation** (yd) : distance entre le receveur ciblé et le défenseur le plus proche. Plus elle est grande, plus le receveur est libre. Repères utilisés par l'outil : **> 3 yd = ouvert**, **< 1 yd = couvert**, **< 0,5 yd = fenêtre quasi inexistante**.
- **Vitesse du receveur** (yd/s) : sa vitesse instantanée, donc sa capacité à accélérer après la réception.
- **Phase de jeu** :
  - *Pré-passe* : avant le lancer (au survol : « avant le snap » ou « le QB lit la défense ») ;
  - *Ballon en l'air* : la passe est partie (au survol : « fin du tracking » sur la dernière image) ;
  - *Réception / YAC* : le ballon est arrivé. Elle n'apparaît que sur les passes très courtes, car le tracking s'arrête environ 0,5 s après le lancer.
- **YAC Potential** (yd) : yards que le receveur peut espérer gagner **après** la réception (détail ci-dessous).
- **Courbe de séparation** : évolution de la séparation du receveur ciblé depuis le snap, avec les repères *snap* et *lancer* et une barre verticale à l'image courante. Elle montre à quel moment le receveur s'est libéré, et s'il l'était encore au lancer.
- **Options du QB** (interrupteur) : séparation de chaque receveur éligible, en vert (> 3 yd), orange ou rouge (< 1 yd). C'est ce que le QB avait comme choix à l'instant du lancer.

### 🏃 YAC Potential

*YAC* signifie *yards after catch* : les yards gagnés après la réception. Le YAC Potential en est une **estimation** à partir de trois ingrédients :

1. la **séparation** (plafonnée à 8 yd) ;
2. l'**espace libre devant** le receveur : distance au premier défenseur situé devant lui, vers l'en-but adverse (plafonnée à 15 yd) ;
3. sa **vitesse**.

`YAC ≈ −0,99 + 0,24 × séparation + 0,27 × espace devant + 0,51 × vitesse`, plafonné à la distance jusqu'à la ligne de but.

Les coefficients sont ajustés sur les passes de la base (`python scripts/calibrate.py` les recalcule). Un **YAC Potential ≥ 5 yd** est considéré comme élevé : c'est à peu près la moyenne observée sur les données.

### 🏅 Les évaluations

La passe est jugée **à l'image du lancer**, avec ce que le QB avait sous les yeux.

| Évaluation | Règle | Ce que ça veut dire pour le coach |
|---|---|---|
| 💎 **Meilleur coup** `!!` | receveur ouvert (> 3 yd) **et** YAC Potential ≥ 5 yd | Le QB a trouvé un receveur libre qui peut gagner des yards après la réception : à montrer en exemple |
| ✅ **Bon coup** | tout le reste | Décision correcte. Une fenêtre serrée sans meilleure option reste un bon coup |
| ⚠️ **Erreur** `?` | receveur couvert (< 1 yd) alors qu'un autre WR/TE était ouvert (> 3 yd) | Le QB a forcé vers un receveur marqué alors qu'une meilleure option existait (l'outil la nomme) |
| ❌ **Gaffe** `??` | séparation < 0,5 yd, **ou** défenseur à ≤ 2 yd du point de réception estimé, **ou** interception | Passe très risquée : le ballon arrive dans une zone déjà occupée par la défense |

En cas de cumul, l'ordre de priorité est : Gaffe > Erreur > Meilleur coup > Bon coup. Seuls les WR et TE comptent comme alternatives « primaires » (les RB sont des solutions de repli). Tous les seuils se modifient dans `tracker/config.py`.

### Les moments clés (vue « Action sélectionnée »)

| Moment | Contenu |
|---|---|
| **Snap** | Le QB, plus la formation, le personnel offensif face au défensif, et la couverture de la défense |
| **Receveur le plus ouvert** | Le moment où le receveur ciblé atteint sa séparation maximale avant le lancer (affiché seulement si ce n'est pas le lancer lui-même) |
| **Lancer** | L'évaluation et son explication complète |
| **Ballon arrivé** | Séparation et YAC Potential à l'arrivée (seulement quand l'arrivée est mesurée) |
| **Fin du tracking** | Description officielle de l'action et position estimée de la réception |

## 📚 Les données (et leurs limites)

- **Big Data Bowl 2023** : saison NFL 2021, semaines 1 à 8, tracking à 10 images par seconde, données de scouting PFF.
- ⏱️ **Le tracking s'arrête environ 0,5 s après le lancer.** La réception et le YAC ne sont donc pas mesurés. Le YAC Potential est un *modèle*, et le point de réception (✕) est *estimé* en prolongeant la trajectoire du ballon.
- 🎯 **Le receveur ciblé n'est pas fourni** : il est retrouvé en croisant la description de l'action avec les receveurs présents (≈ 96 % des passes). Les passes jetées ou sans cible nommée sont écartées ; le nombre de passes écartées est indiqué sous le tableau.
- 📐 **Vue 2D** : la hauteur du ballon est inconnue. Un défenseur « sur la trajectoire » peut être battu par un lancer haut.
- 🖼️ **Photos** : issues de nflverse. Sans photo, une icône par défaut s'affiche.
