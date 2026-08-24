"""Build the Neuro Atlas hub — one page holding every human nervous-system viewer.

Assembles `site/dist/`:

    index.html            the hub: clickable nervous-system map + system list
    404.html              small "not found" that links home
    <slug>/index.html     a copy of each viewer, with navigation injected

Every viewer output in this repo is a *body fragment* — it starts at `<title>`
and ends at `</script>`, with no doctype/html/head/body tags and no charset
meta. So the injector appends the nav markup at the end of the copy and
prepends a charset meta at the front. It works on the copy in `dist/`, never
on the original, which matters because `limbic/` and `whole_brain/` are orphan
outputs with no build script left in the repo — they cannot be regenerated.

Adding a system later = one entry in SYSTEMS (plus a hotspot in the map if it
has an obvious anatomical home), then rebuild and redeploy.

    py -3.13 site/build_hub.py
    npx wrangler pages deploy site/dist --project-name=neuro-atlas
"""

from __future__ import annotations

import math
import shutil
import sys
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent
REPO = SITE_DIR.parent
DIST = SITE_DIR / "dist"

# --- the registry -----------------------------------------------------------
# `src` is repo-relative. `accent` is the viewer's own accent colour where it
# has one, so a card and its page match. `hotspot` names the map element that
# links here (None = listed but not on the map).
SYSTEMS = [
    {
        "slug": "auditory",
        "src": "human/outputs/auditory_system/human_auditory_system_3d.html",
        "accent": "#e0a458", "group": "input", "hotspot": "ear",
        "name": {"en": "Auditory &amp; vestibular", "zh": "聽覺與前庭系統"},
        "short": {"en": "Hearing", "zh": "聽覺"},
        "route": {"en": "cochlea → brainstem → MGB → temporal cortex",
                  "zh": "耳蝸 → 腦幹 → 內側膝狀體 → 顳葉"},
        "fact": {"en": "Full decussation at the trapezoid body — each ear reaches both cortices",
                 "zh": "在腦幹梯形體完全交叉,每隻耳朵的訊息都會抵達兩側皮質"},
        "source": "MNI152 · Harvard-Oxford",
    },
    {
        "slug": "visual",
        "src": "human/outputs/visual_system/human_visual_system_3d.html",
        "accent": "#5a8fe0", "group": "input", "hotspot": "eye",
        "name": {"en": "Visual system", "zh": "視覺系統"},
        "short": {"en": "Vision", "zh": "視覺"},
        "route": {"en": "retina → optic chiasm → LGN → V1",
                  "zh": "視網膜 → 視交叉 → 外側膝狀體 → 距狀溝 V1"},
        "fact": {"en": "Partial decussation — nasal fibres cross, temporal fibres stay",
                 "zh": "視交叉只有一半纖維交叉——鼻側交叉、顳側不交叉"},
        "source": "MNI152 · Harvard-Oxford",
    },
    {
        "slug": "olfactory",
        "src": "human/outputs/olfactory_system/human_olfactory_system_3d.html",
        "accent": "#8fbf7f", "group": "input", "hotspot": "nose",
        "name": {"en": "Olfactory system", "zh": "嗅覺系統"},
        "short": {"en": "Smell", "zh": "嗅覺"},
        "route": {"en": "epithelium → bulb → piriform cortex &amp; amygdala",
                  "zh": "嗅上皮 → 嗅球 → 梨狀皮質與杏仁核"},
        "fact": {"en": "The only sense that skips the thalamus — and never crosses the midline",
                 "zh": "唯一不經視丘直達皮質的感覺,而且完全同側、不交叉"},
        "source": "MNI152 · AAL3",
    },
    {
        "slug": "limbic",
        "src": "human/outputs/limbic/human_limbic_3d.html",
        "accent": "#c9a8ff", "group": "central", "hotspot": "limbic",
        "name": {"en": "Limbic system", "zh": "邊緣系統"},
        "short": {"en": "Limbic", "zh": "邊緣"},
        "route": {"en": "hippocampus · amygdala · cingulate · hypothalamus",
                  "zh": "海馬迴 · 杏仁核 · 扣帶迴 · 下視丘"},
        "fact": {"en": "The six limbic structures resolvable at this atlas's 500µm resolution",
                 "zh": "在此圖譜 500µm 解析度下可分辨出的六個邊緣結構"},
        "source": "Allen Human Brain Atlas",
    },
    {
        "slug": "motor-hippocampus",
        "src": "human/outputs/whole_brain/human_brain_3d.html",
        "accent": "#9fb3c8", "group": "central", "hotspot": "cortex",
        "name": {"en": "Motor cortex &amp; hippocampus", "zh": "運動皮質與海馬迴"},
        "short": {"en": "Cortex", "zh": "皮質"},
        "route": {"en": "precentral gyrus + hippocampal formation, in a translucent shell",
                  "zh": "中央前回與海馬迴,置於半透明全腦殼內"},
        "fact": {"en": "Where a surface structure and a deep one actually sit relative to each other",
                 "zh": "皮質表面結構與深部結構彼此的相對位置"},
        "source": "Allen Human Brain Atlas",
    },
    {
        "slug": "pain",
        "src": "human/outputs/pain_system/human_pain_system_3d.html",
        "accent": "#e0705a", "group": "output", "hotspot": "cord",
        "name": {"en": "Pain · reflex · motor", "zh": "痛覺 · 反射 · 運動"},
        "short": {"en": "Pain", "zh": "痛覺"},
        "route": {"en": "sole → spinal cord → cortex → back down to muscle",
                  "zh": "腳底 → 脊髓 → 皮質 → 再下行到肌肉"},
        "fact": {"en": "Four midline crossings in four different places — cord for pain, medulla for touch and motor",
                 "zh": "四個中線交叉發生在四個不同位置——痛覺在脊髓,觸覺與運動在延髓"},
        "source": "MNI152 · AAL3 · PAM50",
    },
]

