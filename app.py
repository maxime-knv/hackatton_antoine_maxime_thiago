"""YAC Potential & QB Decision Tracker — tableau de bord Streamlit pour coachs NFL.

    streamlit run app.py

(3) UI, de haut en bas :
    1. MENU & CONTRÔLES      sélecteurs (match, quart-temps, situation, passeur, receveur) + lecteur temporel
    2. VISUALISATION         terrain 2D animé (gauche) + télémétrie en temps réel (droite)
    3. ANALYSE DÉCISIONNELLE tableau façon "revue de partie" ; un clic recharge la section 2 à l'image exacte
"""
from __future__ import annotations

from functools import partial

import pandas as pd
import streamlit as st

from tracker import config as C
from tracker.analysis import GameAnalysis, PlayAnalysis, analyze_game, key_events
from tracker.data import Tables, avatar_url, load_tables, short_name
from tracker.evaluation import VERDICT_BY_KEY, VERDICTS
from tracker.player import build_player_html, player_height

st.set_page_config(page_title="YAC Potential & QB Decision Tracker", page_icon="🏈", layout="wide",
                   initial_sidebar_state="collapsed")

ALL = "Tous"
QUARTERS = ["Q1", "Q2", "Q3", "Q4", "OT"]
DOWNS = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4}
DISTANCES = {"Courte (≤ 3 yd)": (0, 3), "Moyenne (4–7 yd)": (4, 7), "Longue (≥ 8 yd)": (8, 99)}
RESULT_FR = {"C": "Complète", "I": "Incomplète", "IN": "Interceptée"}
TABLE_MATCH, TABLE_PLAY = "Match filtré", "Action sélectionnée"

CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1480px;}
h1 {font-size: 1.9rem !important; font-weight: 700 !important; letter-spacing: -.01em; padding: 0 0 .1rem 0 !important;}
.section {font-size: .72rem; font-weight: 600; letter-spacing: .16em; text-transform: uppercase; color: #8B949E;
          margin: 1.8rem 0 .6rem; display: flex; align-items: center; gap: .8rem;}
.section::after {content: ""; flex: 1; height: 1px; background: #26303D;}
[data-testid="stMetricValue"] {font-size: 1.6rem;}
[data-testid="stMetricLabel"] p {font-size: .82rem; color: #8B949E;}
[data-testid="stMetric"] {background: #121821; border-radius: 12px;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 14px;}
[data-testid="stDataFrame"] {border-radius: 12px; overflow: hidden;}
.verdict {background: #121821; border: 1px solid #26303D; border-radius: 12px; padding: .7rem 1rem; margin-bottom: .8rem;}
.verdict .who {color: #8B949E; font-size: .85rem;}
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
# Le lecteur tourne dans le navigateur (tracker/player.py) : Streamlit ne fait que lui indiquer l'image de départ
# (`ss.pos`, un frameId). Un clic sur le tableau change cette image et fait remonter la page jusqu'au lecteur.
def _bump_epoch() -> None:
    """Changer d'action via le menu réinitialise la sélection du tableau (évite une ligne surlignée périmée)."""
    st.session_state.table_epoch += 1


def _on_table_select(table_key: str) -> None:
    """Clic sur une ligne du tableau -> le lecteur saute à l'action et à l'image de l'événement, en haut de page."""
    ss = st.session_state
    state = ss.get(table_key)
    selection = state["selection"] if state else {}
    rows = list(selection.get("rows", [])) or [cell[0] for cell in selection.get("cells", [])]   # case cochée ou clic
    if not rows or rows[0] >= len(ss.table_targets):
        return
    play_id, frame = ss.table_targets[rows[0]]
    ss.sel_play, ss.pos = play_id, int(frame)
    ss.frame_play = (ss.sel_game, play_id)
    ss.scroll_count += 1
    ss.scroll_pending = True
    ss.table_epoch += 1            # nouvelle clé de tableau : la ligne se désélectionne, un nouveau clic refonctionne


SCROLL_JS = """<script>/* {n} */
setTimeout(function () {{      // laisse le lecteur se recomposer (sa hauteur peut changer) avant de mesurer
  const doc = window.parent.document;
  const target = doc.getElementById("player-anchor");
  if (!target) return;
  const main = doc.querySelector('[data-testid="stMain"]') || doc.scrollingElement;
  const top = target.getBoundingClientRect().top - main.getBoundingClientRect().top + main.scrollTop - 70;
  main.scrollTo({{top: Math.max(top, 0), behavior: "smooth"}});
}}, 350);
</script>"""


# --------------------------------------------------------------------------- (3) UI : visualisation
@st.cache_data(show_spinner="Préparation du lecteur…", max_entries=24)
def player_page(game_id: int, play_id: int, start_frame: int) -> tuple[str, int]:
    a = get_game(game_id).plays[play_id]
    return build_player_html(a, start_frame), player_height(a)


def render_player(a: PlayAnalysis, game_id: int) -> None:
    """Section 2 : lecteur animé (navigateur) précédé du résumé de la décision."""
    ss = st.session_state
    m, d = a.meta, a.decision
    st.markdown(f"""<div class="verdict"><div class="who">{m['quarter']} {m['clock']} · {m['situation']} · {m['possession']} attaque
 · {a.passer_name} → <b>{a.target_name}</b> ({a.target_pos})</div>
<div style="margin-top:.15rem">{d.verdict.badge} — {d.text}</div></div>""", unsafe_allow_html=True)
    page, height = player_page(game_id, a.tracking.play_id, int(ss.pos))
    st.iframe(page, height=height)


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
    st.caption("Cliquez sur un moment : la visualisation saute à l'action et à l'image exacte de l'événement.")
    st.dataframe(
        table.style.map(style_verdict, subset=["Évaluation"]),
        key=key, on_select=partial(_on_table_select, key), selection_mode=["single-row", "single-cell"],
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
    defaults = {"table_mode": TABLE_MATCH, "table_epoch": 0, "pos": 1, "table_targets": [], "scroll_count": 0,
                "scroll_pending": False}
    for name in FILTERS:
        defaults[f"f_{name}"] = ALL
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def render_menu(tables: Tables):
    """Section 1 : sélecteurs. Retourne (analyse du match, passes filtrées, action choisie)."""
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
            ss.update(_game=game_id, sel_play=None, table_epoch=ss.table_epoch + 1)
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
    return game, plays, game.plays[int(ss.sel_play)]


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
    game, plays, a = render_menu(tables)

    if ss.get("frame_play") != (ss.sel_game, a.tracking.play_id):   # nouvelle action : retour à la première image
        ss.pos = int(a.frames[0])
        ss.frame_play = (ss.sel_game, a.tracking.play_id)

    st.markdown('<div class="section" id="player-anchor">2 · Visualisation</div>', unsafe_allow_html=True)
    render_player(a, int(ss.sel_game))
    render_decisions(tables, plays, game, a)
    if ss.pop("scroll_pending", False):                 # clic sur le tableau : on remonte jusqu'au lecteur
        st.html(SCROLL_JS.format(n=ss.scroll_count), unsafe_allow_javascript=True)


main()
