"""
Build a self-contained 3D viewer for the MOUSE olfactory pathway, nostril
to piriform cortex, in the Allen CCFv3 adult (P56) atlas space.

Mouse pathway page #2 - sibling to build/mouse_visual.py (repo convention:
mouse/ and human/ never import each other; see AGENTS.md), duplicating the
same render helpers.

COORDINATES - the Allen structure-mesh .obj files use the CCF "pir"
convention (x = posterior+, y = ventral+, z = right+). Everything is
REMAPPED at bake time to the RAS-like convention the human viewers use
(x = right+, y = anterior+, z = superior+), then centered on the root
mesh centroid, so the shared viewer_template camera/axis code works
unchanged:  x' = z, y' = -x, z' = -y  (right-handed, no mirroring).

HEADLINE FACT - A NOSE-LED BRAIN. The mouse main olfactory bulb is
enormous for its body size: on the order of a fiftieth of the whole
brain's volume (in humans the olfactory bulb is a sliver). About a
thousand odorant-receptor genes are intact in the mouse genome (humans
keep roughly 350-400 functional ones), and smell, uniquely among the
senses, reaches its primary cortex without a thalamic relay.

REAL MESHES (Allen CCFv3 2017 structure meshes, in outputs/P56/mesh/):
   997 root (whole brain), 507 MOB (main olfactory bulb),
   159 AON (anterior olfactory nucleus), 961 PIR (piriform area).
Each is anchored on the RIGHT side (the chain runs through the right
nostril); the left homologues exist but are not drawn.

SCHEMATIC (no mesh exists): the nose/nostril entry point.

ACCURACY RULES - do not "simplify" these back:
   - Odorant-receptor gene count: say "about a thousand" intact OR genes
     in the mouse; never a single precise number. Human: ~350-400
     functional.
   - Glomeruli: ~3600 per bulb by count; say "a few thousand per bulb".
   - MOB volume is ~2% of whole-brain volume; always phrase it as "on the
     order of a fiftieth of the whole brain", not a bare percentage.
   - Piriform cortex IS the primary olfactory cortex; mitral cells reach
     it directly with NO thalamic relay (unique among sensory systems).
   - AON projects commissurally back to the contralateral bulb, letting
     the two bulbs compare nostrils - mention in one clause, no more.
   - The MOB mesh is the WHOLE bulb (all layers), not a layer split.
   - Downstream targets beyond AON/PIR (orbitofrontal cortex, amygdala,
     hypothalamus) are out of scope and not drawn.

Data licensing: Allen CCFv3, Allen Institute - free educational use with
citation.

Usage:
    python -m mouse_atlas.build.mouse_olfactory
"""

import json

import numpy as np
import trimesh

from mouse_atlas.common.paths import OUTPUTS_DIR
from mouse_atlas.render.bake_meshes import mesh_to_region_js
from mouse_atlas.render.viewer_template import render_viewer_html

MESH_DIR = OUTPUTS_DIR / "P56" / "mesh"
OUT_DIR = OUTPUTS_DIR / "P56" / "pathway_meshes" / "olfactory"
OUT_FILE = "mouse_olfactory_pathway_3d.html"