PLANNED = [
    {"hotspot": "hand",
     "name": {"en": "Somatosensory system", "zh": "體感覺系統"},
     "short": {"en": "Touch", "zh": "體感"},
     "note": {"en": "the DCML already runs in the pain page as a contrast branch",
              "zh": "背柱-內側蹄系已在痛覺頁作為對照分支"}},
    {"hotspot": "tongue",
     "name": {"en": "Gustatory system", "zh": "味覺系統"},
     "short": {"en": "Taste", "zh": "味覺"},
     "note": {"en": "tongue → solitary nucleus → VPM → insula",
              "zh": "舌 → 孤束核 → 腹後內側核 → 島葉"}},
    {"hotspot": None,
     "name": {"en": "Vestibular system", "zh": "前庭系統"},
     "short": {"en": "Vestibular", "zh": "前庭"},
     "note": {"en": "drawn as a branch of the auditory page; could stand alone",
              "zh": "目前是聽覺頁的一條分支,可獨立成頁"}},
    {"hotspot": "viscera",
     "name": {"en": "Autonomic system", "zh": "自律神經系統"},
     "short": {"en": "Autonomic", "zh": "自律"},
     "note": {"en": "sympathetic / parasympathetic, and the vagus",
              "zh": "交感與副交感,以及迷走神經"}},
    {"hotspot": "cerebellum",
     "name": {"en": "Cerebellum &amp; motor control", "zh": "小腦與運動控制"},
     "short": {"en": "Cerebellum", "zh": "小腦"},
     "note": {"en": "coordination, timing, and the feedback loops",
              "zh": "協調、時序,以及回饋迴路"}},
    {"hotspot": "brainstem",
     "name": {"en": "Sleep &amp; arousal", "zh": "睡眠與覺醒"},
     "short": {"en": "Brainstem", "zh": "腦幹"},
     "note": {"en": "the brainstem reticular formation",
              "zh": "腦幹網狀結構"}},
]

GROUPS = [
    ("input", {"en": "Sensory input", "zh": "感覺輸入"},
     {"en": "how the outside world gets in", "zh": "外界如何進入神經系統"}),
    ("central", {"en": "Central structures", "zh": "中樞結構"},
     {"en": "what the signal arrives at", "zh": "訊號抵達的地方"}),
    ("output", {"en": "Sensory → motor loop", "zh": "感覺 → 運動整合"},
     {"en": "the round trip, and back out to muscle", "zh": "完整的來回,一直到肌肉"}),
]


def bi(d: dict, extra: str = "") -> str:
    """A bilingual text node: JS swaps innerHTML between the two attributes."""
    return f'data-en="{d["en"]}" data-zh="{d["zh"]}"{extra}'


