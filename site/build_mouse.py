"""Build the Mouse Atlas section of the Neuro Atlas site.

Assembles `site/dist/mouse/`:

    index.html            the mouse hub: clickable mouse-head map + list
    visual/index.html     new pathway viewers (body fragments + injected nav)
    whisker/index.html
    olfactory/index.html
    P56/..., P15/..., P14/...   verbatim copies of the legacy standalone
                          viewers, path structure preserved so their
                          existing cross-links keep working

Run AFTER build_hub.py (it writes into site/dist/). Deploy together:

    py -3.13 site/build_hub.py
    py -3.13 site/build_mouse.py
    npx wrangler pages deploy site/dist --project-name=neuro-atlas
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent
REPO = SITE_DIR.parent
MOUSE_OUT = REPO / "mouse" / "outputs"
DIST = SITE_DIR / "dist" / "mouse"

# --- new pathway pages: body fragments that get the nav injected ------------
PATHWAYS = [
    {
        "slug": "visual",
        "src": MOUSE_OUT / "P56/pathway_meshes/visual/mouse_visual_pathway_3d.html",
        "accent": "#5a8fe0", "group": "pathways", "hotspot": "eye",
        "name": {"en": "Visual system", "zh": "視覺系統"},
        "short": {"en": "Vision", "zh": "視覺"},
        "route": {"en": "retina → chiasm → LGd / SC → VISp",
                  "zh": "視網膜 → 交叉 → LGd / 上丘 → VISp"},
        "fact": {"en": "Roughly half of retinal axons go to the superior colliculus — cortex is the minority road",
                 "zh": "約一半視網膜軸突走上丘——皮質反而是少數派"},
        "source": "Allen CCFv3",
    },
    {
        "slug": "whisker",
        "src": MOUSE_OUT / "P56/pathway_meshes/whisker/mouse_whisker_pathway_3d.html",
        "accent": "#b08fd9", "group": "pathways", "hotspot": "whisker",
        "name": {"en": "Whisker somatosensory", "zh": "鬍鬚體感系統"},
        "short": {"en": "Whisker", "zh": "鬍鬚"},
        "route": {"en": "follicle → PSV → VPM → barrel field",
                  "zh": "毛囊 → 三叉主感覺核 → VPM → 桶狀皮質"},
        "fact": {"en": "One barrel = one whisker — topographic at every level",
                 "zh": "一根鬍鬚、一個桶——每一層都保持體位對應"},
        "source": "Allen CCFv3",
    },
    {
        "slug": "olfactory",
        "src": MOUSE_OUT / "P56/pathway_meshes/olfactory/mouse_olfactory_pathway_3d.html",
        "accent": "#8fbf7f", "group": "pathways", "hotspot": "nose",
        "name": {"en": "Olfactory system", "zh": "嗅覺系統"},
        "short": {"en": "Smell", "zh": "嗅覺"},
        "route": {"en": "nostril → bulb → AON → piriform",
                  "zh": "鼻孔 → 嗅球 → 前嗅核 → 梨狀皮質"},
        "fact": {"en": "About a thousand receptor genes and a bulb that is ~1/50 of the whole brain",
                 "zh": "約千個受器基因,嗅球約占全腦五十分之一"},
        "source": "Allen CCFv3",
    },
]

# --- legacy standalone viewers: copied verbatim, structure preserved -------
LEGACY = [
    {"slug": "motor", "src": "P56/motor_cortex_3d.html", "hotspot": "motor",
     "accent": "#9fb3c8", "group": "structures",
     "name": {"en": "Motor cortex (P56)", "zh": "運動皮質(P56)"},
     "short": {"en": "Motor", "zh": "運動"},
     "route": {"en": "MOp · MOs · RSP in a translucent adult brain",
               "zh": "MOp · MOs · RSP,置於半透明成鼠腦內"},
     "fact": {"en": "The original CCFv3 3D viewer — where the site's three.js build came from",
              "zh": "最早的 CCFv3 3D 檢視器——本站 three.js 架構的起點"},
     "source": "Allen CCFv3"},
    {"slug": "motor-only", "src": "P56/motor_cortex_only_3d.html", "hotspot": None,
     "accent": "#9fb3c8", "group": "hidden",   # linked from motor_cortex_3d.html
     "name": {"en": "Motor cortex only", "zh": "運動皮質(單獨)"},
     "short": {"en": "Motor", "zh": "運動"},
     "route": {"en": "cortical areas without the translucent shell",
               "zh": "不含半透明腦殼的皮質檢視"},
     "fact": {"en": "Variant of the motor page, kept for its internal links",
              "zh": "運動頁的變體,為內部連結而保留"},
     "source": "Allen CCFv3"},
    {"slug": "hippocampus", "src": "P56/hippocampus_3d.html", "hotspot": "hippocampus",
     "accent": "#7ed04b", "group": "structures",
     "name": {"en": "Hippocampus (P56)", "zh": "海馬迴(P56)"},
     "short": {"en": "Hippocampus", "zh": "海馬"},
     "route": {"en": "hippocampal formation, adult CCFv3",
               "zh": "海馬迴結構,成鼠 CCFv3"},
     "fact": {"en": "The deep structure the motor page sits next to",
              "zh": "與運動皮質頁並列的深部結構"},
     "source": "Allen CCFv3"},
    {"slug": "p56-plate", "src": "P56/coronal_section289_interactive.html", "hotspot": None,
     "accent": "#e0a458", "group": "structures",
     "name": {"en": "P56 coronal plate", "zh": "P56 冠狀切片"},
     "short": {"en": "P56 plate", "zh": "P56 切片"},
     "route": {"en": "interactive coronal section with region lookup",
               "zh": "互動式冠狀切片,可查腦區"},
     "fact": {"en": "The adult reference atlas, one slice at a time",
              "zh": "成鼠參考圖譜,一次一片"},
     "source": "Allen reference atlas"},
    {"slug": "p15-3d", "src": "P15/motor_cortex_3d_p15.html", "hotspot": None,
     "accent": "#6fb0e0", "group": "structures",
     "name": {"en": "Motor cortex at P15", "zh": "運動皮質(P15)"},
     "short": {"en": "P15 3D", "zh": "P15 3D"},
     "route": {"en": "MOp · MOs · RSP in a real P15-shaped brain",
               "zh": "MOp · MOs · RSP,真實 P15 形狀"},
     "fact": {"en": "The developing brain is not a small adult — this is its own shape",
              "zh": "發育中的腦不是縮小版成腦——它有自己的形狀"},
     "source": "DeMBA · BrainGlobe"},
    {"slug": "p15-plate", "src": "P15/coronal_p15_demba_interactive.html", "hotspot": None,
     "accent": "#6fb0e0", "group": "structures",
     "name": {"en": "P15 coronal plate", "zh": "P15 冠狀切片"},
     "short": {"en": "P15 plate", "zh": "P15 切片"},
     "route": {"en": "DeMBA P15 slice with region lookup",
               "zh": "DeMBA P15 切片,可查腦區"},
     "fact": {"en": "The developing mouse atlas, slice by slice",
              "zh": "發育小鼠圖譜,逐片檢視"},
     "source": "DeMBA · BrainGlobe"},
    {"slug": "p14-plate", "src": "P14/sagittal_p14_section144_interactive.html", "hotspot": None,
     "accent": "#e0705a", "group": "structures",
     "name": {"en": "P14 sagittal plate", "zh": "P14 矢狀切片"},
     "short": {"en": "P14 plate", "zh": "P14 切片"},
     "route": {"en": "developing-mouse sagittal section",
               "zh": "發育小鼠矢狀切面"},
     "fact": {"en": "The P14 developing atlas, sagittal view",
              "zh": "P14 發育圖譜,矢狀視角"},
     "source": "Allen developing mouse"},
]

PLANNED = [
    {"hotspot": "ear", "name": {"en": "Auditory system", "zh": "聽覺系統"},
     "short": {"en": "Hearing", "zh": "聽覺"},
     "note": {"en": "cochlea → inferior colliculus → MGB → auditory cortex",
              "zh": "耳蝸 → 下丘 → 內側膝狀體 → 聽皮質"}},
    {"hotspot": "cerebellum", "name": {"en": "Cerebellum", "zh": "小腦"},
     "short": {"en": "Cerebellum", "zh": "小腦"},
     "note": {"en": "coordination loops, mouse style", "zh": "協調迴路,小鼠版"}},
]

GROUPS = [
    ("pathways", {"en": "Pathways", "zh": "感覺路徑"},
     {"en": "one route at a time, CCFv3 adult space", "zh": "一次一條路,CCFv3 成鼠空間"}),
    ("structures", {"en": "Structures &amp; plates", "zh": "結構與切片"},
     {"en": "the classic viewers, P56 / P15 / P14", "zh": "經典檢視器,P56 / P15 / P14"}),
]


def bi(d):
    return f'data-en="{d["en"]}" data-zh="{d["zh"]}"'


def build_svg() -> str:
    live = {}
    for s in PATHWAYS + LEGACY:
        if s["hotspot"]:
            live[s["hotspot"]] = s
    soon = {p["hotspot"]: p for p in PLANNED if p["hotspot"]}

    def hot(key, body, label_xy, anchor="start"):
        x, y = label_xy
        src = live.get(key) or soon.get(key)
        if src is None:
            return ""
        lab = (f'<text class="hot-label" x="{x}" y="{y}" text-anchor="{anchor}" '
               f'{bi(src["short"])}></text>')
        if key in live:
            return (f'<a class="hot" href="./{live[key]["slug"]}/" data-slug="{live[key]["slug"]}" '
                    f'style="--accent:{live[key]["accent"]}">{body}{lab}</a>')
        return f'<g class="hot hot--soon" data-soon="{key}">{body}{lab}</g>'

    return f"""
