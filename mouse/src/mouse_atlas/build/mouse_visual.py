"""
Build a self-contained 3D viewer for the MOUSE visual pathway, right eye
to cortex, in the Allen CCFv3 adult (P56) atlas space.

First of the mouse pathway pages - sibling to the human pathway pages but
in the mouse sub-project, so it duplicates the render helpers (repo
convention: mouse/ and human/ never import each other; see AGENTS.md).

COORDINATES - the Allen structure-mesh .obj files use the CCF "pir"
convention (x = posterior+, y = ventral+, z = right+). Everything is
REMAPPED at bake time to the RAS-like convention the human viewers use
(x = right+, y = anterior+, z = superior+), then centered on the root
mesh centroid, so the shared viewer_template camera/axis code works
unchanged:  x' = z, y' = -x, z' = -y  (right-handed, no mirroring).

HEADLINE FACT - MICE SEE WITH TWO PARALLEL ROADS. In primates the vast
majority of retinal ganglion cell axons go to the LGN. In the mouse the
single largest retinal target is the SUPERIOR COLLICULUS (roughly half of
all retinal axons), while the dorsal lateral geniculate (LGd) receives
only about one axon in ten. Cortical vision is the minority road; the
collicular road (prey capture, looming-triggered escape, pupil and
orienting control) is the mouse's default. Both roads are drawn, from the
same chiasm.

REAL MESHES (Allen CCFv3 2017 structure meshes, in outputs/P56/mesh/):
  997 root (whole brain), 385 VISp (primary visual area),
  170 LGd (dorsal lateral geniculate complex), 302 SCs (superior
  colliculus superficial stratum - the retinorecipient layers; this is
  the old-ontology id, the current 5744 has no precomputed mesh).

SCHEMATIC (no mesh exists): the eye, the optic nerve, the optic chiasm.

ACCURACY RULES - do not "simplify" these back:
  - Fractions vary by method and by RGC class; say "roughly half" for SC
    and "about one in ten" for LGd, never a single precise number.
  - The mouse chiasm is strongly crossed (~95%+ of fibres); both roads
    are drawn on the contralateral side. Do not add an ipsilateral
    branch.
  - SCs = superficial stratum = the retinorecipient part; the motor/deep
    layers (SCm) are downstream and are not drawn.
  - LGd projects to VISp. SC does NOT project to VISp directly; its
    cortical route runs via the lateroposterior nucleus (out of scope).

Data licensing: Allen CCFv3, Allen Institute - free educational use with
citation.

Usage:
    python -m mouse_atlas.build.mouse_visual
"""

import json

import numpy as np
import trimesh

from mouse_atlas.common.paths import OUTPUTS_DIR
from mouse_atlas.render.bake_meshes import mesh_to_region_js
from mouse_atlas.render.viewer_template import render_viewer_html

MESH_DIR = OUTPUTS_DIR / "P56" / "mesh"
OUT_DIR = OUTPUTS_DIR / "P56" / "pathway_meshes" / "visual"
OUT_FILE = "mouse_visual_pathway_3d.html"

