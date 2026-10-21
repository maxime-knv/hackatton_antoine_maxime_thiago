"""Figures Plotly : terrain 2D vu de dessus et courbe de séparation.

Le terrain est tracé à la verticale (l'attaque monte), vue "derrière le QB" : la gauche et la droite
de l'écran sont celles de l'attaque. Repère d'affichage : u = 53,3 - y (horizontal), v = x (vertical).
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from . import config as C
from .analysis import PHASE_AIR, PlayAnalysis

FONT = "Source Sans, Source Sans Pro, system-ui, sans-serif"
PX_PER_YARD = 12.4
OPTIONS_TRACE = "options"   # bagues de séparation des options du QB (affichables / masquables)
DYNAMIC = "dyn"        # traces redessinées à chaque image par le lecteur (le reste du terrain est fixe)


def to_plot(xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Coordonnées terrain (x, y) -> (u, v) d'affichage : rotation de 90°, sans effet miroir."""
    xy = np.asarray(xy, dtype=float)
    u, v = C.FIELD_WIDTH - xy[..., 1], xy[..., 0]
    # un point isolé doit rester un float : un tableau 0-d serait sérialisé en binaire (bdata) et illisible
    # pour les attributs scalaires de Plotly (annotations...)
    return (float(u), float(v)) if xy.ndim == 1 else (u, v)


def _yard_label(x: float) -> str:
    yard = x - 10.0
    return str(int(round(yard if yard <= 50 else 100 - yard)))