<svg id="map" viewBox="0 0 440 660" role="img" aria-labelledby="mapTitle">
  <title id="mapTitle" data-en="Mouse atlas navigation map" data-zh="小鼠圖譜導覽圖"></title>

  <g class="frame">
    <path class="trunk" d="M 150 330 C 130 380 140 450 170 500
      C 200 545 260 545 290 500 C 315 460 320 400 305 350 Z" />
    <path class="limb" d="M 185 505 L 175 596" />
    <path class="limb" d="M 262 505 L 272 596" />
    <path class="foot" d="M 160 600 L 190 600" />
    <path class="foot" d="M 258 600 L 288 600" />
  </g>

  <!-- head + snout + ear pinna, facing left -->
  <path class="hit-head" d="M 62 306 C 90 268 130 240 170 228
    C 200 200 240 186 268 196 C 300 176 330 178 342 200
    C 356 226 348 258 326 274 C 344 300 346 336 330 362
    C 306 398 250 408 204 396 C 160 386 110 366 84 340 C 70 326 58 318 62 306 Z" />
  <circle class="pinnaline" cx="300" cy="212" r="26" />

  {hot("motor", '<ellipse class="hit-blob" cx="222" cy="238" rx="40" ry="18" transform="rotate(-14 222 238)" />'
        '<path class="leader" d="M 254 226 L 292 210" />', (298, 206), "start")}

  {hot("hippocampus", '<ellipse class="hit-blob" cx="252" cy="296" rx="30" ry="16" transform="rotate(-18 252 296)" />'
        '<path class="leader" d="M 278 306 L 316 320" />', (322, 324), "start")}

  {hot("cerebellum", '<ellipse class="hit-blob" cx="312" cy="258" rx="22" ry="15" />', (340, 262), "start")}

  {hot("ear", '<path class="hit-dot-p" d="M 288 186 C 300 176 316 180 320 192 C 322 202 312 210 300 206" />'
        '<path class="leader" d="M 306 196 L 330 168" />', (336, 164), "start")}

  {hot("eye", '<circle class="hit-dot" cx="152" cy="286" r="12" /><circle class="pupil" cx="152" cy="286" r="4.5" />'
        '<path class="leader" d="M 164 288 L 196 300" />', (140, 262), "middle")}

  {hot("nose", '<circle class="hit-dot-p" cx="66" cy="310" r="8" />'
        '<path class="leader" d="M 74 314 L 100 322" />', (52, 344), "middle")}

  {hot("whisker", '<circle class="hit-dot" cx="96" cy="336" r="9" />'
        '<path class="leader" d="M 88 340 L 66 352" />'
        '<path class="leader" d="M 90 344 L 72 366" />'
        '<path class="leader" d="M 94 346 L 84 372" />', (118, 392), "middle")}
