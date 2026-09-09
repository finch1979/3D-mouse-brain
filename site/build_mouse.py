"""Build the Mouse Atlas section of the Neuro Atlas site.

Assembles `site/dist/mouse/`:

    index.html            the mouse hub: clickable mouse-head map + list
    visual/index.html     new pathway viewers (body fragments + injected nav)
    whisker/index.html
    olfactory/index.html
    P56/..., P15/..., P14/...   decorated copies of the legacy standalone
                          viewers, path structure preserved so their
                          existing cross-links keep working

Run AFTER build_hub.py (it writes into site/dist/). Deploy together:

    py -3.13 site/build_hub.py
    py -3.13 site/build_mouse.py
    npx wrangler pages deploy site/dist --project-name=neuro-atlas
"""

from __future__ import annotations

import sys
from pathlib import Path

from hub_design import render_hub
from viewer_upgrade import prepare_viewer, viewer_upgrade

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
            entry = live[key]
            href = f'./{entry["slug"]}/' if entry in PATHWAYS else f'./{entry["src"]}'
            return (f'<a class="hot" href="{href}" data-slug="{entry["slug"]}" '
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


def assemble() -> None:
    DIST.mkdir(parents=True, exist_ok=True)

    # new pathway viewers: fragment + injected nav, one folder each
    for s in PATHWAYS:
        html = s["src"].read_text(encoding="utf-8")
        if not html.rstrip().endswith("</script>"):
            sys.exit(f"ERROR: {s['src']} does not end with </script>")
        if "neuroNav" in html:
            sys.exit(f"ERROR: {s['src']} already contains the nav")
        html = prepare_viewer(html)
        out = ('<meta charset="utf-8" />\n'
               '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
               + html.rstrip("\n") + "\n" + NAV_SNIPPET)
        if 'id="langToggle"' in html:
            out += LANG_SNIPPET
        out += viewer_upgrade()
        dest = DIST / s["slug"] / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out, encoding="utf-8")
        print(f"  {s['slug']:12s} {dest.stat().st_size / 1e6:6.2f} MB")

    # legacy viewers: decorated copies preserving the P56/P15/P14 structure
    for s in LEGACY:
        src = MOUSE_OUT / s["src"]
        dest = DIST / s["src"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Metadata, navigation and layout are added only to the copied fragment.
        html = src.read_text(encoding="utf-8")
        if s["slug"] == "hippocampus":
            html = html.replace('href="/coronal"', 'href="./coronal_section289_interactive.html"')
        html = prepare_viewer(html)
        out = ('<meta charset="utf-8" />\n'
               '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
               + html.rstrip("\n") + "\n" + NAV_SNIPPET)
        if 'id="langToggle"' in html:
            out += LANG_SNIPPET
        out += viewer_upgrade()
        dest.write_text(out, encoding="utf-8")
        print(f"  {s['slug']:12s} {dest.stat().st_size / 1e6:6.2f} MB  (legacy copy)")

    hub = render_hub("mouse", PATHWAYS + LEGACY, GROUPS, PLANNED, build_svg(), REPO)
    (DIST / "index.html").write_text(hub, encoding="utf-8")
    print(f"  {'hub':12s} {(DIST / 'index.html').stat().st_size / 1024:6.1f} KB")


def main() -> None:
    assemble()
    print(f"\nmouse section -> {DIST}")
    print("deploy: npx wrangler pages deploy site/dist --project-name=neuro-atlas")


if __name__ == "__main__":
    main()
