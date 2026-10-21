"""YAC Potential & QB Decision Tracker — tableau de bord Streamlit pour coachs NFL.

    streamlit run app.py

(3) UI, de haut en bas :
    1. MENU & CONTRÔLES      sélecteurs (match, quart-temps, situation, passeur, receveur) + lecteur temporel
    2. VISUALISATION         terrain 2D animé (gauche) + télémétrie en temps réel (droite)
    3. ANALYSE DÉCISIONNELLE tableau façon "revue de partie" ; un clic recharge la section 2 à l'image exacte
"""
from __future__ import annotations

import time
from functools import partial

import numpy as np
import pandas as pd
import streamlit as st

from tracker import config as C
from tracker.analysis import GameAnalysis, PlayAnalysis, analyze_game, key_events
from tracker.data import Tables, avatar_url, load_tables, short_name
from tracker.evaluation import VERDICT_BY_KEY, VERDICTS
from tracker.field import build_field_figure, build_separation_figure

st.set_page_config(page_title="YAC Potential & QB Decision Tracker", page_icon="🏈", layout="wide",
                   initial_sidebar_state="collapsed")

ALL = "Tous"
QUARTERS = ["Q1", "Q2", "Q3", "Q4", "OT"]
DOWNS = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4}
DISTANCES = {"Courte (≤ 3 yd)": (0, 3), "Moyenne (4–7 yd)": (4, 7), "Longue (≥ 8 yd)": (8, 99)}
RESULT_FR = {"C": "Complète", "I": "Incomplète", "IN": "Interceptée"}
SPEEDS = {"0,25×": 0.25, "0,5×": 0.5, "1×": 1.0}
TABLE_MATCH, TABLE_PLAY = "Match filtré", "Action sélectionnée"
TICK_SECONDS = 0.1           # période cible du lecteur (10 images/s = temps réel à 1×)
PLOT_CONFIG = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False}

CSS = """
<style>
.block-container {padding-top: 2.4rem; max-width: 1480px;}
h1 {font-size: 1.85rem !important; padding: 0 0 .1rem 0 !important;}
.section {font-size: .74rem; letter-spacing: .14em; text-transform: uppercase; color: #8B949E; margin: 1.4rem 0 .45rem;}
[data-testid="stMetricValue"] {font-size: 1.6rem;}
[data-testid="stMetricLabel"] p {font-size: .82rem; color: #8B949E;}
.stAppDeployButton {display: none;}
</style>
"""


# --------------------------------------------------------------------------- données (en cache)
@st.cache_resource(show_spinner="Chargement des données…")
def get_tables() -> Tables:
    return load_tables()


@st.cache_resource(show_spinner="Analyse du match : tracking + évaluation de chaque lancer…", max_entries=6)
def get_game(game_id: int) -> GameAnalysis:
    return analyze_game(get_tables(), game_id)


# --------------------------------------------------------------------------- filtres (facettes)
FILTERS = {
    "quarter": lambda df, v: df["quarter"] == v,
    "down": lambda df, v: df["down"] == DOWNS[v],
    "distance": lambda df, v: df["yardsToGo"].between(*DISTANCES[v]),
    "passer": lambda df, v: df["passer"] == v,
    "receiver": lambda df, v: df["target"] == v,
}


def apply_filters(df: pd.DataFrame, selection: dict, skip: str | None = None) -> pd.DataFrame:
    for name, predicate in FILTERS.items():
        if name != skip and selection[name] != ALL:
            df = df[predicate(df, selection[name])]
    return df


def available_options(df: pd.DataFrame, name: str) -> list[str]:
    """Valeurs possibles d'un filtre pour les passes `df`."""
    if name == "quarter":
        return [q for q in QUARTERS if q in set(df["quarter"])]
    if name == "down":
        return [label for label, n in DOWNS.items() if n in set(df["down"])]
    if name == "distance":
        return [label for label, (lo, hi) in DISTANCES.items() if df["yardsToGo"].between(lo, hi).any()]
    return sorted(df["passer" if name == "passer" else "target"].unique())


def facet_options(summary: pd.DataFrame, selection: dict) -> dict[str, list[str]]:
    """Filtrage à facettes : les options de chaque filtre tiennent compte des QUATRE autres filtres."""
    return {name: [ALL] + available_options(apply_filters(summary, selection, skip=name), name) for name in FILTERS}


def play_label(row) -> str:
    return (f"{row.quarter} {row.clock} · {row.situation} · {short_name(row.passer)} → "
            f"{short_name(row.target)} · {RESULT_FR.get(row.pass_result, row.pass_result)}")


