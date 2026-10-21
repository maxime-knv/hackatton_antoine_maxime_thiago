"""Lecteur d'action animé côté navigateur.

Toutes les images sont calculées une fois en Python puis jouées en JavaScript : pas d'aller-retour avec le serveur
Streamlit pendant la lecture, donc pas de clignotement. Seules les traces « dynamiques » (joueurs, ballon,
trajectoires...) sont mises à jour à chaque image ; le gazon reste en place.
"""
from __future__ import annotations

import json

import numpy as np

from . import config as C
from .analysis import PlayAnalysis
from .field import DYNAMIC, OPTIONS_TRACE, PX_PER_YARD, build_field_figure, build_separation_figure

PLOTLY_JS = "https://cdn.plot.ly/plotly-4.1.1.min.js"
CONTROLS_HEIGHT = 118
# attributs mis à jour image par image (dans cet ordre dans les tableaux JSON)
ATTRS = ("x", "y", "text", "customdata", "textposition", "marker.line.color")


def _plain(value):
    """Valeur Plotly (tableau numpy, tuple...) -> liste JSON, arrondie à 0,01 pour les nombres."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    out = []
    for item in value:
        if isinstance(item, (list, tuple, np.ndarray)):
            out.append(_plain(item))
        elif isinstance(item, (float, np.floating)):
            out.append(None if np.isnan(item) else round(float(item), 2))
        elif isinstance(item, np.integer):
            out.append(int(item))
        else:
            out.append(item)
    return out


def _frame_payload(fig) -> list[list]:
    """Pour chaque trace dynamique : [x, y, text, customdata, textposition, marker.line.color] (null si absent)."""
    payload = []
    for trace in fig.data:
        if trace.meta != DYNAMIC:
            continue
        line_color = trace.marker.line.color if trace.marker is not None and trace.marker.line is not None else None
        position = trace.textposition
        values = [trace.x, trace.y, trace.text, trace.customdata,
                  [position] if isinstance(position, str) else position,
                  list(line_color) if isinstance(line_color, (list, tuple, np.ndarray)) else None]
        payload.append([_plain(v) for v in values])
    return payload


def _dynamic_indices(fig) -> list[int]:
    return [i for i, trace in enumerate(fig.data) if trace.meta == DYNAMIC]


def _signed(value: float) -> str | None:
    return f"{value:+.1f}" if abs(value) >= 0.05 else None


def _kpis(a: PlayAnalysis) -> list[dict]:
    rows = []
    for idx in range(len(a.frames)):
        prev = max(idx - 1, 0)
        rows.append({
            "frame": int(a.frames[idx]),
            "time": round(a.time_at(idx), 1),
            "sep": f"{a.sep[idx]:.1f}", "dsep": _signed(float(a.sep[idx] - a.sep[prev])) if idx else None,
            "speed": f"{a.speed[idx]:.1f}", "dspeed": _signed(float(a.speed[idx] - a.speed[prev])) if idx else None,
            "yac": f"{a.yac[idx]:.1f}", "dyac": _signed(float(a.yac[idx] - a.yac[prev])) if idx else None,
            "phase": a.phase_at(idx), "detail": a.phase_detail(idx),
        })
    return rows


def player_height(a: PlayAnalysis) -> int:
    return int((a.view[1] - a.view[0]) * PX_PER_YARD) + 44 + CONTROLS_HEIGHT


def build_player_html(a: PlayAnalysis, start_frame: int, nonce: int = 0) -> str:
    """Page HTML autonome du lecteur, positionnée sur l'image `start_frame` (frameId)."""
    n = len(a.frames)
    start = int(np.clip(a.tracking.index_of(start_frame), 0, n - 1))
    fields = [build_field_figure(a, i, True) for i in range(n)]
    seps = [build_separation_figure(a, i) for i in range(n)]
    field, sep = fields[start], seps[start]
    field.update_layout(uirevision=None)
    sep.update_layout(height=None, autosize=True, uirevision=None)
    data = {
        "n": n, "start": start, "snap": a.snap_idx, "release": a.release_idx, "last": int(a.frames[-1]),
        "fps": C.TRACKING_FPS, "key": f"{a.tracking.game_id}-{a.tracking.play_id}",
        "field": json.loads(field.to_json()), "sep": json.loads(sep.to_json()),
        "fieldDyn": _dynamic_indices(field),
        "optionsIdx": [i for i, trace in enumerate(field.data) if trace.name == OPTIONS_TRACE], "sepDyn": _dynamic_indices(sep),
        "fieldFrames": [_frame_payload(f) for f in fields], "sepFrames": [_frame_payload(f) for f in seps],
        "kpi": _kpis(a), "fieldHeight": field.layout.height,
    }
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    return (TEMPLATE.replace("__PLOTLY__", PLOTLY_JS).replace("__DATA__", blob).replace("__ATTRS__", json.dumps(ATTRS))
            .replace("__NONCE__", str(nonce)))