# --- the map ----------------------------------------------------------------
# A stylised sagittal brain (facing left) over a minimal body. NOT atlas
# geometry - the page says so out loud. viewBox is 0 0 440 660 and the figure
# stays inside x 90..320 so the label gutters never collide with it.
#
# Map labels are SHORT; the full name is on the card that lights up with the
# hotspot. Full names overflow the gutters, badly so in English.
def cerebrum_path(cx=208.0, cy=148.0, rx=104.0, ry=74.0,
                  lobes=9, depth=0.032, steps=200) -> str:
    """The cerebrum outline, generated rather than hand-drawn.

    An ellipse with a sinusoidal scallop on the dorsal rim, fading to nothing
    at the base, which is also flattened. Hand-tuned beziers kept reading as a
    featureless blob; the scallop is what makes it read as cortex.
    """
    pts = []
    for i in range(steps + 1):
        th = 2 * math.pi * i / steps
        up = max(0.0, math.sin(th))              # 1 at the vertex, 0 at the base
        r = 1 + depth * up * math.sin(lobes * th + 0.6)
        dx = rx * r * math.cos(th)
        dy = ry * r * math.sin(th)
        if dy < 0:
            dy *= 0.52                           # flatten the underside
        pts.append((cx + dx, cy - dy))
    return (f"M {pts[0][0]:.1f} {pts[0][1]:.1f} "
            + " ".join(f"L {x:.1f} {y:.1f}" for x, y in pts[1:]) + " Z")


def build_svg() -> str:
    live = {s["hotspot"]: s for s in SYSTEMS if s["hotspot"]}
    soon = {p["hotspot"]: p for p in PLANNED if p["hotspot"]}

    def hot(key: str, body: str, label_xy: tuple[float, float], anchor: str = "start") -> str:
        """One hotspot: <a> if the system exists, inert <g> if it is planned."""
        x, y = label_xy
        src = live.get(key) or soon[key]
        lab = (f'<text class="hot-label" x="{x}" y="{y}" text-anchor="{anchor}" '
               f'{bi(src["short"])}></text>')
        if key in live:
            return (f'<a class="hot" href="./{live[key]["slug"]}/" data-slug="{live[key]["slug"]}" '
                    f'style="--accent:{live[key]["accent"]}">{body}{lab}</a>')
        return f'<g class="hot hot--soon" data-soon="{key}">{body}{lab}</g>'

    return f"""
<svg id="map" viewBox="0 0 440 660" role="img" aria-labelledby="mapTitle">
  <title id="mapTitle" data-en="Nervous system navigation map" data-zh="神經系統導覽圖"></title>

  <!-- ---------- static frame: trunk, limbs, sulci ---------- -->
  <g class="frame">
    <path class="trunk" d="M 158 314 C 146 342 143 372 150 400
      C 155 421 159 434 161 444 L 251 444 C 253 434 257 421 262 400
      C 269 372 266 342 254 314 Z" />
    <path class="shoulder" d="M 160 316 C 190 306 222 306 252 316" />
    <path class="limb" d="M 158 322 L 116 388 L 100 420" />
    <path class="limb" d="M 190 444 L 180 596" />
    <path class="limb" d="M 226 444 L 240 596" />
    <path class="foot" d="M 164 600 L 194 600" />
    <path class="foot" d="M 228 600 L 258 600" />
  </g>

  <!-- ---------- hotspots ---------- -->
  {hot("cortex", f'<path class="hit-brain" d="{cerebrum_path()}" />'
                 '<ellipse class="hit-brain" cx="168" cy="182" rx="46" ry="20" '
                 'transform="rotate(-13 168 182)" />'
                 '<path class="leader" d="M 292 100 L 330 92" />', (336, 96), "start")}

  <!-- sulci sit on top of the cerebrum fill, and must not eat its hover -->
  <g class="sulci">
    <path d="M 140 126 C 168 146 190 168 196 194" />
    <path d="M 196 90 C 200 120 212 144 236 158" />
    <path d="M 256 96 C 250 126 252 150 266 166" />
  </g>

  {hot("limbic", '<ellipse class="hit-blob" cx="204" cy="162" rx="42" ry="22" />',
         (204, 167), "middle")}

  {hot("cerebellum", '<ellipse class="hit-blob" cx="290" cy="202" rx="32" ry="24" />'
        '<g class="foliate">'
        '<path d="M 266 192 C 282 188 300 192 314 200" />'
        '<path d="M 264 206 C 280 204 300 208 314 214" />'
        '</g>', (334, 198), "start")}

  {hot("brainstem", '<path class="hit-blob" d="M 217 180 C 219 216 216 252 218 298 '
        'L 234 298 C 234 252 233 216 235 178 Z" />'
        '<path class="leader" d="M 214 268 L 186 276" />', (182, 280), "end")}

  {hot("eye", '<circle class="hit-dot" cx="70" cy="162" r="13" />'
        '<circle class="pupil" cx="70" cy="162" r="4.5" />'
        '<path class="leader" d="M 83 164 L 108 170" />', (70, 136), "middle")}

  {hot("nose", '<path class="hit-dot-p" d="M 56 214 L 80 202 L 80 226 Z" />'
        '<path class="leader" d="M 82 214 L 120 198" />', (68, 246), "middle")}

  {hot("tongue", '<path class="hit-dot-p" d="M 74 266 '
        'C 90 260 110 264 114 272 C 108 280 86 282 74 276 Z" />', (94, 300), "middle")}

  {hot("ear", '<path class="hit-dot-p" d="M 250 230 '
        'C 268 224 280 236 278 252 C 276 268 262 276 250 272" />'
        '<path class="leader" d="M 252 242 L 234 214" />', (296, 260), "start")}

  {hot("hand", '<circle class="hit-dot" cx="94" cy="428" r="13" />', (94, 456), "middle")}

  {hot("viscera", '<ellipse class="hit-blob" cx="200" cy="392" rx="31" ry="24" />',
         (300, 392), "start")}

  {hot("cord", '<path class="hit-cord" d="M 216 300 L 236 300 L 232 444 L 218 444 Z" />'
        '<g class="cord-ticks">'
        '<line x1="212" y1="328" x2="240" y2="328" /><line x1="212" y1="354" x2="240" y2="354" />'
        '<line x1="212" y1="380" x2="240" y2="380" /><line x1="212" y1="406" x2="240" y2="406" />'
        '<line x1="212" y1="432" x2="240" y2="432" />'
        '</g>'
        '<circle class="hit-dot" cx="168" cy="600" r="10" />'
        '<path class="leader" d="M 172 588 L 196 460 L 216 442" />'
        '<path class="leader" d="M 244 340 L 294 340" />', (300, 344), "start")}
</svg>
"""


