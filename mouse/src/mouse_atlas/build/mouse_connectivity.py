"""
Build the self-contained MOUSE BRAIN CONNECTIVITY EXPLORER page
(Allen CCFv3 adult / P56).

This is the third layer of the atlas: anatomy -> CONNECTIVITY -> stimulation.
Sibling to build/mouse_visual.py, and deliberately a SEPARATE page: the
visual pathway page tells the retina->LGd/SC->VISp story and must stay
byte-identical, while this page needs regions (LP, RSP, MOs) that story
does not contain.

WHAT THIS PAGE IS - a region-level projection graph you can click through,
plus a network diffusion model you can run. What it is NOT: a connectome
simulation. Allen connectivity data is mesoscale axonal projection density,
not synapse-level wiring, and the propagation carries no spike timing.

PHASE 3 added edge inspection (click a row/tube for raw + normalized weight,
n_experiments and note), strongest-path tracing with a deterministic pulse,
and a focus/dim mode. Tracing maximizes the product of normalized weights - a
display aid for finding the most prominent route, not a claim about signal
routing. The deployed stage-note evidence label is overridden via
window.NEURO_CONNECTIONS_LABEL so the shared site/templates/scene.js keeps its
original "schematic connections" text on the pathway pages.

COORDINATES - identical to mouse_visual.py, so the shared viewer_template
camera/axis code works unchanged: Allen "pir" .obj (x = posterior+,
y = ventral+, z = right+) is remapped to RAS-like (x = right+, y =
anterior+, z = superior+) as x' = z, y' = -x, z' = -y, then centered on
the root mesh bbox midpoint.

VOLUME OF REGIONS - Phase 2. The page draws all 17 regions in
connectivity_data.NODE_SPECS (visual, somatosensory/whisker, olfactory,
motor, association, hippocampal), each with a real CCFv3 mesh already in
outputs/P56/mesh/. The edges are real Allen Mouse Brain Connectivity Atlas
projection strengths (source="allen"), EXPERIMENTAL, replacing the Phase 1
hand-specified teaching edges.

REAL MESHES (Allen CCFv3 2017 structure meshes, in outputs/P56/mesh/):
  997 root plus the 17 NODE_SPECS ids (170 LGd, 385 VISp, 302 SCs, 218 LP,
  329 SSp-bfd, 733 VPM, 7 PSV, 429 SPVC, 507 MOB, 159 AON, 961 PIR,
  985 MOp, 993 MOs, 254 RSP, 382 CA1, 463 CA3, 726 DG).

ACCURACY RULES - do not "simplify" these back:
  - LP is 218 in the adult CCF ontology (graph_id=1). atlas_plate
    .lookup_structure("LP") returns 3793, a different ontology graph with
    no precomputed mesh. Same trap as SCs (302, not 5744).
  - The real data does contain a direct SCs -> VISp edge, but it is far
    weaker than LGd -> VISp and than the SCs -> LP -> VISp relay. Do NOT
    reintroduce the old absolute claim "SC does not project to VISp".
    The walkthrough now states the measured ordering.
  - Edge weights are EXPERIMENTAL Allen tracer means over uneven injection
    counts (n is per-edge and shown on the row tooltip). Keep the caveats
    in strings["legend_note"] and strings["walk_0"].
  - Every element is tagged with one of four evidence classes. Do not add
    an element without one.

The entire connectivity + stimulation layer ships through cfg["custom_js"]
(-> __CUSTOM__ in render/viewer_template.html), so the template shared with
the whisker / olfactory / human pages is not modified at all.

Usage:
    python -m mouse_atlas.build.mouse_connectivity
"""

import json
import os
from pathlib import Path

import numpy as np
import trimesh

from mouse_atlas.build.connectivity_data import (
    NODE_SPECS,
    SYSTEM_NAMES,
    attach_positions,
    load_connectivity,
    validate,
)
from mouse_atlas.build.running_model import RUNNING_MODEL_CONFIG
from mouse_atlas.common.paths import OUTPUTS_DIR
from mouse_atlas.render.bake_meshes import mesh_to_region_js
from mouse_atlas.render.viewer_template import render_viewer_html

MESH_DIR = OUTPUTS_DIR / "P56" / "mesh"
OUT_DIR = OUTPUTS_DIR / "P56" / "pathway_meshes" / "connectivity"
OUT_FILE = "mouse_connectivity_3d.html"