ROOT_ID, MOB_ID, AON_ID, PIR_ID = 997, 507, 159, 961


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
    for sid, acr in [(MOB_ID, "MOB"), (AON_ID, "AON"), (PIR_ID, "PIR")]:
        tm = load_mesh_ras(sid)
        tm.vertices = tm.vertices - center
        meshes[acr] = tm
    root.vertices = root.vertices - center
    cx = center[0]

    meta = {
        "root": ("CCCCCC", "Whole-brain outline (CCFv3)", "全腦輪廓(CCFv3)", True, True),
        "MOB": ("8fbf7f", "Main olfactory bulb (right)", "主嗅球(右)", False, True),
        "AON": ("a0c890", "Anterior olfactory nucleus (right)", "前嗅核(右)", False, True),
        "PIR": ("6fa87f", "Piriform cortex (right)", "梨狀皮質(右)", False, True),
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
    order = ["root", "MOB", "AON", "PIR"]
    extent = float(np.ptp(root.vertices, axis=0).max())

    # ---- waypoints (remapped um, then centered like the meshes) ----
    def wp(x, y, z, r):
        return [x - cx, y - center[1], z - center[2], r]

    MOB_R = right_anchor(meshes["MOB"]).tolist() + [0]
    AON_R = right_anchor(meshes["AON"]).tolist() + [0]
    PIR_R = right_anchor(meshes["PIR"]).tolist() + [0]

    waypoints = {
        "Nose":  wp(6200, -300, -5900, 300),
        "MOB_R": MOB_R,
        "AON_R": AON_R,
        "PIR_R": PIR_R,
    }

    labels = {
        "Nose":  {"en": "① Odorant molecules (right nostril)", "zh": "① 氣味分子(右鼻孔)"},
        "MOB_R": {"en": "② Main olfactory bulb (mitral cells)", "zh": "② 主嗅球(mitral 細胞)"},
        "AON_R": {"en": "③ Anterior olfactory nucleus", "zh": "③ 前嗅核"},
        "PIR_R": {"en": "④ Piriform cortex", "zh": "④ 梨狀皮質"},
    }

    strings = {
        "eyebrow": {"en": "Mouse &middot; CCFv3 (P56) &middot; nostril&rarr;bulb&rarr;piriform",
                    "zh": "小鼠 &middot; CCFv3 (P56) &middot; 鼻孔&rarr;嗅球&rarr;梨狀皮質"},
        "title_main": {"en": "Olfactory system (mouse)", "zh": "嗅覺系統(小鼠)"},
        "title_suffix": {"en": '<span class="accent">a nose-led brain</span>',
                         "zh": '<span class="accent">由鼻子主導</span>的腦'},
        "subtitle": {
            "en": (
                "An odorant molecule lands in the right nostril. Relative to body size the "
                "<b>mouse main olfactory bulb is enormous</b> &mdash; on the order of a "
                "<b>fiftieth of the whole brain</b>&rsquo;s volume (in humans the olfactory "
                "bulb is a sliver). About <b>a thousand odorant-receptor genes</b> are intact "
                "in the mouse genome (humans keep roughly 350&ndash;400 functional ones), and "
                "each <b>glomerulus</b> collects axons from receptors of just <b>one type</b> "
                "&mdash; a few thousand glomeruli per bulb. <b>Mitral cells</b> project to the "
                "<b>anterior olfactory nucleus</b> and <b>piriform cortex</b> without any "
                "thalamic relay, and AON is the hub that lets the two bulbs compare nostrils. "
                "Solid meshes are real CCFv3 anatomy; wireframe markers are schematic. "
                "Hover a node for a slice plane."
            ),
            "zh": (
                "氣味分子落入右鼻孔。相對於體型,<b>小鼠的主嗅球大得驚人</b>&mdash;約佔"
                "<b>全腦體積的五十分之一</b>(人類的嗅球只是一小條)。小鼠基因體中約有"
                "<b>一千個完整的嗅覺受器基因</b>(人類僅存約 350&ndash;400 個具功能),而每個"
                "<b>嗅小球</b>只收集<b>單一類型</b>受器的軸突&mdash;每側嗅球約有數千個嗅小球。"
                "<b>僧帽細胞</b>投射到<b>前嗅核</b>與<b>梨狀皮質</b>,不經視丘中繼;前嗅核正是"
                "讓兩側嗅球互相比較鼻孔訊息的樞紐。實心網格是真實 CCFv3 解剖;線框標記為示意。"
                "滑鼠移到節點可顯示切面。"
            ),
        },
        "walk_title": {"en": "Pathway walkthrough &nbsp;1&ndash;3", "zh": "路徑逐段說明 &nbsp;1&ndash;3"},
        "walk_0": {
            "en": (
                '<span class="step-tag">1 &middot; Inside the bulb &mdash; wiring the smell map</span>'
                "① Odorant molecules dissolve in the nasal mucus &rarr; ② they activate a subset "
                "of the <b>~thousand receptor types</b>; all axons from <b>ONE receptor type</b> "
                "converge onto one or a few <b>glomeruli</b> (ball-shaped synapse clusters) in the "
                "bulb &rarr; ③ <b>mitral cells</b> read which glomeruli fired and carry the pattern "
                "deeper. The bulb turns chemistry into a spatial map."
            ),
            "zh": (
                '<span class="step-tag">1 &middot; 嗅球內部&mdash;把化學接成地圖</span>'
                "① 氣味分子溶入鼻腔黏液 &rarr; ② 它們活化約<b>一千種受器</b>中的一小部分;"
                "<b>同一種受器</b>的所有軸突會聚到嗅球裡一至數個<b>嗅小球</b>(球狀突觸團)"
                "&rarr; ③ <b>僧帽細胞</b>讀出哪些嗅小球被點亮,把這個型式帶往更深處。"
                "嗅球就這樣把「化學」變成「空間地圖」。"
            ),
        },
        "walk_1": {
            "en": (
                '<span class="step-tag">2 &middot; Out of the bulb &mdash; cortex without thalamus</span>'
                "④ <b>Piriform cortex</b> is the primary olfactory cortex: mitral-cell axons reach "
                "it <b>directly, with no thalamic relay</b> &mdash; unique among the senses.<br />"
                "⑤ The <b>anterior olfactory nucleus</b> sits between bulb and piriform and, via "
                "its commissural branch back to the opposite bulb, lets the two bulbs compare "
                "nostrils.<br />"
                "From there, output spreads wide &mdash; orbitofrontal cortex, amygdala, "
                "hypothalamus (not drawn)."
            ),
            "zh": (
                '<span class="step-tag">2 &middot; 出嗅球&mdash;不經視丘的皮質</span>'
                "④ <b>梨狀皮質</b>就是初級嗅覺皮質:僧帽細胞的軸突<b>直接抵達、不經視丘中繼</b>"
                "&mdash;這在感覺系統中獨一無二。<br />"
                "⑤ <b>前嗅核</b>位於嗅球與梨狀皮質之間,並經連合分支回傳到對側嗅球,"
                "讓兩側嗅球得以比較左右鼻孔。<br />"
                "再往後,輸出廣泛分布&mdash;眶額皮質、杏仁核、下視丘(未繪出)。"
            ),
        },
        "walk_2": {
            "en": (
                '<span class="step-tag">3 &middot; Why mouse smell is a superpower</span>'
                "Three numbers make the point: about <b>a thousand intact odorant-receptor "
                "genes</b> (humans keep only ~350&ndash;400 functional ones); a main olfactory "
                "bulb that is <b>on the order of a fiftieth of the entire brain</b> (in humans a "
                "sliver); and a body built to use them &mdash; mice constantly <b>sniff</b>, "
                "sampling the air several times a second. Smell is not a sense the mouse borrows; "
                "it is the sense the mouse leads with."
            ),
            "zh": (
                '<span class="step-tag">3 &middot; 為什麼嗅覺是小鼠的超能力</span>'
                "三個數字說明一切:約<b>一千個完整的嗅覺受器基因</b>(人類僅剩約 350&ndash;400 個"
                "具功能);主嗅球<b>約佔全腦的五十分之一</b>(人類只是一小條);還有為此打造的"
                "身體&mdash;小鼠除了睡覺幾乎一直在<b>吸嗅</b>,每秒採樣空氣數次。"
                "嗅覺對小鼠不是附屬感官,而是主導一切的感官。"
            ),
        },
        "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
        "structures_title": {"en": "Structures", "zh": "結構"},
        "pathways_title": {"en": "Pathways", "zh": "路徑"},
        "legend_note": {"en": "Dashed swatch / wireframe sphere = schematic node, not a real segmented structure.",
                        "zh": "虛線色塊／線框球體＝示意節點,並非真實分割出的解剖構造。"},
        "olf_name": {"en": "Main olfactory (nose-led)", "zh": "主嗅覺(由鼻主導)"},
        "olf_desc": {"en": "nostril &rarr; MOB &rarr; AON &rarr; piriform cortex",
                     "zh": "鼻孔&rarr;主嗅球&rarr;前嗅核&rarr;梨狀皮質"},
        "signal_name": {"en": "Neural signal", "zh": "神經訊號"},
        "signal_desc": {"en": "animated pulse, nostril &rarr; piriform", "zh": "動畫訊號,鼻孔&rarr;梨狀皮質"},
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
        "title": "嗅覺系統(小鼠)",
        "accent": "8fbf7f",
        "extent": extent,
        "regions_js": regions_js,
        "order": order,
        "strings": strings,
        "legend_meta": legend_meta,
        "pathways": [
            {"id": "olf", "name_key": "olf_name", "desc_key": "olf_desc",
             "color": "0x8fbf7f", "default_checked": True,
             "chains": [["Nose", "MOB_R", "AON_R", "PIR_R"]]},
        ],
        "labels": labels,
        "waypoints": waypoints,
        "real": ["MOB_R", "AON_R", "PIR_R"],
        "signal": {"pathway": "olf", "color": "0xffd48a", "duration": 2.6},
        "walk": [
            {"key": "walk_0", "color": "#8fbf7f"},
            {"key": "walk_1", "color": "#a0c890"},
            {"key": "walk_2", "color": "#6fa87f"},
        ],
    })

    out_path = OUT_DIR / OUT_FILE
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