# --- the list ---------------------------------------------------------------
def build_list() -> str:
    out = []
    for key, title, sub in GROUPS:
        rows = []
        for s in (x for x in SYSTEMS if x["group"] == key):
            rows.append(f"""
      <a class="card" href="./{s['slug']}/" data-card="{s['slug']}" style="--accent:{s['accent']}">
        <span class="card-head">
          <span class="card-name" {bi(s['name'])}></span>
          <span class="card-status" data-en="live" data-zh="上線"></span>
        </span>
        <span class="card-route" {bi(s['route'])}></span>
        <span class="card-fact" {bi(s['fact'])}></span>
        <span class="card-source">{s['source']}</span>
      </a>""")
        out.append(f"""
    <section class="group">
      <h2 class="group-title" {bi(title)}></h2>
      <p class="group-sub" {bi(sub)}></p>
      <div class="cards">{''.join(rows)}</div>
    </section>""")

    soon_rows = "".join(
        f"""
        <li class="soon-row"{f' data-soon-row="{p["hotspot"]}"' if p["hotspot"] else ''}>
          <span class="soon-name" {bi(p['name'])}></span>
          <span class="soon-note" {bi(p['note'])}></span>
        </li>"""
        for p in PLANNED
    )
    out.append(f"""
    <section class="group group--soon">
      <h2 class="group-title" data-en="Planned" data-zh="規劃中"></h2>
      <p class="group-sub" data-en="Being added one at a time. Dimmed marks on the map are these."
         data-zh="逐一慢慢完成。導覽圖上的暗色標記就是這些。"></p>
      <ul class="soon-list">{soon_rows}</ul>
    </section>""")
    return "".join(out)