# --------------------------------------------------------------------------- terrain
def _turf(fig: go.Figure, lo: float, hi: float) -> None:
    """Gazon à bandes de 5 yd, zones d'en-but, lignes de yards, marques latérales et numéros."""
    c = C.COLORS
    for start in range(int(lo // 5) * 5, int(hi) + 5, 5):
        a, b = max(start, lo), min(start + 5, hi)
        if a >= b:
            continue
        zone = start < 10 or start >= 110
        color = c["endzone"] if zone else (c["turf"] if (start // 5) % 2 == 0 else c["turf_alt"])
        fig.add_shape(type="rect", x0=0, x1=C.FIELD_WIDTH, y0=a, y1=b, fillcolor=color, line_width=0, layer="below")

    # lignes de yards (5 yd fines, 10 yd marquées) en deux traces seulement
    thin_u, thin_v, bold_u, bold_v = [], [], [], []
    for x in range(10, 111, 5):
        if lo <= x <= hi:
            target_u, target_v = (bold_u, bold_v) if x % 10 == 0 else (thin_u, thin_v)
            target_u += [0, C.FIELD_WIDTH, None]
            target_v += [x, x, None]
    fig.add_trace(go.Scatter(x=thin_u, y=thin_v, mode="lines", line=dict(color=c["line"], width=1),
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=bold_u, y=bold_v, mode="lines", line=dict(color=c["line"], width=2),
                             hoverinfo="skip", showlegend=False))

    # marques de yard (1 yd) sur les deux couloirs de hash et près des lignes de touche
    tick_u, tick_v = [], []
    for x in range(int(np.ceil(max(lo, 10))), int(min(hi, 110)) + 1):
        for centre in (23.58, 29.72):
            tick_u += [centre - 0.3, centre + 0.3, None]
            tick_v += [x, x, None]
        for edge in (0.0, C.FIELD_WIDTH):
            sign = 1 if edge == 0 else -1
            tick_u += [edge, edge + sign * 0.8, None]
            tick_v += [x, x, None]
    fig.add_trace(go.Scatter(x=tick_u, y=tick_v, mode="lines", line=dict(color=c["line"], width=1),
                             opacity=0.55, hoverinfo="skip", showlegend=False))

    numbers = [x for x in range(20, 101, 10) if lo + 1 <= x <= hi - 1]
    for u in (5.5, C.FIELD_WIDTH - 5.5):
        fig.add_trace(go.Scatter(
            x=[u] * len(numbers), y=numbers, mode="text", text=[_yard_label(x) for x in numbers],
            textfont=dict(color=c["line"], size=15, family=FONT), hoverinfo="skip", showlegend=False,
        ))


def _line_of_scrimmage(fig: go.Figure, a: PlayAnalysis) -> None:
    """Ligne de mêlée (trait plein) et ligne à gagner (pointillé), étiquetées au bord droit du terrain."""
    lo, hi = a.view
    los = a.tracking.los_x
    label = dict(showarrow=False, xanchor="right", font=dict(size=10, color="#FFFFFF", family=FONT),
                 bgcolor="rgba(13,17,23,0.55)", borderpad=1)
    fig.add_shape(type="line", x0=0, x1=C.FIELD_WIDTH, y0=los, y1=los, line=dict(color="#FFFFFF", width=3), layer="below")
    fig.add_annotation(x=C.FIELD_WIDTH - 0.3, y=los, text="Mêlée", yanchor="top", **label)
    first_down = los + float(a.meta["yards_to_go"])
    if lo < first_down < min(hi, C.GOAL_LINE_X):
        fig.add_shape(type="line", x0=0, x1=C.FIELD_WIDTH, y0=first_down, y1=first_down,
                      line=dict(color="#FFFFFF", width=2, dash="dot"), layer="below")
        fig.add_annotation(x=C.FIELD_WIDTH - 0.3, y=first_down, text="1er essai", yanchor="bottom", **label)


def _players(a: PlayAnalysis, idx: int) -> tuple[go.Scatter, go.Scatter]:
    t = a.tracking
    off, dfn = t.offense, t.defense
    others = [k for k in range(len(off.ids)) if k != a.target_k]

    def trace(squad, ks, name, color, rank) -> go.Scatter:
        u, v = to_plot(squad.xy[idx, ks])
        custom = [[squad.names[k], int(squad.jerseys[k]), squad.positions[k], round(float(squad.speed[idx, k]), 1)]
                  for k in ks]
        return go.Scatter(
            x=u, y=v, mode="markers+text", name=name, customdata=custom, legendrank=rank, meta=DYNAMIC,
            text=[str(j) for j in squad.jerseys[ks]], textposition="middle center",
            textfont=dict(size=8, color="#FFFFFF", family=FONT),
            marker=dict(size=17, color=color, line=dict(color="rgba(255,255,255,0.85)", width=1.2)),
            hovertemplate="<b>%{customdata[0]}</b><br>#%{customdata[1]} · %{customdata[2]}"
                          "<br>%{customdata[3]:.1f} yd/s<extra></extra>",
        )

    return (
        trace(off, others, "Attaque", C.COLORS["offense"], 1),
        trace(dfn, list(range(len(dfn.ids))), "Défense", C.COLORS["defense"], 2),
    )


def build_field_figure(a: PlayAnalysis, idx: int, show_options: bool = False) -> go.Figure:
    """Terrain à l'image `idx` : joueurs, trajectoires, ballon, lien receveur-défenseur le plus proche."""
    t, c = a.tracking, C.COLORS
    off, dfn = t.offense, t.defense
    lo, hi = a.view
    fig = go.Figure()
    _turf(fig, lo, hi)
    _line_of_scrimmage(fig, a)

    receiver_xy = off.xy[:, a.target_k]
    near_k = int(a.nearest_def[idx])

    # Options du QB : séparation de chaque receveur éligible (bague + valeur, jamais la couleur seule).
    # Toujours présente (masquable côté navigateur) pour que la composition des traces ne change jamais.
    ks = [k for k in t.route_ks if k != a.target_k]
    sep = a.route_sep[idx, [t.route_ks.index(k) for k in ks]]
    u, v = to_plot(off.xy[idx, ks])
    status = np.where(sep > C.OPEN_SEP, "#3FB950", np.where(sep >= C.COVERED_SEP, "#D29922", "#F85149"))
    fig.add_trace(go.Scatter(
        x=u, y=v, mode="markers+text", text=[f"{s:.1f}" for s in sep], textposition="bottom center", meta=DYNAMIC,
        name=OPTIONS_TRACE,
        textfont=dict(size=11, color="#FFFFFF", family=FONT), showlegend=False, hoverinfo="skip",
        visible=bool(show_options),
        marker=dict(size=30, color="rgba(0,0,0,0)", line=dict(color=list(status), width=2.5)),
    ))

    # Trajectoires : receveur (jaune), défenseur direct (orange), ballon (marron)
    for xy, color in ((receiver_xy[: idx + 1], c["target"]), (dfn.xy[: idx + 1, a.direct_k], c["defense"])):
        u, v = to_plot(xy)
        fig.add_trace(go.Scatter(x=u, y=v, mode="lines", line=dict(color=color, width=3), opacity=0.9,
                                 hoverinfo="skip", showlegend=False, meta=DYNAMIC))
    label = "Réception" if a.landing.observed else "Réception estimée"
    in_flight = idx >= a.release_idx
    landing_u, landing_v = to_plot(np.array(a.landing.xy))
    nothing = ([None], [None])
    # toujours présentes (vides avant le lancer) : la composition des traces ne change jamais pendant la lecture
    trail = to_plot(t.ball_xy[a.release_idx: idx + 1]) if in_flight else nothing
    fig.add_trace(go.Scatter(x=trail[0], y=trail[1], mode="lines", line=dict(color=c["ball"], width=3.5),
                             hoverinfo="skip", showlegend=False, meta=DYNAMIC))
    ball_u, ball_v = to_plot(t.ball_xy[idx])
    fig.add_trace(go.Scatter(x=[ball_u, landing_u] if in_flight else [None], y=[ball_v, landing_v] if in_flight else [None],
                             mode="lines", line=dict(color=c["ball"], width=2.5, dash="dot"),
                             hoverinfo="skip", showlegend=False, meta=DYNAMIC))
    fig.add_trace(go.Scatter(
        x=[landing_u] if in_flight else [None], y=[landing_v] if in_flight else [None], mode="markers",
        name=label, legendrank=7, hovertemplate=f"{label}<extra></extra>", meta=DYNAMIC,
        marker=dict(symbol="x", size=13, color="#FFFFFF", line=dict(color=c["ball"], width=2.5)),
    ))

    # Lien pointillé receveur ciblé <-> défenseur le plus proche, avec la distance
    ru, rv = to_plot(receiver_xy[idx])
    du, dv = to_plot(dfn.xy[idx, near_k])
    fig.add_trace(go.Scatter(x=[ru, du], y=[rv, dv], mode="lines", line=dict(color="#FFFFFF", width=2, dash="dot"),
                             hoverinfo="skip", showlegend=False, meta=DYNAMIC))
    # étiquette de distance posée juste derrière le défenseur, dans l'axe receveur -> défenseur
    # (une trace de texte, pas une annotation : le lecteur ne met à jour que les traces)
    gap = float(np.hypot(du - ru, dv - rv))
    ux, uy = ((du - ru) / gap, (dv - rv) / gap) if gap > 1e-6 else (0.0, 1.0)
    fig.add_trace(go.Scatter(
        x=[du + 1.5 * ux], y=[dv + 1.5 * uy], mode="text", text=[f"<b>{a.sep[idx]:.1f} yd</b>"], hoverinfo="skip",
        showlegend=False, textfont=dict(size=12, color="#FFFFFF", family=FONT), meta=DYNAMIC,
    ))

    offense_trace, defense_trace = _players(a, idx)
    fig.add_trace(defense_trace)
    fig.add_trace(offense_trace)

    # le nom du receveur se place du côté opposé au défenseur (pas de chevauchement avec la distance),
    # et vers l'intérieur du terrain quand il longe une ligne de touche (pas de nom rogné)
    if ru < 9:
        name_side = "middle right"
    elif ru > C.FIELD_WIDTH - 9:
        name_side = "middle left"
    else:
        name_side = "bottom center" if dv > rv else "top center"
    fig.add_trace(go.Scatter(
        x=[ru], y=[rv], mode="markers+text", name="Receveur ciblé", legendrank=3,
        text=[f"<b>{a.target_name}</b>"], textposition=name_side,
        textfont=dict(size=12, color="#FFFFFF", family=FONT), meta=DYNAMIC,
        marker=dict(size=20, color=c["target"], line=dict(color="#FFFFFF", width=2.5)),
        customdata=[[a.target_name, int(off.jerseys[a.target_k]), a.target_pos, round(float(a.speed[idx]), 1)]],
        hovertemplate="<b>%{customdata[0]}</b> (cible)<br>#%{customdata[1]} · %{customdata[2]}"
                      "<br>%{customdata[3]:.1f} yd/s<extra></extra>",
    ))
    bu, bv = to_plot(t.ball_xy[idx])
    fig.add_trace(go.Scatter(
        x=[bu], y=[bv], mode="markers", name="Ballon", legendrank=4, meta=DYNAMIC,
        marker=dict(symbol="diamond-wide", size=17, color=c["ball"], line=dict(color="#FFFFFF", width=2)),
        hovertemplate="Ballon<extra></extra>",
    ))

    height = int((hi - lo) * PX_PER_YARD) + 44
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=34, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=c["turf"],
        font=dict(family=FONT, color=c["ink"]), uirevision=f"{t.game_id}-{t.play_id}", hovermode="closest",
        legend=dict(orientation="h", x=0, y=1.0, yanchor="bottom", font=dict(size=12), itemsizing="constant"),
        xaxis=dict(range=[0, C.FIELD_WIDTH], visible=False, fixedrange=True, constrain="domain"),
        yaxis=dict(range=[lo, hi], visible=False, fixedrange=True, scaleanchor="x", scaleratio=1, constrain="domain"),
    )
    return fig


# --------------------------------------------------------------------------- courbe de séparation
def build_separation_figure(a: PlayAnalysis, idx: int) -> go.Figure:
    """Séparation du receveur ciblé au cours de l'action, avec une barre verticale à l'instant présent."""
    c = C.COLORS
    seconds = (np.arange(len(a.frames)) - a.snap_idx) / C.TRACKING_FPS
    now = seconds[idx]
    ceiling = max(6.0, float(np.ceil(a.sep.max() + 0.5)))
    release_t = seconds[a.release_idx]
    note = dict(showarrow=False, font=dict(size=10, color=c["muted"], family=FONT))
    fig = go.Figure()

    # le ballon est en l'air à partir du lancer
    fig.add_vrect(x0=release_t, x1=seconds[-1] + 0.05, fillcolor="rgba(168,96,42,0.16)", line_width=0, layer="below")
    fig.add_annotation(x=seconds[-1], y=ceiling, text=PHASE_AIR.lower(), xanchor="right", yanchor="top", **note)
    for level in (C.COVERED_SEP, C.OPEN_SEP):
        fig.add_hline(y=level, line=dict(color=c["muted"], width=1, dash="dot"))
    for when, text in ((0.0, "snap"), (release_t, "lancer")):
        fig.add_vline(x=when, line=dict(color=c["muted"], width=1))
        fig.add_annotation(x=when, y=0, text=text, xanchor="left", yanchor="bottom", xshift=3, **note)

    fig.add_trace(go.Scatter(
        x=seconds, y=a.sep, mode="lines", line=dict(color=c["target"], width=2.5, shape="spline", smoothing=0.4),
        customdata=a.frames, hovertemplate="<b>%{y:.1f} yd</b> · image %{customdata} · %{x:+.1f} s<extra></extra>",
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(x=[now, now], y=[0, ceiling], mode="lines", line=dict(color="#FFFFFF", width=1.5),
                             showlegend=False, hoverinfo="skip", meta=DYNAMIC))
    fig.add_trace(go.Scatter(
        x=[now], y=[a.sep[idx]], mode="markers", showlegend=False, hoverinfo="skip", meta=DYNAMIC,
        marker=dict(size=10, color=c["target"], line=dict(color="#0E1117", width=2)),
    ))

    # les seuils de l'évaluation se lisent sur l'axe, sans texte par-dessus la courbe
    ticks = {0: "0", C.COVERED_SEP: f"{C.COVERED_SEP:.0f} couvert", C.OPEN_SEP: f"{C.OPEN_SEP:.0f} ouvert"}
    ticks.update({v: str(v) for v in range(5, int(ceiling) + 1, 2)})
    axis = dict(gridcolor=c["grid"], gridwidth=1, zeroline=False, linecolor=c["grid"], fixedrange=True,
                tickfont=dict(size=11, color=c["muted"]), automargin=True)
    fig.update_layout(
        height=300, margin=dict(l=8, r=12, t=10, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=c["ink"]), uirevision="separation", hovermode="x",
        xaxis=dict(title=dict(text="Temps depuis le snap (s)", font=dict(size=11, color=c["muted"])),
                   range=[seconds[0], seconds[-1] + 0.05], **axis),
        yaxis=dict(title=dict(text="Séparation (yd)", font=dict(size=11, color=c["muted"])), range=[0, ceiling],
                   tickmode="array", tickvals=list(ticks), ticktext=list(ticks.values()), **axis),
    )
    return fig