# --------------------------------------------------------------------------- callbacks
# Position de lecture : `ss.pos` (frameId). Le curseur `ss.frame` n'en est qu'une vue ; pendant la lecture il est
# remplacé par une barre de progression, si bien que la boucle de lecture ne modifie jamais l'état d'un widget.
# La lecture n'existe que dans l'exécution déclenchée par le bouton (`start_loop`) : toute autre interaction
# (filtre, tableau, pause...) relance le script avec `playing = False`.
def _bump_epoch() -> None:
    """Changer d'action via le menu réinitialise la sélection du tableau (évite une ligne surlignée périmée)."""
    st.session_state.table_epoch += 1


def _on_slider() -> None:
    st.session_state.pos = int(st.session_state.frame)


def _set_playing(playing: bool, first: int, last: int) -> None:
    """Idempotent : l'état voulu est fixé au rendu du bouton, pas déduit de l'état courant."""
    ss = st.session_state
    if playing and ss.pos >= last:
        ss.pos = first
    ss.start_loop = playing
    ss.play_pos, ss.last_tick = 0.0, time.perf_counter()


def _goto(frame: int) -> None:
    st.session_state.pos = int(frame)


def _step(delta: int, first: int, last: int) -> None:
    st.session_state.pos = int(np.clip(st.session_state.pos + delta, first, last))


def _on_table_select(table_key: str) -> None:
    """Clic sur une ligne du tableau -> la section 2 saute à l'action et à l'image de l'événement."""
    ss = st.session_state
    state = ss.get(table_key)
    rows = list(state["selection"]["rows"]) if state else []
    if not rows or rows[0] >= len(ss.table_targets):
        return
    play_id, frame = ss.table_targets[rows[0]]
    ss.sel_play, ss.pos = play_id, int(frame)
    ss.frame_play = (ss.sel_game, play_id)


