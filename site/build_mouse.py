"""Build the Mouse Atlas section of the Neuro Atlas site.

Assembles `site/dist/mouse/`:

    index.html            the mouse hub: atlas projection + numbered navigation
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
import json
from pathlib import Path

from hub_design import render_hub
from navigation_map import render_navigation_map
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
    {
        "slug": "connectivity",
        "src": MOUSE_OUT / "P56/pathway_meshes/connectivity/mouse_connectivity_3d.html",
        "accent": "#84dcc5", "group": "network", "hotspot": None,
        "name": {"en": "Connectivity Explorer", "zh": "連結探索器"},
        "short": {"en": "Network", "zh": "網路"},
        "route": {"en": "17 regions → 136 measured Allen projection edges → network propagation",
                  "zh": "17 個腦區 → 136 條 Allen 實測投射連線 → 網路傳播"},
        "fact": {"en": "Real Allen tracer data across 17 regions — the SC→LP thalamic relay the visual page had to leave out",
                 "zh": "橫跨 17 腦區的真實 Allen 追蹤數據——視覺頁必須略過的 SC→LP 丘腦中繼"},
        "source": "Allen CCFv3 + Allen Mouse Brain Connectivity Atlas",
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

NEW_SYSTEMS = json.loads((MOUSE_OUT / 'P56/pathway_meshes/systems.json').read_text(encoding='utf-8'))
for system in NEW_SYSTEMS:
    system['src'] = MOUSE_OUT / system['src']
PLANNED = []

GROUPS = [
    ("pathways", {"en": "Pathways", "zh": "感覺路徑"},
     {"en": "one route at a time, CCFv3 adult space", "zh": "一次一條路,CCFv3 成鼠空間"}),
    ("structures", {"en": "Structures &amp; plates", "zh": "結構與切片"},
     {"en": "the classic viewers, P56 / P15 / P14", "zh": "經典檢視器,P56 / P15 / P14"}),
    ('output', {'en':'Brain & body', 'zh':'身體連結'},
     {'en':'selected pain and visceral regulation circuits', 'zh':'疼痛與內臟調節的代表性連結'}),
    ("network", {"en": "Network", "zh": "神經連結"},
     {"en": "click a region, watch activity propagate", "zh": "點選腦區,觀察活動如何傳播"}),
]


def build_map() -> str:
    return render_navigation_map("mouse", PATHWAYS + LEGACY + NEW_SYSTEMS, REPO)



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
    for s in PATHWAYS + NEW_SYSTEMS:
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

    hub = render_hub("mouse", PATHWAYS + LEGACY + NEW_SYSTEMS, GROUPS, PLANNED, build_map(), REPO)
    # Mouse-only adjustment; preserve the human homepage byte-for-byte.
    css = (SITE_DIR / 'templates' / 'mouse.css').read_text(encoding='utf-8')
    hub = hub.replace('</style>', css + '\n</style>', 1)
    (DIST / "index.html").write_text(hub, encoding="utf-8")
    print(f"  {'hub':12s} {(DIST / 'index.html').stat().st_size / 1024:6.1f} KB")


def main() -> None:
    assemble()
    print(f"\nmouse section -> {DIST}")
    print("deploy: npx wrangler pages deploy site/dist --project-name=neuro-atlas")


if __name__ == "__main__":
    main()