ROOT_ID, VISP_ID, LGD_ID, SCS_ID = 997, 385, 170, 302


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
    for sid, acr in [(VISP_ID, "VISp"), (LGD_ID, "LGd"), (SCS_ID, "SCs")]:
        tm = load_mesh_ras(sid)
        tm.vertices = tm.vertices - center
        meshes[acr] = tm
    root.vertices = root.vertices - center
    cx = center[0]

    meta = {
        "root": ("CCCCCC", "Whole-brain outline (CCFv3)", "全腦輪廓(CCFv3)", True, True),
        "VISp": ("5A8FE0", "Primary visual area VISp (right)", "初級視覺區 VISp(右)", False, True),
        "LGd":  ("E0A458", "Dorsal lateral geniculate LGd (right)", "背側外側膝狀體 LGd(右)", False, True),
        "SCs":  ("5AC0C0", "Superior colliculus, superficial (right)", "上丘淺層 SCs(右)", False, True),
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
    order = ["root", "VISp", "LGd", "SCs"]
    extent = float(np.ptp(root.vertices, axis=0).max())

    # ---- waypoints (remapped um, then centered like the meshes) ----
    def wp(x, y, z, r):
        return [x - cx, y - center[1], z - center[2], r]

    SC_R = right_anchor(meshes["SCs"]).tolist() + [0]
    LGD_R = right_anchor(meshes["LGd"]).tolist() + [0]
    VISP_R = right_anchor(meshes["VISp"]).tolist() + [0]

    waypoints = {
        "Eye":    wp(9000, -2250, -4750, 400),
        "OpticN": wp(7900, -2900, -5300, 180),
        "Chiasm": wp(5700, -3500, -6200, 150),
        "LGd_R":  LGD_R,
        "SC_R":   SC_R,
        "VISp_R": VISP_R,
    }

    labels = {
        "Eye":    {"en": "① Retina (right eye)", "zh": "① 視網膜(右眼)"},
        "OpticN": {"en": "② Optic nerve", "zh": "② 視神經"},
        "Chiasm": {"en": "③ Optic chiasm — ~95% cross", "zh": "③ 視交叉—約 95% 交叉"},
        "LGd_R":  {"en": "④ LGd — the cortical road (~1 in 10 axons)", "zh": "④ 背側外側膝狀體—皮質之路(約 1/10)"},
        "VISp_R": {"en": "⑤ VISp — primary visual cortex", "zh": "⑤ 初級視覺皮質"},
        "SC_R":   {"en": "⑥ Superior colliculus — the mouse's main road (~1/2)", "zh": "⑥ 上丘—小鼠的主要道路(約 1/2)"},
    }

    strings = {
        "eyebrow": {"en": "Mouse &middot; CCFv3 (P56) &middot; retina&rarr;chiasm&rarr;LGd/SC&rarr;VISp",
                    "zh": "小鼠 &middot; CCFv3 (P56) &middot; 視網膜&rarr;視交叉&rarr;LGd/SC&rarr;VISp"},
        "title_main": {"en": "Visual system (mouse)", "zh": "視覺系統(小鼠)"},
        "title_suffix": {"en": '<span class="accent">Two roads</span> from one chiasm',
                         "zh": '<span class="accent">同一交叉</span>、兩條道路'},
        "subtitle": {
            "en": "A right retina fires. In primates almost everything goes to the LGN; in the mouse the <b>single largest retinal target is the superior colliculus</b> (roughly half the axons) and the cortical road via <b>LGd</b> carries only about <b>one axon in ten</b>. Both roads cross almost completely at the chiasm and run on the contralateral side. Solid meshes are real CCFv3 anatomy; wireframe markers are schematic. Hover a node for a slice plane.",
            "zh": "右眼視網膜放電。在靈長類幾乎全部走向視丘;在小鼠,<b>視網膜最大的下游是上丘</b>(約一半軸突),而經<b>背側外側膝狀體</b>的皮質之路只帶約<b>十分之一</b>的軸突。兩條路在視交叉幾乎完全交叉,都走對側。實心網格是真實 CCFv3 解剖;線框標記為示意。滑鼠移到節點可顯示切面。",
        },
        "walk_title": {"en": "Pathway walkthrough &nbsp;1&ndash;2", "zh": "路徑逐段說明 &nbsp;1&ndash;2"},
        "walk_0": {
            "en": (
                '<span class="step-tag">1 &middot; The shared trunk — eye, nerve, chiasm</span>'
                "① Retinal ganglion cells in the right eye spike &rarr; ② their axons form the <b>optic nerve</b> &rarr; ③ at the <b>optic chiasm</b> the overwhelming majority of mouse fibres cross to the left side. From here the road splits &mdash; and the split is the mouse's signature."
            ),
            "zh": (
                '<span class="step-tag">1 &middot; 共同幹道—眼、神經、交叉</span>'
                "① 右眼視網膜神經節細胞放電 &rarr; ② 軸突組成<b>視神經</b> &rarr; ③ 在<b>視交叉</b>,小鼠的纖維絕大多數交叉到對側。從這裡道路一分為二&mdash;而這個分岔正是小鼠的特徵。"
            ),
        },
        "walk_1": {
            "en": (
                '<span class="step-tag">2 &middot; The split — colliculus first, cortex second</span>'
                "④ <b>The cortical road.</b> About one retinal axon in ten reaches the <b>dorsal lateral geniculate (LGd)</b>, whose relay cells project to <b>VISp</b>, the primary visual cortex &mdash; the road a primate would consider the whole system.<br />"
                "⑤ <b>The collicular road (the mouse's main road).</b> Roughly HALF of all retinal axons go instead to the <b>superior colliculus (superficial layers)</b> &mdash; the structure that turns looming shadows into escape bursts, drives prey capture and orienting, and only reaches cortex indirectly (via the lateroposterior nucleus; not drawn).<br />"
                "So when you record from mouse &lsquo;vision&rsquo;, first ask: which road?"
            ),
            "zh": (
                '<span class="step-tag">2 &middot; 分岔—上丘為主,皮質為輔</span>'
                "④ <b>皮質之路。</b>約十分之一的視網膜軸突抵達<b>背側外側膝狀體(LGd)</b>,其中繼細胞再投射到<b>VISp</b>(初級視覺皮質)&mdash;靈長類會把這條路當成整個系統。<br />"
                "⑤ <b>上丘之路(小鼠的主要道路)。</b>約<b>一半</b>的視網膜軸突改走<b>上丘(淺層)</b>&mdash;把逼近的陰影轉成逃脫爆發、驅動獵捕與定向的是它;它只會間接抵達皮質(經後外側核,未繪出)。<br />"
                "所以記錄小鼠「視覺」之前,先問:走的是哪一條路?"
            ),
        },
        "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
        "structures_title": {"en": "Structures", "zh": "結構"},
        "pathways_title": {"en": "Pathways", "zh": "路徑"},
        "legend_note": {"en": "Dashed swatch / wireframe sphere = schematic node, not a real segmented structure.",
                        "zh": "虛線色塊／線框球體＝示意節點,並非真實分割出的解剖構造。"},
        "gen_name": {"en": "Retino-geniculate (cortical road)", "zh": "視網膜—膝狀體(皮質之路)"},
        "gen_desc": {"en": "retina &rarr; chiasm &rarr; LGd &rarr; VISp", "zh": "視網膜&rarr;交叉&rarr;LGd&rarr;VISp"},
        "col_name": {"en": "Retino-collicular (main road)", "zh": "視網膜—上丘(主要道路)"},
        "col_desc": {"en": "retina &rarr; chiasm &rarr; superior colliculus", "zh": "視網膜&rarr;交叉&rarr;上丘"},
        "signal_name": {"en": "Neural signal", "zh": "神經訊號"},
        "signal_desc": {"en": "animated pulse, eye &rarr; VISp", "zh": "動畫訊號,眼&rarr;VISp"},
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
        "title": "視覺系統(小鼠)",
        "accent": "5a8fe0",
        "extent": extent,
        "regions_js": regions_js,
        "order": order,
        "strings": strings,
        "legend_meta": legend_meta,
        "pathways": [
            {"id": "gen", "name_key": "gen_name", "desc_key": "gen_desc",
             "color": "0x5a8fe0", "default_checked": True,
             "chains": [["Eye", "OpticN", "Chiasm", "LGd_R", "VISp_R"]]},
            {"id": "col", "name_key": "col_name", "desc_key": "col_desc",
             "color": "0x5ac0c0", "default_checked": True,
             "chains": [["Chiasm", "SC_R"]]},
        ],
        "labels": labels,
        "waypoints": waypoints,
        "real": ["LGd_R", "SC_R", "VISp_R"],
        "signal": {"pathway": "gen", "color": "0xffd48a", "duration": 2.2},
        "walk": [
            {"key": "walk_0", "color": "#5a8fe0"},
            {"key": "walk_1", "color": "#5ac0c0"},
        ],
    })

    out_path = OUT_DIR / OUT_FILE
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