# --------------------------------------------------------------------------- (3) UI : visualisation
class Player:
    """Section 2 : lecteur temporel, terrain animé et télémétrie.

    Le constructeur crée les contrôles et les emplacements (`st.empty`) à leur place dans la page et dessine
    l'image courante. `play()` est appelé en toute fin de script, une fois le tableau affiché : il redessine
    les emplacements à ~10 images/s. Chaque clic de l'utilisateur relance le script, ce qui interrompt la boucle.
    """

    def __init__(self, a: PlayAnalysis, controls) -> None:
        ss = st.session_state
        self.a, self.t = a, a.tracking
        self.first, self.last = int(a.frames[0]), int(a.frames[-1])
        ss.pos = int(np.clip(ss.pos, self.first, self.last))
        ss.frame = ss.pos
        first, last, t = self.first, self.last, self.t

        with controls:
            c_play, c_start, c_back, c_next, c_release, c_speed, c_opts = st.columns(
                [1.5, 0.7, 0.7, 0.7, 1.3, 2.6, 2.2], vertical_alignment="center")
            c_play.button("⏸ Pause" if ss.playing else "▶ Lecture", key="btn_play", type="primary", width="stretch",
                          on_click=_set_playing, args=(not ss.playing, first, last))
            c_start.button("⏮", key="btn_start", help="Revenir à la première image", width="stretch",
                           on_click=_goto, args=(first,))
            c_back.button("◀", key="btn_back", help="Image précédente", width="stretch",
                          on_click=_step, args=(-1, first, last))
            c_next.button("▶", key="btn_next", help="Image suivante", width="stretch",
                          on_click=_step, args=(1, first, last))
            c_release.button("🎯 Lancer", key="btn_release", help="Aller à l'image du lancer", width="stretch",
                             on_click=_goto, args=(int(t.frames[a.release_idx]),))
            c_speed.segmented_control("Vitesse", list(SPEEDS), key="speed_label", required=True,
                                      label_visibility="collapsed")
            c_opts.toggle("Options du QB", key="show_options",
                          help="Affiche la séparation de chaque receveur éligible (vert > 3 yd, orange, rouge < 1 yd).")
            self.timeline = st.empty()
            if not ss.playing:
                with self.timeline.container():
                    st.slider("Image (frameId)", first, last, step=1, key="frame", on_change=_on_slider,
                              help="Chaque image = 0,1 s de jeu.")

        m, d = a.meta, a.decision
        st.markdown(f"**{m['quarter']} {m['clock']} · {m['situation']}** · {m['possession']} attaque · "
                    f"{a.passer_name} → **{a.target_name}** ({a.target_pos})"
                    f"  \n{d.verdict.badge} — {d.text}")

        left, right = st.columns([5, 4], gap="large")
        self.field_slot = left.empty()
        row1, row2 = right.columns(2), right.columns(2)
        self.kpi = [row1[0].empty(), row1[1].empty(), row2[0].empty(), row2[1].empty()]
        self.caption_slot = right.empty()
        self.separation_slot = right.empty()
        self.draw(ss.pos)

    def draw(self, pos: int) -> None:
        """Dessine tous les éléments dépendant du temps à l'image `pos` (frameId)."""
        ss, a = st.session_state, self.a
        idx = self.t.index_of(pos)
        prev = max(idx - 1, 0)

        def trend(series):          # variation depuis l'image précédente ; rien si elle est invisible (< 0,05)
            delta = round(float(series[idx] - series[prev]), 1)
            return f"{delta:+.1f}" if idx and delta else None

        if ss.playing:
            self.timeline.progress((pos - self.first) / max(self.last - self.first, 1),
                                   text=f"Image {pos} / {self.last} · {a.time_at(idx):+.1f} s depuis le snap")
        self.field_slot.plotly_chart(build_field_figure(a, idx, ss.show_options), config=PLOT_CONFIG, theme=None,
                                     width="stretch")
        self.kpi[0].metric("Séparation actuelle", f"{a.sep[idx]:.1f} yd", trend(a.sep), border=True, height=118,
                           help="Distance au défenseur le plus proche (distance euclidienne).")
        self.kpi[1].metric("Vitesse du receveur", f"{a.speed[idx]:.1f} yd/s", trend(a.speed), delta_color="off",
                           border=True, height=118)
        self.kpi[2].metric("Phase de jeu", a.phase_at(idx), border=True, height=118, help=a.phase_detail(idx))
        self.kpi[3].metric("YAC Potential", f"{a.yac[idx]:.1f} yd", trend(a.yac), border=True, height=118,
                           help="Yards qu'on peut espérer gagner après la réception (séparation, espace devant, vitesse).")
        self.caption_slot.caption(f"Image {int(a.frames[idx])} / {self.last} · {a.time_at(idx):+.1f} s depuis le snap"
                                  f" · {a.phase_detail(idx)}")
        self.separation_slot.plotly_chart(build_separation_figure(a, idx), config=PLOT_CONFIG, theme=None,
                                          width="stretch")

    def play(self) -> None:
        """Lecture : image suivante au rythme réel du tracking (10 images/s), quelle que soit la latence."""
        ss = st.session_state
        if not ss.playing:
            return
        drawn = self.t.index_of(ss.pos)
        while ss.playing:
            time.sleep(max(0.0, TICK_SECONDS - (time.perf_counter() - ss.last_tick)))
            now = time.perf_counter()
            ss.play_pos += (now - ss.last_tick) * C.TRACKING_FPS * SPEEDS[ss.speed_label]
            ss.last_tick = now
            step = int(ss.play_pos)
            ss.play_pos -= step
            ss.pos = min(self.last, ss.pos + step)
            if ss.pos >= self.last:
                ss.playing = False
            if self.t.index_of(ss.pos) != drawn:    # Streamlit refuse deux graphiques identiques dans un même run
                drawn = self.t.index_of(ss.pos)
                self.draw(ss.pos)
        st.rerun()                  # fin de lecture : on redessine les contrôles (bouton "Lecture", curseur)


# --------------------------------------------------------------------------- (3) UI : analyse décisionnelle
def style_verdict(value: str) -> str:
    for v in VERDICTS:
        if value == v.badge:
            return f"background-color: {v.color}40; font-weight: 600;"
    return "color: #8B949E;"


def match_rows(tables: Tables, plays: pd.DataFrame, current: int) -> tuple[pd.DataFrame, list]:
    """Une ligne par passe : le QB est le "joueur" qui a pris la décision."""
    table = pd.DataFrame({
        "Moment": [("▶ " if r.playId == current else "") + f"{r.quarter} {r.clock}" for r in plays.itertuples()],
        "Situation": plays["situation"].to_numpy(),
        "Photo": [avatar_url(tables, r.passer_id, r.passer) for r in plays.itertuples()],
        "Joueur": plays["passer"].to_numpy(),
        "Évaluation": [VERDICT_BY_KEY[k].badge for k in plays["verdict"]],
        "Description": plays["short"].to_numpy(),
    })
    return table, [(int(r.playId), int(r.release_frame)) for r in plays.itertuples()]


