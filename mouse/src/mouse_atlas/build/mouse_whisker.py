"""
Build a self-contained 3D viewer for the MOUSE whisker somatosensory
pathway (the barrel system), right whisker pad to barrel cortex, in the
Allen CCFv3 adult (P56) atlas space.

Second of the mouse pathway pages - sibling to build/mouse_visual.py but
for the touch/pain story, duplicating the render helpers (repo
convention: mouse/ and human/ never import each other; see AGENTS.md).

COORDINATES - the Allen structure-mesh .obj files use the CCF "pir"
convention (x = posterior+, y = ventral+, z = right+). Everything is
REMAPPED at bake time to the RAS-like convention the human viewers use
(x = right+, y = anterior+, z = superior+), then centered on the root
mesh centroid, so the shared viewer_template camera/axis code works
unchanged:  x' = z, y' = -x, z' = -y  (right-handed, no mirroring).

HEADLINE FACT - ONE WHISKER, ONE BARREL. Mice sense the world mainly
through ~30 large whiskers arranged in 5 rows (A-E). Each follicle maps,
one-to-one and topographically, onto ONE barrel in layer 4 of SSp-bfd,
and the map stays point-to-point at every level: barrelettes in the
brainstem trigeminal complex, barreloids in VPM, barrels in cortex. The
fine-touch/position route relays through PSV (the principal sensory
trigeminal nucleus - the mouse's DCML analogue); pain/temperature takes
the SPVC route instead and crosses - drawn as an opt-in contrast layer.

REAL MESHES (Allen CCFv3 2017 structure meshes, in outputs/P56/mesh/):
  997 root (whole brain), 329 SSp-bfd (primary somatosensory area,
  barrel field), 733 VPM (ventral posteromedial nucleus), 7 PSV
  (principal sensory nucleus of the trigeminal), 429 SPVC (spinal
  nucleus of the trigeminal, caudal part).

SCHEMATIC (no mesh exists): the whisker follicles and the trigeminal
(Gasserian) ganglion - wireframe balls only.

ACCURACY RULES - do not "simplify" these back:
  - Barrels are LAYER 4 of SSp-bfd. Barrelettes sit in the brainstem
    trigeminal complex (SPVI/SPVO + PSV); barreloids sit in VPM. Three
    different words - don't swap them.
  - The mouse has ~30 major whiskers plus smaller ones, in 5 rows
    (A-E); active whisking runs at roughly 5-15 Hz. Say "roughly",
    never one precise number.
  - PSV receives the large-caliber afferents (touch/position);
    SPVC the small-caliber ones (pain/temperature). The SPVC route
    crosses then ascends (trigeminothalamic) - keep the copy simple,
    it mirrors the human DCML / spinothalamic split.
  - Only the right side is drawn; the left hemisphere mirror is out
    of scope, same as the sibling pages.

Data licensing: Allen CCFv3, Allen Institute - free educational use with
citation.

Usage:
    py -3.13 -m mouse_atlas.build.mouse_whisker
"""

import json

import numpy as np
import trimesh

from mouse_atlas.common.paths import OUTPUTS_DIR
from mouse_atlas.render.bake_meshes import mesh_to_region_js
from mouse_atlas.render.viewer_template import render_viewer_html

MESH_DIR = OUTPUTS_DIR / "P56" / "mesh"
OUT_DIR = OUTPUTS_DIR / "P56" / "pathway_meshes" / "whisker"
OUT_FILE = "mouse_whisker_pathway_3d.html"

ROOT_ID, BFD_ID, VPM_ID, PSV_ID, SPVC_ID = 997, 329, 733, 7, 429


def load_mesh_ras(sid):
    """Load an Allen .obj, remap pir -> RAS-like (x'=z, y'=-x, z'=-y)."""
    m = trimesh.load_mesh(MESH_DIR / f"{sid}.obj", process=False)
    v = m.vertices
    ras = np.column_stack([v[:, 2], -v[:, 0], -v[:, 1]])
    return trimesh.Trimesh(vertices=ras.astype(np.float64), faces=m.faces, process=True)