ACCENT = "84dcc5"
ROOT_ID = 997
# The region table is the single source of truth in
# connectivity_data.NODE_SPECS: acronym, structure id, name_en, name_zh,
# colour, system. Both the mesh bake and the viewer legend derive from it,
# so the 17 regions drawn can never drift from the graph the data layer
# loads. All 17 meshes already exist in outputs/P56/mesh/.
REGION_SPECS = [
    {
        "acr": acr,
        "sid": sid,
        "color": color,
        "name_en": name_en,
        "name_zh": name_zh,
        "system": system,
    }
    for acr, sid, name_en, name_zh, color, system in NODE_SPECS
]


def load_mesh_ras(sid):
    """Load an Allen .obj, remap pir -> RAS-like (x'=z, y'=-x, z'=-y)."""
    path = MESH_DIR / f"{sid}.obj"
    if not path.exists():
        raise SystemExit(
            f"missing mesh {path}\n"
            f"fetch it with:  py -3.13 -c \"from mouse_atlas.fetch.atlas_3d import "
            f"download_mesh; download_mesh({sid})\""
        )
    m = trimesh.load_mesh(path, process=False)
    v = m.vertices
    ras = np.column_stack([v[:, 2], -v[:, 0], -v[:, 1]])
    return trimesh.Trimesh(vertices=ras.astype(np.float64), faces=m.faces, process=True)


def right_anchor(tm):
    """Centroid of the right-side (x > 0) blob of a CENTERED mesh, in um."""
    sel = tm.vertices[tm.vertices[:, 0] > 0]
    return sel.mean(axis=0)