def event_rows(tables: Tables, a: PlayAnalysis, current_frame: int) -> tuple[pd.DataFrame, list]:
    """Une ligne par moment clé de l'action sélectionnée (snap, fenêtre maximale, lancer, fin)."""
    events = key_events(a)
    table = pd.DataFrame({
        "Moment": [("▶ " if e.frame == current_frame else "") + f"{(e.frame - int(a.frames[a.snap_idx])) / C.TRACKING_FPS:+.1f} s"
                   for e in events],
        "Situation": [e.title for e in events],
        "Photo": [avatar_url(tables, e.player_id, e.player) for e in events],
        "Joueur": [e.player for e in events],
        "Évaluation": [e.badge for e in events],
        "Description": [e.description for e in events],
    })
    return table, [(a.tracking.play_id, e.frame) for e in events]


def render_decisions(tables: Tables, plays: pd.DataFrame, game: GameAnalysis, a: PlayAnalysis) -> None:
    ss = st.session_state
    st.markdown('<div class="section">3 · Analyse décisionnelle</div>', unsafe_allow_html=True)

    counts = plays["verdict"].value_counts()
    for col, v in zip(st.columns(len(VERDICTS)), VERDICTS):
        n = int(counts.get(v.key, 0))
        col.metric(v.badge, n, f"{n / len(plays):.0%} des passes", delta_color="off", delta_arrow="off", border=True)

    mode = st.segmented_control("Vue", [TABLE_MATCH, TABLE_PLAY], key="table_mode", required=True,
                                help="Match filtré : une ligne par passe (les filtres du haut s'appliquent). "
                                     "Action sélectionnée : les moments clés de l'action en cours.")
    if mode == TABLE_MATCH:
        table, targets = match_rows(tables, plays, a.tracking.play_id)
        scope = (tuple(plays["playId"]),)
    else:
        table, targets = event_rows(tables, a, ss.pos)
        scope = (a.tracking.play_id,)
    ss.table_targets = targets

    key = f"decisions_{ss.table_epoch}_{mode}_{ss.sel_game}_{hash(scope)}"
    st.caption("Cliquez sur une ligne : la visualisation saute à l'action et à l'image exacte de l'événement.")
    st.dataframe(
        table.style.map(style_verdict, subset=["Évaluation"]),
        key=key, on_select=partial(_on_table_select, key), selection_mode="single-row",
        hide_index=True, row_height=40, height=min(40 * (len(table) + 1) + 3, 440),
        column_config={
            "Moment": st.column_config.TextColumn("Moment", width=100),
            "Situation": st.column_config.TextColumn("Situation" if mode == TABLE_MATCH else "Événement",
                                                     width=95 if mode == TABLE_MATCH else 165),
            "Photo": st.column_config.ImageColumn("", width=48),
            "Joueur": st.column_config.TextColumn("Joueur", width=140),
            "Évaluation": st.column_config.TextColumn("Évaluation", width=165),
            "Description": st.column_config.TextColumn("Description", width="large"),
        },
    )

    with st.expander("Comment sont calculées les évaluations ?"):
        st.markdown(
            f"""
Chaque passe est jugée **à l'image du lancer** (`pass_forward`), avec ce que le QB avait sous les yeux.

| Évaluation | Règle |
|---|---|
| 💎 **Meilleur coup** `!!` | receveur ouvert (> {C.OPEN_SEP:.0f} yd) **et** YAC Potential ≥ {C.HIGH_YAC:.0f} yd |
| ✅ **Bon coup** | tout le reste (une fenêtre serrée sans meilleure option reste un bon coup) |
| ⚠️ **Erreur** `?` | receveur couvert (< {C.COVERED_SEP:.0f} yd) alors qu'un autre WR/TE était ouvert (> {C.OPEN_SEP:.0f} yd) |
| ❌ **Gaffe** `??` | séparation < {C.DANGER_SEP} yd, **ou** un défenseur à ≤ {C.CATCH_POINT_RADIUS:.0f} yd du point de réception estimé, **ou** interception |

**YAC Potential** = yards attendus après la réception ≈ `{C.YAC_MODEL['intercept']:+.2f} + {C.YAC_MODEL['sep']:.2f}·séparation + {C.YAC_MODEL['space']:.2f}·espace devant + {C.YAC_MODEL['speed']:.2f}·vitesse`
(plafonné à la distance jusqu'à la ligne de but). Le tracking s'arrête ~0,5 s après le lancer : le YAC n'est donc pas
mesuré, il est estimé. Détails : `README.md`.
"""
        )
    skipped = game.skipped
    if skipped:
        st.caption(f"{len(game.plays)} passes analysées sur {game.attempts} dans ce match "
                   f"({skipped} sans receveur identifiable : passes jetées ou balles détournées).")