# --- the hub page -----------------------------------------------------------
HUB = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>神經系統整合 · Neuro Atlas</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#129504;</text></svg>" />
<style>
  :root {
    --bg: #12151a;
    --panel: rgba(27, 32, 40, 0.86);
    --panel-border: #2b323d;
    --text: #e9edf1;
    --text-dim: #8b96a3;
    --text-faint: #5c6672;
    --accent: #e0a458;
    --mono: ui-monospace, "Cascadia Code", "SF Mono", "JetBrains Mono", Consolas, "Liberation Mono", monospace;
    --sans: -apple-system, "Segoe UI", system-ui, Roboto, "Noto Sans TC", sans-serif;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0; min-height: 100%;
    background: var(--bg); color: var(--text); font-family: var(--sans);
    -webkit-font-smoothing: antialiased;
  }
  a { color: inherit; text-decoration: none; }

  .wrap { max-width: 1320px; margin: 0 auto; padding: 34px 30px 60px; }

  header { display: flex; flex-direction: column; gap: 6px; position: relative; }
  .eyebrow {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--text-faint);
  }
  h1 {
    margin: 0; font-family: var(--mono); font-weight: 600;
    font-size: clamp(22px, 3vw, 34px); letter-spacing: 0.01em;
  }
  h1 .accent { color: var(--accent); }
  .subtitle {
    font-size: 13px; color: var(--text-dim); max-width: 76ch; line-height: 1.6;
  }
  .subtitle b { color: var(--text); font-weight: 600; }

  .lang {
    position: absolute; right: 0; top: 0;
    background: var(--panel); border: 1px solid var(--panel-border);
    border-radius: 10px; padding: 8px 16px; cursor: pointer;
    font-family: var(--mono); font-size: 12px; color: var(--text);
    backdrop-filter: blur(10px);
  }
  .lang:hover { border-color: var(--accent); color: var(--accent); }

  main {
    display: grid; grid-template-columns: minmax(300px, 420px) 1fr;
    gap: 32px; align-items: start; margin-top: 30px;
  }

  /* ---- map ---- */
  .map-panel {
    background: var(--panel); border: 1px solid var(--panel-border);
    border-radius: 14px; padding: 18px 16px 14px; position: sticky; top: 24px;
  }
  #map { width: 100%; height: auto; display: block; }
  .map-note {
    font-size: 10.5px; color: var(--text-faint); line-height: 1.55;
    border-top: 1px solid var(--panel-border); margin-top: 10px; padding-top: 10px;
  }

  .frame path, .frame line { fill: none; stroke: #333d49; stroke-width: 1.6; }
  .frame .trunk { fill: rgba(124, 139, 153, 0.04); stroke: #29313a; stroke-width: 1.4; }
  .frame .limb, .frame .foot, .frame .shoulder { stroke-linecap: round; stroke-width: 2; }
  .sulci { pointer-events: none; }
  .sulci path { fill: none; stroke: #46515e; stroke-width: 1.2; opacity: 0.85; }

  .hot .hit-brain {
    fill: color-mix(in srgb, var(--accent) 16%, transparent);
    stroke: var(--accent); stroke-width: 1.6; stroke-linejoin: round;
    transition: fill 0.16s ease, stroke-width 0.16s ease;
  }
  .hot:hover .hit-brain, .hot.on .hit-brain, .hot:focus-visible .hit-brain {
    fill: color-mix(in srgb, var(--accent) 34%, transparent); stroke-width: 2.4;
  }

  .hot { cursor: pointer; outline: none; }
  .hot .hit-band, .hot .hit-blob, .hot .hit-dot, .hot .hit-dot-p, .hot .hit-cord {
    fill: color-mix(in srgb, var(--accent, #5c6672) 26%, transparent);
    stroke: var(--accent, #5c6672); stroke-width: 1.6;
    transition: fill 0.16s ease, stroke-width 0.16s ease;
  }
  .hot .hit-dot-p, .hot .hit-band { fill: color-mix(in srgb, var(--accent, #5c6672) 30%, transparent); }
  .hot .pupil { fill: var(--accent); stroke: none; }
  .hot .leader { fill: none; stroke: var(--accent, #5c6672); stroke-width: 1; stroke-dasharray: 3 3; opacity: 0.7; }
  .hot .cord-ticks line { stroke: var(--accent); stroke-width: 1; opacity: 0.5; }
  .hot .foliate path { fill: none; stroke: #46505c; stroke-width: 1; opacity: 0.9; }
  .hot-label {
    font-family: var(--mono); font-size: 12px; fill: var(--text-dim);
    transition: fill 0.16s ease;
  }
  .hot:hover .hit-band, .hot:hover .hit-blob, .hot:hover .hit-dot,
  .hot:hover .hit-dot-p, .hot:hover .hit-cord,
  .hot.on .hit-band, .hot.on .hit-blob, .hot.on .hit-dot,
  .hot.on .hit-dot-p, .hot.on .hit-cord,
  .hot:focus-visible .hit-band, .hot:focus-visible .hit-blob,
  .hot:focus-visible .hit-dot, .hot:focus-visible .hit-dot-p, .hot:focus-visible .hit-cord {
    fill: color-mix(in srgb, var(--accent) 62%, transparent); stroke-width: 2.4;
  }
  .hot:hover .hot-label, .hot.on .hot-label, .hot:focus-visible .hot-label {
    fill: var(--accent);
  }

  .hot--soon { cursor: default; }
  .hot--soon .hit-blob, .hot--soon .hit-dot, .hot--soon .hit-dot-p {
    fill: rgba(110, 121, 134, 0.2); stroke: #56616e;
    stroke-width: 1.3; stroke-dasharray: 4 3;
  }
  .hot--soon .hot-label { fill: var(--text-faint); font-size: 11px; }
  .hot--soon.on .hit-blob, .hot--soon.on .hit-dot, .hot--soon.on .hit-dot-p {
    fill: rgba(139, 150, 163, 0.28); stroke: #8b96a3;
  }
  .hot--soon.on .hot-label { fill: var(--text-dim); }

  /* ---- list ---- */
  .group { margin-bottom: 26px; }
  .group-title {
    margin: 0; font-family: var(--mono); font-size: 12px; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--text-faint);
  }
  .group-sub { margin: 4px 0 12px; font-size: 12px; color: var(--text-faint); }

  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 12px; }
  .card {
    display: flex; flex-direction: column; gap: 5px;
    background: var(--panel); border: 1px solid var(--panel-border);
    border-left: 3px solid var(--accent); border-radius: 10px;
    padding: 13px 15px 14px;
    transition: border-color 0.16s ease, transform 0.16s ease, background 0.16s ease;
  }
  .card:hover, .card.on {
    background: rgba(35, 41, 51, 0.92);
    border-color: color-mix(in srgb, var(--accent) 55%, var(--panel-border));
    border-left-color: var(--accent); transform: translateX(2px);
  }
  .card-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
  .card-name { font-family: var(--mono); font-size: 14px; color: var(--text); }
  .card-status {
    font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--accent); white-space: nowrap;
  }
  .card-status::before { content: "● "; }
  .card-route { font-family: var(--mono); font-size: 11px; color: var(--text-dim); line-height: 1.5; }
  .card-fact { font-size: 12px; color: var(--text-dim); line-height: 1.55; }
  .card-source {
    font-family: var(--mono); font-size: 10px; color: var(--text-faint);
    letter-spacing: 0.04em; margin-top: 2px;
  }

  .group--soon .soon-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 1px; }
  .soon-row {
    display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px;
    padding: 9px 12px; border-radius: 8px;
    border: 1px dashed transparent; transition: background 0.16s ease, border-color 0.16s ease;
  }
  .soon-row.on { background: rgba(35, 41, 51, 0.7); border-color: var(--panel-border); }
  .soon-name { font-family: var(--mono); font-size: 12.5px; color: var(--text-dim); }
  .soon-name::before { content: "○ "; color: var(--text-faint); }
  .soon-note { font-size: 11.5px; color: var(--text-faint); }

  footer {
    margin-top: 34px; padding-top: 16px; border-top: 1px solid var(--panel-border);
    font-size: 11px; color: var(--text-faint); line-height: 1.7;
  }
  footer a { color: var(--text-dim); text-decoration: underline; text-underline-offset: 2px; }
  footer a:hover { color: var(--accent); }

  @media (max-width: 900px) {
    main { grid-template-columns: 1fr; }
    .map-panel { position: static; max-width: 460px; }
    .wrap { padding: 26px 18px 48px; }
    .lang { position: static; align-self: flex-start; margin-top: 6px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <span class="eyebrow" data-en="Human · MNI152 &amp; Allen atlases · self-contained 3D viewers"
          data-zh="人體 · MNI152 與 Allen 圖譜 · 自足式 3D 檢視器"></span>
    <h1>神經系統整合 <span class="accent">Neuro Atlas</span></h1>
    <p class="subtitle"
       data-en="Every viewer here traces <b>one route through the nervous system</b> in 3D — where a signal enters, which nuclei it relays through, where it crosses the midline, and where it ends up. Solid meshes are real atlas anatomy; wireframe markers are schematic. Pick a system from the map or the list. The map is a <b>stylised diagram</b>, not atlas geometry."
       data-zh="這裡的每一頁都以 3D 追蹤<b>神經系統裡的一條路徑</b>——訊號從哪裡進入、經過哪些神經核、在哪裡越過中線、最後到哪裡。實心網格是真實的圖譜解剖;線框標記為示意。可以從導覽圖或右側清單進入各系統。導覽圖本身是<b>示意圖</b>,不是真實的圖譜幾何。"></p>
    <button class="lang" id="langToggle" type="button">EN</button>
  </header>

  <main>
    <div class="map-panel">
      __SVG__
      <p class="map-note"
         data-en="Bright marks are live systems — click to open. Dimmed dashed marks are planned."
         data-zh="亮色標記為已完成的系統,點擊即可開啟;暗色虛線標記為規劃中。"></p>
    </div>

    <div class="list">__LIST__</div>
  </main>

  <footer>
    <p data-en="Atlas sources: MNI152 template with the Harvard-Oxford and AAL3 atlases, the PAM50 spinal cord template, and the Allen Human Brain Atlas. For free educational use with citation; Harvard-Oxford is non-commercial."
       data-zh="圖譜來源:MNI152 模板與 Harvard-Oxford、AAL3 圖譜,PAM50 脊髓模板,以及 Allen Human Brain Atlas。供免費教育用途並註明出處;Harvard-Oxford 為非商業授權。"></p>
    <p data-en="Each viewer is a single self-contained HTML file with its meshes baked in — no server, no CDN. The original per-system addresses still work."
       data-zh="每個檢視器都是把網格資料內嵌好的單一 HTML 檔案,不需要伺服器,也不依賴 CDN。原本各系統的獨立網址仍然可以使用。"></p>
  </footer>
</div>

<script>
(function () {
  var LANG = "zh";
  try { LANG = localStorage.getItem("neuroLang") || "zh"; } catch (e) {}
  var SVG_NS = "http://www.w3.org/2000/svg";

  function applyLang() {
    document.querySelectorAll("[data-en]").forEach(function (el) {
      var txt = el.dataset[LANG];
      if (txt === undefined) return;
      if (el.namespaceURI === SVG_NS) el.textContent = txt;
      else el.innerHTML = txt;
    });
    document.getElementById("langToggle").textContent = LANG === "zh" ? "EN" : "中文";
    document.documentElement.lang = LANG === "zh" ? "zh-Hant" : "en";
  }

  document.getElementById("langToggle").addEventListener("click", function () {
    LANG = LANG === "zh" ? "en" : "zh";
    try { localStorage.setItem("neuroLang", LANG); } catch (e) {}
    applyLang();
  });
  applyLang();
  // Write it through even if untouched, so the viewers follow the hub's language.
  try { localStorage.setItem("neuroLang", LANG); } catch (e) {}

  // Map <-> list cross-highlighting, both directions.
  function pair(hotSel, cardSel, attr) {
    document.querySelectorAll(hotSel).forEach(function (hot) {
      var key = hot.dataset.slug || hot.dataset.soon;
      var card = document.querySelector(cardSel.replace("KEY", key));
      if (!card) return;
      function on(v) { hot.classList.toggle("on", v); card.classList.toggle("on", v); }
      hot.addEventListener("mouseenter", function () { on(true); });
      hot.addEventListener("mouseleave", function () { on(false); });
      hot.addEventListener("focus", function () { on(true); });
      hot.addEventListener("blur", function () { on(false); });
      card.addEventListener("mouseenter", function () { on(true); });
      card.addEventListener("mouseleave", function () { on(false); });
    });
  }
  pair(".hot[data-slug]", '[data-card="KEY"]', "slug");
  pair(".hot--soon[data-soon]", '[data-soon-row="KEY"]', "soon");
})();
</script>
</body>
</html>
"""

NOT_FOUND = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>404 · Neuro Atlas</title>
<style>
  html, body { margin: 0; height: 100%; background: #12151a; color: #e9edf1;
    font-family: ui-monospace, "Cascadia Code", Consolas, monospace; }
  div { height: 100%; display: flex; flex-direction: column; gap: 14px;
    align-items: center; justify-content: center; text-align: center; padding: 20px; }
  p { margin: 0; color: #8b96a3; font-size: 13px; }
  b { font-size: 15px; color: #e9edf1; letter-spacing: 0.08em; }
  a { color: #e0a458; font-size: 13px; text-decoration: none;
      border: 1px solid #2b323d; border-radius: 10px; padding: 9px 18px; }
  a:hover { border-color: #e0a458; }
</style>
</head>
<body>
<div>
  <b>404</b>
  <p>這個路徑沒有對應的系統 &middot; no system at this path</p>
  <a href="/">&larr; NEURO ATLAS</a>
</div>
</body>
</html>
"""

# --- injected into each viewer copy -----------------------------------------
NAV_SNIPPET = """
<style>
  #neuroNav {
    position: fixed; top: 14px; left: 50%; transform: translateX(-50%); z-index: 60;
    display: flex; gap: 9px; align-items: center; padding: 7px 15px; border-radius: 999px;
    background: rgba(27, 32, 40, 0.88); border: 1px solid #2b323d;
    backdrop-filter: blur(10px); text-decoration: none; white-space: nowrap;
    font: 11.5px/1 ui-monospace, "Cascadia Code", "SF Mono", Consolas, monospace;
    letter-spacing: 0.06em; color: #8b96a3;
    transition: color 0.15s ease, border-color 0.15s ease;
  }
  #neuroNav:hover { color: #e9edf1; border-color: #5c6672; }
  @media (max-width: 720px) { #neuroNav { font-size: 10.5px; padding: 6px 12px; } }
</style>
<a id="neuroNav" href="../" title="Neuro Atlas"><span>&larr;</span><span>NEURO ATLAS &middot; 神經系統首頁</span></a>
"""

# Only for the pages that have an EN/中文 button: follow the hub's choice.
LANG_SNIPPET = """
<script>
(function () {
  var want = null;
  try { want = localStorage.getItem("neuroLang"); } catch (e) {}
  if (want !== "zh") return;
  var btn = document.getElementById("langToggle");
  if (btn) btn.click();   // viewers start in English
})();
</script>
"""


def assemble() -> list[tuple[str, int, bool]]:
    # Clear the contents rather than the directory itself: on Windows a dev
    # server running inside dist/ holds a lock on the folder, and rebuilding
    # while previewing is the normal case.
    DIST.mkdir(parents=True, exist_ok=True)
    for child in DIST.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()

    report = []
    for s in SYSTEMS:
        src = REPO / s["src"]
        if not src.exists():
            sys.exit(f"ERROR: missing viewer source {src}")
        html = src.read_text(encoding="utf-8")
        if not html.rstrip().endswith("</script>"):
            sys.exit(f"ERROR: {src} does not end with </script> - injection anchor moved")
        if "neuroNav" in html:
            sys.exit(f"ERROR: {src} already contains the nav - refusing to double-inject")

        bilingual = 'id="langToggle"' in html
        # The viewers are body fragments with no <head>: the charset meta has to
        # be prepended so the file is self-describing however it gets served.
        out = '<meta charset="utf-8" />\n' + html.rstrip("\n") + "\n" + NAV_SNIPPET
        if bilingual:
            out += LANG_SNIPPET

        dest = DIST / s["slug"] / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out, encoding="utf-8")
        report.append((s["slug"], dest.stat().st_size, bilingual))

    hub = HUB.replace("__SVG__", build_svg()).replace("__LIST__", build_list())
    (DIST / "index.html").write_text(hub, encoding="utf-8")
    (DIST / "404.html").write_text(NOT_FOUND, encoding="utf-8")
    return report


def main() -> None:
    report = assemble()
    hub_kb = (DIST / "index.html").stat().st_size / 1024
    total = sum(sz for _, sz, _ in report)

    print(f"\nhub          {hub_kb:8.1f} KB  index.html")
    print(f"404          {(DIST / '404.html').stat().st_size / 1024:8.1f} KB")
    for slug, size, bilingual in report:
        print(f"  {slug:20s} {size / 1e6:6.2f} MB  nav=yes  lang-sync={'yes' if bilingual else 'n/a'}")
    print(f"\n{len(report)} viewers + hub + 404 -> {DIST}  ({total / 1e6:.1f} MB)")
    print("deploy: npx wrangler pages deploy site/dist --project-name=neuro-atlas")


if __name__ == "__main__":
    main()