</svg>
"""


MOUSE_HUB = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>小鼠腦圖譜 · Mouse Atlas</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#1280;</text></svg>" />
<style>
  :root {
    --bg: #12151a;
    --panel: rgba(27, 32, 40, 0.86);
    --panel-border: #2b323d;
    --text: #e9edf1;
    --text-dim: #8b96a3;
    --text-faint: #5c6672;
    --accent: #7ed04b;
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
  .topbtns { position: absolute; right: 0; top: 0; display: flex; gap: 8px; }
  .lang, .home {
    background: var(--panel); border: 1px solid var(--panel-border);
    border-radius: 10px; padding: 8px 16px; cursor: pointer;
    font-family: var(--mono); font-size: 12px; color: var(--text);
    backdrop-filter: blur(10px);
  }
  .lang:hover, .home:hover { border-color: var(--accent); color: var(--accent); }
  main {
    display: grid; grid-template-columns: minmax(300px, 420px) 1fr;
    gap: 32px; align-items: start; margin-top: 30px;
  }
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
  .frame .limb, .frame .foot { stroke-linecap: round; stroke-width: 2; }
  .hit-head { fill: rgba(124, 139, 153, 0.05); stroke: #29313a; stroke-width: 1.6; }
  .pinnaline { fill: none; stroke: #333d49; stroke-width: 1.4; }
  .hot .hit-blob, .hot .hit-dot, .hot .hit-dot-p {
    fill: color-mix(in srgb, var(--accent, #5c6672) 26%, transparent);
    stroke: var(--accent, #5c6672); stroke-width: 1.6;
    transition: fill 0.16s ease, stroke-width 0.16s ease;
  }
  .hot .hit-dot-p { fill: color-mix(in srgb, var(--accent, #5c6672) 30%, transparent); }
  .hot .pupil { fill: var(--accent); stroke: none; }
  .hot .leader { fill: none; stroke: var(--accent, #5c6672); stroke-width: 1; stroke-dasharray: 3 3; opacity: 0.7; }
  .hot-label {
    font-family: var(--mono); font-size: 12px; fill: var(--text-dim);
    transition: fill 0.16s ease;
  }
  .hot { cursor: pointer; outline: none; }
  .hot:hover .hit-blob, .hot:hover .hit-dot, .hot:hover .hit-dot-p,
  .hot.on .hit-blob, .hot.on .hit-dot, .hot.on .hit-dot-p,
  .hot:focus-visible .hit-blob, .hot:focus-visible .hit-dot, .hot:focus-visible .hit-dot-p {
    fill: color-mix(in srgb, var(--accent) 62%, transparent); stroke-width: 2.4;
  }
  .hot:hover .hot-label, .hot.on .hot-label, .hot:focus-visible .hot-label { fill: var(--accent); }
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
  @media (max-width: 900px) {
    main { grid-template-columns: 1fr; }
    .map-panel { position: static; max-width: 460px; }
    .wrap { padding: 26px 18px 48px; }
    .topbtns { position: static; align-self: flex-start; margin-top: 6px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <span class="eyebrow" data-en="Mouse &middot; Allen CCFv3 (P56) &amp; DeMBA (P15) &middot; self-contained 3D viewers"
          data-zh="小鼠 &middot; Allen CCFv3 (P56) 與 DeMBA (P15) &middot; 自足式 3D 檢視器"></span>
    <h1>小鼠腦圖譜 <span class="accent">Mouse Atlas</span></h1>
    <p class="subtitle"
       data-en="The mouse side of the Neuro Atlas: <b>pathway pages in the adult CCFv3 space</b> — whisker touch, vision, smell — plus the classic structure viewers across three ages (P56 / P15 / P14). The mouse is the workhorse of systems neuroscience, and its signature tricks (barrels, a colliculus-led visual system, a nose-led brain) are exactly what these pages teach. The map is a <b>stylised diagram</b>, not atlas geometry. The human hub lives <a href='../' style='text-decoration:underline;text-underline-offset:2px'>here</a>."
       data-zh="Neuro Atlas 的小鼠側:<b>成鼠 CCFv3 空間的路徑頁</b>——鬍鬚體感、視覺、嗅覺——加上橫跨三個年齡(P56 / P15 / P14)的經典結構檢視器。小鼠是系統神經科學的主力物種,而它的招牌絕活(桶狀皮質、以上丘為主導的視覺、由鼻子主導的腦)正是這些頁面要教的事。導覽圖為<b>示意圖</b>,不是圖譜幾何。人類首頁在<a href='../' style='text-decoration:underline;text-underline-offset:2px'>這裡</a>。"></p>
    <div class="topbtns">
      <a class="home" href="../" data-en="&larr; Human hub" data-zh="&larr; 人類首頁"></a>
      <button class="lang" id="langToggle" type="button">EN</button>
    </div>
  </header>

  <main>
    <div class="map-panel">
      __SVG__
      <p class="map-note"
         data-en="Bright marks are live pages — click to open. Dimmed dashed marks are planned."
         data-zh="亮色標記為已上線的頁面,點擊即可開啟;暗色虛線標記為規劃中。"></p>
    </div>

    <div class="list">__LIST__</div>
  </main>

  <footer>
    <p data-en="Atlas sources: Allen Mouse Brain Atlas CCFv3 (P56) structure meshes and reference plates; the DeMBA P15 atlas via BrainGlobe; the Allen Developing Mouse Brain Atlas (P14). Free educational use with citation."
       data-zh="圖譜來源:Allen Mouse Brain Atlas CCFv3 (P56) 結構網格與參考切片;經 BrainGlobe 使用的 DeMBA P15 圖譜;Allen Developing Mouse Brain Atlas (P14)。供免費教育用途並註明出處。"></p>
    <p data-en="Every viewer is a single self-contained HTML file — no server, no CDN. Legacy viewers keep their original addresses inside /mouse/."
       data-zh="每個檢視器都是單一自包含 HTML 檔案——不需要伺服器,也不依賴 CDN。舊版檢視器在 /mouse/ 底下保留原本的相對路徑。"></p>
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
  try { localStorage.setItem("neuroLang", LANG); } catch (e) {}

  function pair(hotSel, attr) {
    document.querySelectorAll(hotSel).forEach(function (hot) {
      var key = hot.dataset.slug || hot.dataset.soon;
      var card = document.querySelector('[data-card="' + key + '"], [data-soon-row="' + key + '"]');
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
  pair(".hot[data-slug]", "slug");
  pair(".hot--soon[data-soon]", "soon");
})();
</script>
</body>
</html>
"""

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
<a id="neuroNav" href="../" title="Mouse Atlas"><span>&larr;</span><span>MOUSE ATLAS &middot; 小鼠首頁</span></a>
"""

LANG_SNIPPET = """
<script>
(function () {
  var want = null;
  try { want = localStorage.getItem("neuroLang"); } catch (e) {}
  if (want !== "zh") return;
  var btn = document.getElementById("langToggle");
  if (btn) btn.click();
})();
</script>
"""


def build_list() -> str:
    out = []
    for key, title, sub in GROUPS:
        rows = []
        for s in (x for x in PATHWAYS + LEGACY if x["group"] == key):
            href = f"./{s['slug']}/" if s in PATHWAYS else f"./{s['src']}"
            rows.append(f"""
      <a class="card" href="{href}" data-card="{s['slug']}" style="--accent:{s['accent']}">
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

    if PLANNED:
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
      <p class="group-sub" data-en="Next up on the mouse side." data-zh="小鼠側的下一批。"></p>
      <ul class="soon-list">{soon_rows}</ul>
    </section>""")
    return "".join(out)


def assemble() -> None:
    DIST.mkdir(parents=True, exist_ok=True)

    # new pathway viewers: fragment + injected nav, one folder each
    for s in PATHWAYS:
        html = s["src"].read_text(encoding="utf-8")
        if not html.rstrip().endswith("</script>"):
            sys.exit(f"ERROR: {s['src']} does not end with </script>")
        if "neuroNav" in html:
            sys.exit(f"ERROR: {s['src']} already contains the nav")
        out = '<meta charset="utf-8" />\n' + html.rstrip("\n") + "\n" + NAV_SNIPPET
        if 'id="langToggle"' in html:
            out += LANG_SNIPPET
        dest = DIST / s["slug"] / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out, encoding="utf-8")
        print(f"  {s['slug']:12s} {dest.stat().st_size / 1e6:6.2f} MB")

    # legacy viewers: verbatim copies preserving the P56/P15/P14 structure
    for s in LEGACY:
        src = MOUSE_OUT / s["src"]
        dest = DIST / s["src"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        # prepend a charset meta + append the nav pill (fragments have no head)
        html = src.read_text(encoding="utf-8")
        out = '<meta charset="utf-8" />\n' + html.rstrip("\n") + "\n" + NAV_SNIPPET
        dest.write_text(out, encoding="utf-8")
        print(f"  {s['slug']:12s} {dest.stat().st_size / 1e6:6.2f} MB  (legacy copy)")

    hub = MOUSE_HUB.replace("__SVG__", build_svg()).replace("__LIST__", build_list())
    (DIST / "index.html").write_text(hub, encoding="utf-8")
    print(f"  {'hub':12s} {(DIST / 'index.html').stat().st_size / 1024:6.1f} KB")


def main() -> None:
    assemble()
    print(f"\nmouse section -> {DIST}")
    print("deploy: npx wrangler pages deploy site/dist --project-name=neuro-atlas")


if __name__ == "__main__":
    main()