TEMPLATE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script src="__PLOTLY__"></script>
<style>
:root{--bg:#121821;--bg2:#171F2A;--line:#26303D;--ink:#E6EDF3;--muted:#8B949E;--accent:#3987E5;--good:#3FB950;--bad:#F85149;
  font-family:"Source Sans Pro","Source Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
*{box-sizing:border-box}
html,body{margin:0;background:transparent;color:var(--ink);overflow:hidden}
#yac-player{background:var(--bg);border:1px solid var(--line);border-radius:16px;padding:14px 16px 10px;
  display:flex;flex-direction:column;gap:12px;height:100vh;outline:none}
.bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:36px;min-width:36px;padding:0 12px;
  border-radius:10px;border:1px solid var(--line);background:var(--bg2);color:var(--ink);font:600 13px inherit;
  font-family:inherit;cursor:pointer;transition:background .15s,border-color .15s,transform .05s}
.btn:hover{background:#1f2a38;border-color:#35445a}.btn:active{transform:scale(.97)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff;min-width:112px}
.btn.primary:hover{background:#4b95ec}
.btn svg{width:15px;height:15px;fill:currentColor}
.seg{display:inline-flex;background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:2px}
.seg button{border:0;background:transparent;color:var(--muted);font:600 12px inherit;font-family:inherit;height:30px;
  padding:0 11px;border-radius:8px;cursor:pointer}
.seg button.on{background:#2a3a50;color:#fff}
.switch{display:inline-flex;align-items:center;gap:8px;color:var(--muted);font-size:13px;cursor:pointer;user-select:none;margin-left:auto}
.switch i{width:34px;height:20px;border-radius:99px;background:#2b3542;position:relative;transition:background .15s}
.switch i::after{content:"";position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:#fff;transition:left .15s}
.switch.on i{background:var(--accent)}.switch.on i::after{left:16px}.switch.on{color:var(--ink)}
.timeline{display:flex;align-items:center;gap:14px}
.clock{min-width:210px;font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.clock b{color:var(--ink);font-weight:600}
.track{position:relative;flex:1;height:26px}
.track input{position:absolute;inset:0;width:100%;margin:0;background:transparent;-webkit-appearance:none;appearance:none;cursor:pointer;height:26px}
.track input::-webkit-slider-runnable-track{height:6px;border-radius:99px;background:linear-gradient(to right,var(--accent) var(--p,0%),#2b3542 var(--p,0%))}
.track input::-moz-range-track{height:6px;border-radius:99px;background:#2b3542}
.track input::-moz-range-progress{height:6px;border-radius:99px;background:var(--accent)}
.track input::-webkit-slider-thumb{-webkit-appearance:none;width:16px;height:16px;margin-top:-5px;border-radius:50%;background:#fff;
  border:3px solid var(--accent);box-shadow:0 1px 4px rgba(0,0,0,.5)}
.track input::-moz-range-thumb{width:12px;height:12px;border-radius:50%;background:#fff;border:3px solid var(--accent)}
.mark{position:absolute;top:19px;transform:translateX(-50%);font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);pointer-events:none}
.mark::before{content:"";position:absolute;left:50%;top:-8px;width:1px;height:6px;background:var(--muted)}
.stage{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,5fr) minmax(0,4fr);gap:18px}
#field{min-width:0;border-radius:12px;overflow:hidden;background:#2D6A3E}
.side{display:flex;flex-direction:column;gap:10px;min-width:0;min-height:0}
.kpis{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.kpi{background:var(--bg2);border:1px solid var(--line);border-radius:12px;padding:10px 14px 11px;min-width:0}
.kpi label{display:block;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
.kpi .v{display:flex;align-items:baseline;gap:8px;margin-top:3px;font-size:27px;font-weight:600;line-height:1.15;font-variant-numeric:tabular-nums;white-space:nowrap}
.kpi .v small{font-size:13px;font-weight:500;color:var(--muted)}
.kpi .d{font-size:12px;font-weight:600;border-radius:99px;padding:1px 8px;background:#222c39;color:var(--muted)}
.kpi .d.up{background:#14361f;color:#56d364}.kpi .d.down{background:#43181a;color:#ff7b72}
.kpi .d:empty{display:none}
.caption{font-size:12px;color:var(--muted);padding:0 2px}
#sepbox{flex:1;min-height:150px;position:relative;background:var(--bg2);border:1px solid var(--line);border-radius:12px;overflow:hidden}
#sep{position:absolute;inset:4px}
.err{color:#ff7b72;font-size:13px;padding:20px}
@media(max-width:900px){.stage{grid-template-columns:1fr}}
</style></head>
<body>
<div id="yac-player" tabindex="0" data-nonce="__NONCE__">
  <div class="bar">
    <button class="btn primary" id="play" title="Lecture / pause (espace)"></button>
    <button class="btn" id="first" title="Première image"><svg viewBox="0 0 16 16"><path d="M3 2h2v12H3zM14 2v12L6 8z"/></svg></button>
    <button class="btn" id="back" title="Image précédente (←)"><svg viewBox="0 0 16 16"><path d="M11 2v12L3 8z"/></svg></button>
    <button class="btn" id="next" title="Image suivante (→)"><svg viewBox="0 0 16 16"><path d="M5 2v12l8-6z"/></svg></button>
    <button class="btn" id="release" title="Aller à l'image du lancer"><svg viewBox="0 0 16 16"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 2a5 5 0 110 10A5 5 0 018 3zm0 2a3 3 0 100 6 3 3 0 000-6z"/></svg>Lancer</button>
    <div class="seg" id="speed" title="Vitesse de lecture"></div>
    <div class="switch" id="opts" title="Séparation de chaque receveur éligible (vert &gt; 3 yd, orange, rouge &lt; 1 yd)"><i></i>Options du QB</div>
  </div>
  <div class="timeline">
    <div class="clock" id="clock"></div>
    <div class="track"><input type="range" id="slider" min="0" step="1" value="0" aria-label="Image">
      <span class="mark" id="mSnap">snap</span><span class="mark" id="mRel">lancer</span></div>
  </div>
  <div class="stage">
    <div id="field"></div>
    <div class="side">
      <div class="kpis">
        <div class="kpi"><label>Séparation</label><div class="v"><span id="k_sep"></span><small>yd</small><span class="d" id="d_sep"></span></div></div>
        <div class="kpi"><label>Vitesse du receveur</label><div class="v"><span id="k_speed"></span><small>yd/s</small><span class="d" id="d_speed"></span></div></div>
        <div class="kpi" id="k_phase_box"><label>Phase de jeu</label><div class="v" style="font-size:21px;padding-top:5px"><span id="k_phase"></span></div></div>
        <div class="kpi"><label>YAC Potential</label><div class="v"><span id="k_yac"></span><small>yd</small><span class="d" id="d_yac"></span></div></div>
      </div>
      <div class="caption" id="caption"></div>
      <div id="sepbox"><div id="sep"></div></div>
    </div>
  </div>
</div>
<script>
const D = __DATA__, ATTRS = __ATTRS__;
const $ = id => document.getElementById(id);
const SPEEDS = {"0,25×":0.25,"0,5×":0.5,"1×":1};
const store = {get(k,f){try{return localStorage.getItem("yac."+k) ?? f}catch(e){return f}}, set(k,v){try{localStorage.setItem("yac."+k,v)}catch(e){}}};
let pos = D.start, playing = false, speed = store.get("speed","0,5×"), showOpts = store.get("opts","1")==="1", last = performance.now(), acc = 0, shown = -1;
if(!(speed in SPEEDS)) speed = "0,5×";

function pickAttrs(frames, dyn){
  const upd = {};
  ATTRS.forEach((a,k)=>{ if(frames.some(t=>t[k]!==null)) upd[a]=k; });
  return upd;
}
const fieldAttrs = pickAttrs(D.fieldFrames[0], D.fieldDyn), sepAttrs = pickAttrs(D.sepFrames[0], D.sepDyn);
function restyle(div, frames, dyn, attrs, i){
  const f = frames[i], upd = {};
  for(const a in attrs){ const k = attrs[a]; upd[a] = f.map(t => t[k]===null ? undefined : t[k]); }
  Plotly.restyle(div, upd, dyn);
}
function setDelta(id, v){
  const el = $(id); el.textContent = v ?? ""; el.className = "d" + (v ? (v[0]==="+" ? " up" : " down") : "");
}
function setFrame(i){
  i = Math.max(0, Math.min(D.n-1, Math.round(i))); if(i===shown) return; shown = i; pos = i;
  restyle($("field"), D.fieldFrames, D.fieldDyn, fieldAttrs, i);
  restyle($("sep"), D.sepFrames, D.sepDyn, sepAttrs, i);
  const k = D.kpi[i];
  $("k_sep").textContent = k.sep; $("k_speed").textContent = k.speed; $("k_yac").textContent = k.yac; $("k_phase").textContent = k.phase;
  setDelta("d_sep", k.dsep); setDelta("d_yac", k.dyac); $("d_speed").textContent = k.dspeed ?? ""; $("d_speed").className = "d";
  $("k_phase_box").title = k.detail;
  $("caption").textContent = k.detail.charAt(0).toUpperCase() + k.detail.slice(1);
  const sign = k.time>=0 ? "+" : "−";
  $("clock").innerHTML = "Image <b>"+k.frame+"</b> / "+D.last+" · <b>"+sign+Math.abs(k.time).toFixed(1)+" s</b> depuis le snap";
  const s = $("slider"); s.value = i; s.style.setProperty("--p", (D.n>1 ? 100*i/(D.n-1) : 0)+"%");
}
function renderPlay(){
  $("play").innerHTML = playing
    ? '<svg viewBox="0 0 16 16"><path d="M3 2h4v12H3zM9 2h4v12H9z"/></svg>Pause'
    : '<svg viewBox="0 0 16 16"><path d="M3 1.5v13l11-6.5z"/></svg>Lecture';
}
function play(on){
  if(on && pos>=D.n-1) setFrame(0);
  playing = on; acc = 0; last = performance.now(); renderPlay();
  if(on) requestAnimationFrame(tick);
}
function tick(now){
  if(!playing) return;
  acc += (now-last)/1000*D.fps*SPEEDS[speed]; last = now;
  const step = Math.floor(acc);
  if(step>0){ acc -= step; setFrame(Math.min(D.n-1, pos+step)); if(pos>=D.n-1){ play(false); return; } }
  requestAnimationFrame(tick);
}
function seek(i){ play(false); setFrame(i); }
function setOpts(on){
  showOpts = on; store.set("opts", on?"1":"0"); $("opts").classList.toggle("on", on);
  Plotly.restyle($("field"), {visible: on}, D.optionsIdx);
}

function init(){
  const cfg = {displayModeBar:false, scrollZoom:false, doubleClick:false, responsive:true};
  const fl = D.field.layout; fl.autosize = true; delete fl.width; fl.height = D.fieldHeight;
  Plotly.newPlot("field", D.field.data, fl, cfg);
  const sl = D.sep.layout; delete sl.height; delete sl.width; sl.autosize = true;
  Plotly.newPlot("sep", D.sep.data, sl, cfg);
  const sp = $("speed");
  Object.keys(SPEEDS).forEach(label => {
    const b = document.createElement("button"); b.textContent = label; b.className = label===speed ? "on" : "";
    b.onclick = () => { speed = label; store.set("speed", label); [...sp.children].forEach(c => c.className = c===b ? "on" : ""); acc = 0; };
    sp.appendChild(b);
  });
  const sl2 = $("slider"); sl2.max = D.n-1;
  $("mSnap").style.left = (100*D.snap/Math.max(D.n-1,1))+"%"; $("mRel").style.left = (100*D.release/Math.max(D.n-1,1))+"%";
  sl2.oninput = () => seek(+sl2.value);
  $("play").onclick = () => play(!playing);
  $("first").onclick = () => seek(0);
  $("back").onclick = () => seek(pos-1);
  $("next").onclick = () => seek(pos+1);
  $("release").onclick = () => seek(D.release);
  $("opts").onclick = () => setOpts(!showOpts);
  $("yac-player").addEventListener("keydown", e => {
    if(e.code==="Space"){ e.preventDefault(); play(!playing); }
    else if(e.code==="ArrowLeft"){ e.preventDefault(); seek(pos-1); }
    else if(e.code==="ArrowRight"){ e.preventDefault(); seek(pos+1); }
  });
  renderPlay(); setOpts(showOpts); setFrame(D.start);
  const fit = () => { Plotly.Plots.resize($("sep")); Plotly.Plots.resize($("field")); };
  requestAnimationFrame(fit); setTimeout(fit, 150);
  window.__yac = {seek, play, setOpts, get pos(){return pos}, get playing(){return playing}};
}
if(window.Plotly) init(); else document.body.innerHTML = '<div class="err">Plotly.js n\'a pas pu être chargé (connexion internet requise).</div>';
</script></body></html>
"""