def right_anchor(tm):
    """Centroid of the right-side (x > 0) blob of a CENTERED mesh, in um."""
    sel = tm.vertices[tm.vertices[:, 0] > 0]
    return sel.mean(axis=0)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading Allen CCFv3 meshes ...")
    root = load_mesh_ras(ROOT_ID)
    center = (root.vertices.min(axis=0) + root.vertices.max(axis=0)) / 2.0
    meshes = {"root": root}
    for sid, acr in [(BFD_ID, "BFD"), (VPM_ID, "VPM"), (PSV_ID, "PSV"), (SPVC_ID, "SPVC")]:
        tm = load_mesh_ras(sid)
        tm.vertices = tm.vertices - center
        meshes[acr] = tm
    root.vertices = root.vertices - center
    cx = center[0]

    meta = {
        "root": ("CCCCCC", "Whole-brain outline (CCFv3)", "全腦輪廓(CCFv3)", True, True),
        "BFD":  ("B08FD9", "Barrel field SSp-bfd (right)", "桶狀皮質 SSp-bfd(右)", False, True),
        "VPM":  ("E0A458", "VPM thalamus (right)", "腹後內側核 VPM(右)", False, True),
        "PSV":  ("8FBF7F", "Principal sensory trigeminal PSV (right)", "三叉神經主感覺核 PSV(右)", False, True),
        "SPVC": ("E0705A", "Spinal trigeminal caudal SPVC (right)", "脊髓三叉神經核尾側部 SPVC(右)", False, False),
    }

    regions_js_parts, manifest = [], {}
    for acr, tm in meshes.items():
        color, name_en, name_zh = meta[acr][0], meta[acr][1], meta[acr][2]
        print(f"  baking {acr} ({len(tm.faces)} faces) ...")
        tm.export(OUT_DIR / f"{acr}.obj")
        manifest[acr] = {"name": name_en, "color": color,
                         "vertex_count": len(tm.vertices)}
        regions_js_parts.append(mesh_to_region_js(acr, tm, color))

    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    regions_js = "{" + ",".join(regions_js_parts) + "}"
    order = ["root", "BFD", "VPM", "PSV", "SPVC"]
    extent = float(np.ptp(root.vertices, axis=0).max())

    # ---- waypoints (remapped um, then centered like the meshes) ----
    def wp(x, y, z, r):
        return [x - cx, y - center[1], z - center[2], r]

    PSV_R = right_anchor(meshes["PSV"]).tolist() + [0]
    VPM_R = right_anchor(meshes["VPM"]).tolist() + [0]
    BFD_R = right_anchor(meshes["BFD"]).tolist() + [0]
    SPVC_R = right_anchor(meshes["SPVC"]).tolist() + [0]

    waypoints = {
        "WhiskerPad": wp(7600, -700, -5800, 350),
        "TrigG":      wp(7400, -2200, -5400, 250),
        "WhiskerP":   wp(7550, -750, -5850, 300),
        "TrigGP":     wp(7450, -2300, -5350, 220),
        "PSV_R":      PSV_R,
        "VPM_R":      VPM_R,
        "BFD_R":      BFD_R,
        "SPVC_R":     SPVC_R,
    }

    labels = {
        "WhiskerPad": {"en": "① whisker follicle (right snout)",
                       "zh": "① 鬍鬚毛囊(右吻部)"},
        "TrigG":      {"en": "② trigeminal ganglion",
                       "zh": "② 三叉神經節"},
        "PSV_R":      {"en": "③ principal sensory trigeminal nucleus (PSV)",
                       "zh": "③ 三叉神經主感覺核"},
        "VPM_R":      {"en": "④ VPM thalamus (barreloids)",
                       "zh": "④ 腹後內側核(VPM,棒狀體)"},
        "BFD_R":      {"en": "⑤ barrel field (SSp-bfd)",
                       "zh": "⑤ 桶狀皮質(SSp-bfd)"},
        "WhiskerP":   {"en": "⑥ whisker pain & temperature (contrast)",
                       "zh": "⑥ 鬍鬚痛溫傳入(對照)"},
        "TrigGP":     {"en": "⑦ trigeminal ganglion (contrast)",
                       "zh": "⑦ 三叉神經節(對照)"},
        "SPVC_R":     {"en": "⑧ spinal trigeminal nucleus, caudal (SPVC)",
                       "zh": "⑧ 脊髓三叉神經核尾側部"},
    }

    strings = {
        "eyebrow": {"en": "Mouse &middot; CCFv3 (P56) &middot; whisker&rarr;brainstem&rarr;VPM&rarr;barrel field",
                    "zh": "小鼠 &middot; CCFv3 (P56) &middot; 鬍鬚&rarr;腦幹&rarr;VPM&rarr;桶狀皮質"},
        "title_main": {"en": "Somatosensory system (mouse)", "zh": "體感覺系統(小鼠)"},
        "title_suffix": {"en": '<span class="accent">one whisker, one barrel</span> &mdash; the barrel system',
                         "zh": '<span class="accent">一根鬍鬚、一個桶</span>&mdash;&mdash;桶狀皮質系統'},
        "subtitle": {
            "en": "Mice sense the world mainly through ~30 large whiskers in 5 rows; each follicle maps to <b>ONE barrel in layer 4</b> of SSp-bfd, and the map stays topographic at every level (<b>barrelette</b> in brainstem &rarr; <b>barreloid</b> in VPM &rarr; <b>barrel</b> in cortex). Touch synapses in <b>PSV</b>; pain/temperature takes the <b>SPVC</b> route and crosses (opt-in contrast layer). Solid meshes are real CCFv3 anatomy; wireframe markers are schematic. Hover a node for a slice plane.",
            "zh": "小鼠主要靠約 30 根大鬍鬚、5 排感知世界;每個毛囊對應 SSp-bfd 第四層的<b>一個桶</b>,而且這張地圖在每一層都保持點對點(腦幹<b>小桶</b>&rarr;視丘<b>棒狀體</b>&rarr;皮質<b>桶</b>)。觸覺在 <b>PSV</b> 轉接;痛溫走 <b>SPVC</b> 路線並交叉(可勾選的對照層)。實心網格是真實 CCFv3 解剖;線框標記為示意。滑鼠移到節點可顯示切面。",
        },
        "walk_title": {"en": "Pathway walkthrough &nbsp;1&ndash;3", "zh": "路徑逐段說明 &nbsp;1&ndash;3"},
        "walk_0": {
            "en": (
                '<span class="step-tag">1 &middot; Follicle to PSV &mdash; fine touch, like the human DCML story</span>'
                "① A whisker deflects; mechanoreceptors in the follicle spike &rarr; ② their axons run back to the <b>trigeminal (Gasserian) ganglion</b> &mdash; cell bodies only, <b>no synapse</b> &rarr; ③ they relay in the <b>principal sensory trigeminal nucleus (PSV)</b>, the face's counterpart of the dorsal column nuclei."
            ),
            "zh": (
                '<span class="step-tag">1 &middot; 毛囊到 PSV&mdash;精細觸覺,如同人類的 DCML 故事</span>'
                "① 鬍鬚偏折,毛囊內的機械受器放電 &rarr; ② 軸突走回<b>三叉神經節</b>&mdash;只有細胞本體,<b>不換神經元</b> &rarr; ③ 在<b>三叉神經主感覺核(PSV)</b>轉接&mdash;它就是臉部的背柱核對應物。"
            ),
        },
        "walk_1": {
            "en": (
                '<span class="step-tag">2 &middot; VPM barreloids to barrel field &mdash; one barrel, one whisker</span>'
                "④ PSV output climbs to the <b>VPM</b>, where relay cells form <b>barreloids</b> &mdash; one per whisker &rarr; ⑤ each barreloid projects to <b>one barrel in layer 4 of SSp-bfd</b>: the famous 5&times;5 grid. During active whisking (~5&ndash;15 Hz) the mouse reads textures by this point-for-point map."
            ),
            "zh": (
                '<span class="step-tag">2 &middot; VPM 棒狀體到桶狀皮質&mdash;一桶一鬍鬚</span>'
                "④ PSV 的輸出上行到 <b>VPM</b>,中繼細胞聚成<b>棒狀體(barreloid)</b>&mdash;一根鬍鬚一個 &rarr; ⑤ 每個棒狀體投射到 <b>SSp-bfd 第四層的一個桶</b>:著名的 5&times;5 格。主動鬍鬚掃動(約 5&ndash;15 Hz)時,小鼠就靠這張點對點地圖讀取質地。"
            ),
        },
        "walk_2": {
            "en": (
                '<span class="step-tag">3 &middot; The pain contrast &mdash; SPVC route, crosses, then up</span>'
                "⑥&ndash;⑧ Pain and temperature from the same whiskers take a different road: small-caliber afferents descend to the <b>spinal trigeminal nucleus, caudal part (SPVC)</b>, whose neurons <b>cross</b> and ascend (trigeminothalamic) to the thalamus. It mirrors the human spinothalamic split from the somatosensory page. Tick the red pathway to compare."
            ),
            "zh": (
                '<span class="step-tag">3 &middot; 痛溫對照&mdash;SPVC 路線,交叉後上行</span>'
                "⑥&ndash;⑧ 同樣來自鬍鬚的痛覺與溫度走另一條路:細徑傳入纖維下行到<b>脊髓三叉神經核尾側部(SPVC)</b>,其神經元<b>交叉</b>後上行(三叉丘腦徑)抵達視丘。正好對應人體頁面的脊髓視丘路分岔。勾選紅色路徑即可比較。"
            ),
        },
        "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
        "structures_title": {"en": "Structures", "zh": "結構"},
        "pathways_title": {"en": "Pathways", "zh": "路徑"},
        "legend_note": {"en": "Dashed swatch / wireframe sphere = schematic node, not a real segmented structure.",
                        "zh": "虛線色塊／線框球體＝示意節點,並非真實分割出的解剖構造。"},
        "barrel_name": {"en": "Whisker lemniscal route (touch/position)", "zh": "鬍鬚內側蹄繫型路線(觸覺／位置)"},
        "barrel_desc": {"en": "follicle &rarr; trigeminal ganglion &rarr; PSV &rarr; VPM &rarr; barrel field",
                        "zh": "毛囊&rarr;三叉神經節&rarr;PSV&rarr;VPM&rarr;桶狀皮質"},
        "paintrig_name": {"en": "Whisker pain & temperature (contrast)", "zh": "鬍鬚痛溫路線(對照)"},
        "paintrig_desc": {"en": "follicle &rarr; trigeminal ganglion &rarr; SPVC (crosses, then ascends)",
                          "zh": "毛囊&rarr;三叉神經節&rarr;SPVC(交叉後上行)"},
        "signal_name": {"en": "Neural signal", "zh": "神經訊號"},
        "signal_desc": {"en": "animated pulse, whisker &rarr; barrel field", "zh": "動畫訊號,鬍鬚&rarr;桶狀皮質"},
        "controls_title": {"en": "Controls", "zh": "操作說明"},
        "hint_controls": {"en": "<b>drag</b> orbit &nbsp; <b>scroll</b> zoom &nbsp; <b>right-drag</b> pan &nbsp; <b>hover</b> a node for a slice plane",
                          "zh": "<b>拖曳</b>旋轉 &nbsp; <b>滾輪</b>縮放 &nbsp; <b>右鍵拖曳</b>平移 &nbsp; <b>滑鼠移到節點</b>顯示切面"},
        "hint_units": {"en": "CCFv3 space (&micro;m)", "zh": "CCFv3 空間(&micro;m)"},
        "lang_button": {"en": "中文", "zh": "EN"},
        "anterior": {"en": "Anterior", "zh": "前"},
        "posterior": {"en": "Posterior", "zh": "後"},
        "superior": {"en": "Superior", "zh": "上"},
        "right_axis": {"en": "Right", "zh": "右"},
    }

    legend_meta = [
        {"acr": a, "name_en": meta[a][1], "name_zh": meta[a][2],
         "color": meta[a][0], "outline": meta[a][3], "default_checked": meta[a][4]}
        for a in order
    ]

    html = render_viewer_html({
        "title": "體感覺系統(小鼠)",
        "accent": "b08fd9",
        "extent": extent,
        "regions_js": regions_js,
        "order": order,
        "strings": strings,
        "legend_meta": legend_meta,
        "pathways": [
            {"id": "barrel", "name_key": "barrel_name", "desc_key": "barrel_desc",
             "color": "0xb08fd9", "default_checked": True,
             "chains": [["WhiskerPad", "TrigG", "PSV_R", "VPM_R", "BFD_R"]]},
            {"id": "paintrig", "name_key": "paintrig_name", "desc_key": "paintrig_desc",
             "color": "0xe0705a", "default_checked": False,
             "chains": [["WhiskerP", "TrigGP", "SPVC_R"]]},
        ],
        "labels": labels,
        "waypoints": waypoints,
        "real": ["PSV_R", "VPM_R", "BFD_R", "SPVC_R"],
        "signal": {"pathway": "barrel", "color": "0xffd48a", "duration": 2.4},
        "walk": [
            {"key": "walk_0", "color": "#b08fd9"},
            {"key": "walk_1", "color": "#b08fd9"},
            {"key": "walk_2", "color": "#e0705a"},
        ],
    })

    out_path = OUT_DIR / OUT_FILE
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