# --------------------------------------------------------------------------- (3) UI : page
def init_state() -> None:
    defaults = {"playing": False, "speed_label": "0,5×", "show_options": True, "table_mode": TABLE_MATCH,
                "table_epoch": 0, "play_pos": 0.0, "last_tick": 0.0, "pos": 1, "frame": 1, "table_targets": []}
    for name in FILTERS:
        defaults[f"f_{name}"] = ALL
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def render_menu(tables: Tables):
    """Section 1 : sélecteurs. Retourne (conteneur du menu, analyse du match, passes filtrées, action choisie)."""
    ss = st.session_state
    st.markdown('<div class="section">1 · Menu &amp; contrôles</div>', unsafe_allow_html=True)
    menu = st.container(border=True)
    with menu:
        games = tables.games.set_index("gameId")["label"]
        c_game, c_q, c_down, c_dist, c_passer, c_recv = st.columns([2.4, 1, 1, 1.5, 1.9, 1.9])
        game_id = c_game.selectbox("Match", list(games.index), format_func=games.get, key="sel_game")
        if ss.get("_game") != game_id:                      # nouveau match : on repart de zéro
            for name in FILTERS:
                ss[f"f_{name}"] = ALL
            ss.update(_game=game_id, playing=False, sel_play=None, table_epoch=ss.table_epoch + 1)
        game = get_game(int(game_id))
        if game.summary.empty:
            st.warning("Aucune passe analysable dans ce match.")
            st.stop()

        for _ in range(3):                                   # options valides : un filtre peut en invalider un autre
            selection = {name: ss[f"f_{name}"] for name in FILTERS}
            options = facet_options(game.summary, selection)
            invalid = [name for name in FILTERS if ss[f"f_{name}"] not in options[name]]
            for name in invalid:
                ss[f"f_{name}"] = ALL
            if not invalid:
                break
        c_q.selectbox("Quart-temps", options["quarter"], key="f_quarter")
        c_down.selectbox("Down", options["down"], key="f_down")
        c_dist.selectbox("Distance", options["distance"], key="f_distance")
        c_passer.selectbox("Passeur", options["passer"], key="f_passer")
        c_recv.selectbox("Receveur", options["receiver"], key="f_receiver")

        plays = apply_filters(game.summary, {name: ss[f"f_{name}"] for name in FILTERS})
        if plays.empty:
            st.warning("Aucune passe ne correspond à ces filtres.")
            st.stop()
        play_ids = [int(p) for p in plays["playId"]]
        if ss.get("sel_play") not in play_ids:
            ss.sel_play = play_ids[0]
        labels = {int(r.playId): play_label(r) for r in plays.itertuples()}
        st.selectbox(f"Action ({len(play_ids)} passe{'s' if len(play_ids) > 1 else ''})", play_ids,
                     format_func=labels.get, key="sel_play", on_change=_bump_epoch)
    return menu, game, plays, game.plays[int(ss.sel_play)]


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("🏈 YAC Potential & QB Decision Tracker")
    st.caption("Rejouez chaque passe NFL (saison 2021, semaines 1-8), mesurez qui était ouvert et jugez la décision "
               "du quarterback — façon revue de partie d'échecs.")
    try:
        tables = get_tables()
    except FileNotFoundError as error:
        st.error(str(error))
        st.stop()

    init_state()
    ss = st.session_state
    ss.playing = bool(ss.pop("start_loop", False))   # la lecture ne survit qu'à l'exécution lancée par le bouton
    menu, game, plays, a = render_menu(tables)

    if ss.get("frame_play") != (ss.sel_game, a.tracking.play_id):   # nouvelle action : retour à la première image
        ss.pos = int(a.frames[0])
        ss.frame_play = (ss.sel_game, a.tracking.play_id)

    st.markdown('<div class="section">2 · Visualisation</div>', unsafe_allow_html=True)
    player = Player(a, menu)

    render_decisions(tables, plays, game, a)
    player.play()                   # en dernier : la boucle de lecture ne bloque pas l'affichage du tableau


main()