# --------------------------------------------------------------------------
# The connectivity + stimulation layer. Injected verbatim at __CUSTOM__,
# which sits INSIDE the template's main IIFE, so THREE / scene / meshes /
# EXTENT / STRINGS / LANG / applyLang are all in scope. Kept in its own
# file rather than inlined here: it is close to 1,400 lines of JS/CSS, and
# a giant Python string literal was hard to review or edit. See that
# file's own header comment for the accuracy rules and the exact strings
# it must never contain (site/viewer_upgrade.py patches the deployed
# viewer's last <script> by literal str.replace, so a collision would
# silently break the site layer) - tests/test_connectivity.py enforces
# those, plus no randomness in the propagation path and no leftover
# __TOKEN__ after substitution.
# --------------------------------------------------------------------------
_CUSTOM_JS_PATH = Path(__file__).resolve().parent.parent / "render" / "templates" / "connectivity.js"
CUSTOM_JS = _CUSTOM_JS_PATH.read_text(encoding="utf-8")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if os.environ.get("MOUSE_CONN_STRICT_DRIVE") == "1":
        assert str(OUTPUTS_DIR)[:2].upper() == "K:", (
            f"expected the K: worktree, got {OUTPUTS_DIR}. "
            "Set PYTHONPATH to the worktree's mouse/src."
        )

    print("Loading Allen CCFv3 meshes ...")
    root = load_mesh_ras(ROOT_ID)
    center = (root.vertices.min(axis=0) + root.vertices.max(axis=0)) / 2.0
    meshes = {"root": root}
    for spec in REGION_SPECS:
        tm = load_mesh_ras(spec["sid"])
        tm.vertices = tm.vertices - center
        meshes[spec["acr"]] = tm
    root.vertices = root.vertices - center

    positions = {
        spec["acr"]: right_anchor(meshes[spec["acr"]]).tolist()
        for spec in REGION_SPECS
    }

    # Phase 2: real Allen Mouse Brain Connectivity Atlas data. The 17 meshes
    # above are exactly the node set the cache carries; load_connectivity
    # raises rather than falling back to mock if the cache is missing.
    doc = attach_positions(load_connectivity("allen"), positions)
    validate(doc)
    print(f"  graph: {len(doc['nodes'])} nodes, {len(doc['edges'])} edges "
          f"({doc['provenance']['version']})")

    meta = {"root": ("CCCCCC", "Whole-brain outline (CCFv3)", "全腦輪廓(CCFv3)", True)}
    for spec in REGION_SPECS:
        meta[spec["acr"]] = (spec["color"], spec["name_en"], spec["name_zh"], True)

    order = ["root"] + [spec["acr"] for spec in REGION_SPECS]
    regions_js_parts, manifest = [], {}
    for acr in order:
        tm = meshes[acr]
        color, name_en, name_zh, _checked = meta[acr]
        print(f"  baking {acr} ({len(tm.faces)} faces) ...")
        tm.export(OUT_DIR / f"{acr}.obj")
        manifest[acr] = {"name": name_en, "color": color, "vertex_count": len(tm.vertices)}
        regions_js_parts.append(mesh_to_region_js(acr, tm, color))

    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "connectivity.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    regions_js = "{" + ",".join(regions_js_parts) + "}"
    extent = float(np.ptp(root.vertices, axis=0).max())

    strings = {
        "eyebrow": {
            "en": "Mouse &middot; CCFv3 (P56) &middot; region graph &rarr; network propagation",
            "zh": "小鼠 &middot; CCFv3 (P56) &middot; 腦區連結圖 &rarr; 網路傳播",
        },
        "title_main": {"en": "Connectivity Explorer", "zh": "連結探索器"},
        "title_suffix": {
            "en": '<span class="accent">Anatomy</span> becomes a network',
            "zh": '<span class="accent">解剖</span>成為網路',
        },
        "subtitle": {
            "en": "Pick a region to see what it projects to and what projects onto it, then press "
                  "<b>Stimulate</b> to watch activity spread through the graph. Solid meshes are real "
                  "CCFv3 anatomy, and the connection weights are real <b>Allen Mouse Brain Connectivity "
                  "Atlas</b> tracer measurements &mdash; a mesoscale measure of axonal projection, not "
                  "synapse count, connection probability or functional strength. Connection curves "
                  "indicate network relationships and do not represent reconstructed axon trajectories.",
            "zh": "選一個腦區,看它向外投射到哪裡、又接收誰的投射,然後按<b>開始刺激</b>,觀察活動在圖中擴散。"
                  "實心網格是真實 CCFv3 解剖;本頁的連結權重是真實的 <b>Allen 小鼠腦連結圖譜</b>追蹤測量值"
                  "&mdash;屬於中尺度軸突投射量,並非突觸數、連接機率或功能強度。連線曲線表示腦區間投射關係,"
                  "並非實際軸突路徑重建。",
        },
        "walk_title": {"en": "How to read this page &nbsp;1&ndash;3", "zh": "如何閱讀本頁 &nbsp;1&ndash;3"},
        "walk_0": {
            "en": '<span class="step-tag">1 &middot; What is measured, what is drawn</span>'
                  "The brain regions are <b>atlas-derived</b>: real Allen CCFv3 segmentations, and the "
                  "node positions are the centroids of those meshes. The <b>connections</b> are also "
                  "measurements now: each edge is the mean Allen tracer projection from a region's "
                  "injection experiments, and its injection count is on the row tooltip. Allen "
                  "connectivity data is <b>mesoscale axonal projection density</b> &mdash; not a "
                  "synapse-level connectome &mdash; and it carries no spike timing.",
            "zh": '<span class="step-tag">1 &middot; 哪些是量測、哪些是繪製</span>'
                  "腦區屬於<b>圖譜衍生</b>:真實的 Allen CCFv3 分割,節點位置就是這些網格的重心。"
                  "本頁的<b>連結</b>如今也是量測值:每條連線是該腦區注射實驗的平均 Allen 追蹤投射量,"
                  "注射實驗次數顯示於列的工具提示。Allen 連結資料是<b>中尺度軸突投射密度</b>"
                  "&mdash;並非突觸層級連結體,也不包含放電時間。",
        },
        "walk_1": {
            "en": '<span class="step-tag">2 &middot; Two roads, and why LP is here</span>'
                  "<b>LGd &rarr; VISp</b> is the dominant cortical road (mean projection volume). The "
                  "collicular route&rsquo;s main way to cortex is the thalamic relay <b>SCs &rarr; LP "
                  "&rarr; VISp</b>. Allen does detect a direct <b>SCs &rarr; VISp</b> projection too, "
                  "but it is far weaker. LP is the edge the visual pathway page had to leave out &mdash; "
                  "and the reason this page exists.",
            "zh": '<span class="step-tag">2 &middot; 兩條道路,以及 LP 為何在此</span>'
                  "<b>LGd &rarr; VISp</b> 是主要的皮質之路(平均投射量)。上丘路線通往皮質的主要途徑,"
                  "是經丘腦的 <b>SCs &rarr; LP &rarr; VISp</b>。Allen 資料也偵測到直接的 "
                  "<b>SCs &rarr; VISp</b> 投射,但弱得多。LP 正是視覺路徑頁必須略過的那一段,"
                  "也是本頁存在的理由。",
        },
        "walk_2": {
            "en": '<span class="step-tag">3 &middot; What Stimulate actually computes</span>'
                  "Each step every region keeps a fraction of its activity and passes the rest along its "
                  "outgoing edges, weighted by projection strength, clipped to 0&ndash;1. It is a "
                  "<b>computational network diffusion</b>, deliberately not a Hodgkin&ndash;Huxley or "
                  "integrate-and-fire neuron model. Same input always gives the same output.",
            "zh": '<span class="step-tag">3 &middot; 「開始刺激」實際在算什麼</span>'
                  "每一步,各腦區保留一部分自身活動,其餘依投射強度沿向外連線傳遞,並限制在 0&ndash;1 之間。"
                  "這是<b>計算性的網路擴散</b>,刻意不採用 Hodgkin&ndash;Huxley 或整合放電神經元模型。"
                  "相同輸入永遠得到相同輸出。",
        },
        "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
        "structures_title": {"en": "Structures", "zh": "結構"},
        "pathways_title": {"en": "Network", "zh": "網路"},
        "legend_note": {
            "en": "Edge weights are mean normalized projection volume from Allen tracer experiments "
                  "(hemisphere = both). Injection counts are uneven (from a handful to >100), so weak "
                  "edges are less stable. An absent edge means little or no bulk axonal signal in this "
                  "atlas, not proof that no connection exists. Curves show network relationships, not "
                  "reconstructed axon trajectories.",
            "zh": "連線權重為 Allen 追蹤實驗的平均正規化投射量(雙側半球)。各腦區注射次數落差很大"
                  "(從個位數到超過 100 次),因此弱連線較不穩定。圖上沒有某條連線,代表此圖譜中"
                  "該處幾乎沒有整體軸突訊號,並不證明該連結不存在。曲線表示網路關係,而非實際軸突路徑重建。",
        },
        # the template's applyLang() reads these unconditionally, because
        # #txtSignalName / #txtSignalDesc exist in the DOM even when the
        # signal row is hidden (signal=None). Omitting them throws.
        "signal_name": {"en": "Neural signal", "zh": "神經訊號"},
        "signal_desc": {"en": "not used on this page", "zh": "本頁未使用"},
        "controls_title": {"en": "Controls", "zh": "操作說明"},
        "hint_controls": {
            "en": "<b>This page:</b> pick a region &rarr; see what it connects to &rarr; press "
                  "<b>Stimulate</b> and watch activity spread &mdash; full explanation in "
                  "<b>Reading guide</b>.<br /><br />"
                  "<b>drag</b> orbit &nbsp; <b>scroll</b> zoom &nbsp; <b>right-drag</b> pan &nbsp; "
                  "<b>click</b> a region to select it",
            "zh": "<b>本頁概念:</b>選一個腦區 &rarr; 看它跟誰連結 &rarr; 按"
                  "<b>「開始刺激」</b>觀察活動如何擴散&mdash;完整說明見"
                  "<b>「閱讀指南」</b>。<br /><br />"
                  "<b>拖曳</b>旋轉 &nbsp; <b>滾輪</b>縮放 &nbsp; <b>右鍵拖曳</b>平移 &nbsp; "
                  "<b>點擊</b>腦區即可選取",
        },
        "hint_units": {"en": "CCFv3 space (&micro;m)", "zh": "CCFv3 空間(&micro;m)"},
        "lang_button": {"en": "中文", "zh": "EN"},
        "anterior": {"en": "Anterior", "zh": "前"},
        "posterior": {"en": "Posterior", "zh": "後"},
        "superior": {"en": "Superior", "zh": "上"},
        "right_axis": {"en": "Right", "zh": "右"},
    }

    legend_meta = [
        {"acr": acr, "name_en": meta[acr][1], "name_zh": meta[acr][2],
         "color": meta[acr][0], "outline": acr == "root", "default_checked": meta[acr][3]}
        for acr in order
    ]

    # The viewer needs both the graph (pure schema) and SYSTEM_NAMES for the
    # grouped picker. Keep them separate so connectivity.json stays the
    # documented graph schema; only the JS bundles them under one token.
    payload = {"graph": doc, "systems": SYSTEM_NAMES, "running": RUNNING_MODEL_CONFIG}
    custom_js = CUSTOM_JS.replace("__CONN_JSON__", json.dumps(payload, ensure_ascii=False))

    html = render_viewer_html({
        "title": "連結探索器(小鼠)",
        "accent": ACCENT,
        "extent": extent,
        "regions_js": regions_js,
        "order": order,
        "strings": strings,
        "legend_meta": legend_meta,
        "pathways": [],
        "labels": {},
        "waypoints": {},
        "real": [],
        "signal": None,
        "walk": [
            {"key": "walk_0", "color": "#84dcc5"},
            {"key": "walk_1", "color": "#5a8fe0"},
            {"key": "walk_2", "color": "#e0a458"},
        ],
        "custom_js": custom_js,
    })

    out_path = OUT_DIR / OUT_FILE
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
