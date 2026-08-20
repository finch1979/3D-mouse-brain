"""
Build a self-contained 3D viewer for the human visual pathway (retina to
cortex), plus its reflex branch to the superior colliculus / oculomotor
nuclei. Sibling to human_auditory.py -- same architecture, same rigor about
what's real anatomy vs. schematic, applied to vision instead of hearing.

Combines a REAL MNI152-space structure mesh (primary visual cortex) with
SCHEMATIC waypoints for everything else - retina, optic nerve, optic
chiasm, optic tract, lateral geniculate nucleus, superior colliculus, and
the oculomotor/trochlear/abducens nuclear complex have no freely
downloadable segmentation at any usable resolution. Schematic waypoint
coordinates below are approximate, illustrative placements (right eye),
not derived from a specific voxel atlas.

Real data source (already in MNI152 space - the FSL/nilearn default):
  - Whole-brain outline: nilearn's bundled MNI152 brain mask (same as
    human_auditory.py).
  - Primary visual cortex (V1): Harvard-Oxford cortical atlas, label
    "Intracalcarine Cortex" (index 24 in cort-maxprob-thr25-1mm as of this
    build) - the cortex lining the calcarine sulcus, i.e. striate cortex /
    V1. Reuses the SAME atlas + cache dir human_auditory.py already
    downloads for Heschl's Gyrus, so no redundant fetch.

All real meshes are scaled from mm to micrometers (x1000), matching the
rest of this project's human-mesh convention.

IMPORTANT laterality note - the visual pathway PARTIALLY decussates at the
optic chiasm, unlike audition's single full crossing:
  - Temporal (lateral) retina fibers stay UNCROSSED (ipsilateral) -> same-
    side optic tract -> same-side LGN -> same-side V1.
  - Nasal (medial) retina fibers CROSS at the chiasm (contralateral) ->
    opposite-side optic tract -> opposite-side LGN -> opposite-side V1.
  - Net clinical fact: each hemisphere's visual cortex represents the
    OPPOSITE half of the visual field (the lens inverts the image, so
    "temporal retina" sees the nasal/medial visual field and vice versa).
    Get this backwards and the diagram teaches the wrong thing - don't
    "helpfully" straighten the two branches onto the same side.
  - Only one eye (right) is modeled, matching human_auditory.py's "right
    ear" convention - its retina is a single origin node that splits into
    the two fiber populations at the chiasm waypoint.

Usage:
    python -m human_atlas.build.human_visual
"""

import json

import nibabel as nib
import numpy as np
import trimesh
from nilearn import datasets
from scipy.ndimage import binary_dilation, zoom
from skimage import measure
from trimesh import smoothing

from human_atlas.common.paths import DATA_CACHE_DIR, OUTPUTS_DIR, WEB_LIB_DIR
from human_atlas.render.bake_meshes import mesh_to_region_js

MM_TO_UM = 1000.0
# Reuse human_auditory.py's Harvard-Oxford cache dir - identical dataset,
# no need to download it twice.
HO_CACHE_DIR = DATA_CACHE_DIR / "human_auditory"
OUT_DIR = OUTPUTS_DIR / "visual_system"
MESH_DIR = OUT_DIR / "mesh"
OUT_FILE = "human_visual_system_3d.html"

ROOT_DOWNSAMPLE = 0.35  # whole-brain mask is ~2M voxels; downsample before marching cubes
SKULL_MARGIN_MM = 9  # dilation margin (mm, ~1mm/voxel) for the approx. head-size context shell

# Approximate, illustrative MNI coordinates (mm, RAS) + an approximate
# marker radius (mm) for structures with no practical open mesh source.
# Schematic only - see laterality note above for the crossed/uncrossed rule.
VISUAL_SCHEMATIC = {
    "Retina": {"pos": (30, 55, -22), "r": 4},
    "OpticNerve": {"pos": (20, 32, -22), "r": 1.5},
    "Chiasm": {"pos": (0, 4, -14), "r": 2.5},
    "TractR": {"pos": (14, -6, -10), "r": 1.5},
    "TractL": {"pos": (-14, -6, -10), "r": 1.5},
    "LGN_R": {"pos": (24, -24, -2), "r": 2.5},
    "LGN_L": {"pos": (-24, -24, -2), "r": 2.5},
    "SC": {"pos": (4, -30, -6), "r": 2.5},
    "CNIII": {"pos": (0, -22, -14), "r": 2},
}
VISUAL_TRUNK = ["Retina", "OpticNerve", "Chiasm"]
# Group 1: the conscious-vision (geniculostriate) system - two branches that
# share the trunk above then diverge at the chiasm, one staying ipsilateral,
# one crossing. Both terminate on a REAL mesh (V1_R / V1_L, appended in main()).
VISUAL_UNCROSSED_ORDER = VISUAL_TRUNK + ["TractR", "LGN_R", "V1_R"]
VISUAL_CROSSED_ORDER = VISUAL_TRUNK + ["TractL", "LGN_L", "V1_L"]
# Group 2: the reflex (tectal) branch - pupillary light reflex / eye-movement
# reflex circuit, entirely schematic. Arbitrarily continues via the same
# uncrossed tract waypoint (both tracts genuinely contribute in reality).
REFLEX_ORDER = VISUAL_TRUNK + ["TractR", "SC", "CNIII"]

VISUAL_LABELS = {
    "Retina": {"en": "① Retina (right eye)", "zh": "①視網膜(右眼)"},
    "OpticNerve": {"en": "② Optic nerve (CN II, right)", "zh": "②視神經(第二對腦神經,右)"},
    "Chiasm": {"en": "③ Optic chiasm — partial decussation", "zh": "③視交叉—部分交叉"},
    "TractR": {"en": "④a Uncrossed fibers (temporal retina) → right optic tract", "zh": "④a非交叉纖維(顳側視網膜)→右視束"},
    "TractL": {"en": "④b Crossed fibers (nasal retina) → left optic tract", "zh": "④b交叉纖維(鼻側視網膜)→左視束"},
    "SC": {"en": "④c Superior colliculus — reflex branch", "zh": "④c上丘—反射分支"},
    "LGN_R": {"en": "⑤a Right lateral geniculate nucleus", "zh": "⑤a右外側膝狀體"},
    "LGN_L": {"en": "⑤b Left lateral geniculate nucleus", "zh": "⑤b左外側膝狀體"},
    "CNIII": {"en": "⑤c Oculomotor nuclei (III/IV/VI, bilateral)", "zh": "⑤c動眼神經核群(第三、四、六對腦神經,雙側)"},
    "V1_R": {"en": "⑥a Right primary visual cortex (V1)", "zh": "⑥a右初級視覺皮質"},
    "V1_L": {"en": "⑥b Left primary visual cortex (V1)", "zh": "⑥b左初級視覺皮質"},
}

# All static UI copy, en/zh. Node-label sprites (VISUAL_LABELS above) are
# translated separately since they're baked into canvas textures, not DOM text.
STRINGS = {
    "eyebrow": {"en": "Human &middot; MNI152 space &middot; peripheral&rarr;central pathway",
                "zh": "人腦 &middot; MNI152 空間 &middot; 周邊&rarr;中樞路徑"},
    "title_suffix": {"en": '<span class="accent">Visual</span> &amp; <span style="color:var(--accent2)">Reflex</span> Pathways',
                      "zh": '<span class="accent">視覺</span>與<span style="color:var(--accent2)">反射</span>路徑'},
    "subtitle": {
        "en": "The visual pathway from right eye to cortex, showing the optic chiasm's <b>partial decussation</b> &mdash; temporal (lateral) retina fibers stay <b>uncrossed</b> (ipsilateral), nasal (medial) retina fibers <b>cross</b> at the chiasm (contralateral); net result, each hemisphere's visual cortex represents the <b>opposite</b> half of the visual field. A reflex branch continues from the chiasm to the superior colliculus and oculomotor nuclei (pupillary / eye-movement reflexes). Solid meshes are real MNI152-space anatomy; wireframe markers are schematic, illustrative placements for structures too small or too deep for any freely available 3D atlas. Hover a node for a locator line + slice plane.",
        "zh": "從右眼到皮質的視覺路徑,呈現視交叉的<b>部分交叉</b>特性&mdash;顳側(外側)視網膜纖維維持<b>不交叉</b>(同側),鼻側(內側)視網膜纖維在視交叉<b>交叉</b>(對側);結果是每側大腦的視覺皮質代表的是<b>對側</b>視野。另有一條反射分支從視交叉延伸到上丘與動眼神經核群(瞳孔反射／眼球運動反射)。實心網格是真實的 MNI152 空間解剖構造;線框標記是示意性的,代表目前沒有任何免費 3D 圖譜可用的過小或過深結構的概略位置。將滑鼠移到節點上可顯示指示線與切面。",
    },
    "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
    "structures_title": {"en": "Structures", "zh": "結構"},
    "legend_note": {"en": "Dashed swatch / wireframe sphere = schematic node, not a real segmented structure. Click &quot;Structures&quot; to collapse this panel.",
                     "zh": "虛線色塊／線框球體＝示意節點,並非真實分割出的解剖構造。點擊「結構」可收合此面板。"},
    "visual_pathway_name": {"en": "Visual pathway", "zh": "視覺路徑"},
    "visual_pathway_desc": {"en": "retina &rarr; chiasm &rarr; LGN &rarr; ... &rarr; V1 (crossed + uncrossed)", "zh": "視網膜&rarr;視交叉&rarr;外側膝狀體&rarr;……&rarr;初級視覺皮質(交叉+不交叉)"},
    "reflex_pathway_name": {"en": "Reflex pathway", "zh": "反射路徑"},
    "reflex_pathway_desc": {"en": "chiasm &rarr; superior colliculus &rarr; oculomotor nuclei", "zh": "視交叉&rarr;上丘&rarr;動眼神經核群"},
    "signal_name": {"en": "Neural signal", "zh": "神經訊號"},
    "signal_desc": {"en": "animated light pulse, retina &rarr; visual cortex", "zh": "動畫光訊號,視網膜&rarr;視覺皮質"},
    "controls_title": {"en": "Controls", "zh": "操作說明"},
    "hint_controls": {"en": "<b>drag</b> orbit &nbsp; <b>scroll</b> zoom &nbsp; <b>right-drag</b> pan &nbsp; <b>hover</b> a node for a slice plane",
                       "zh": "<b>拖曳</b>旋轉 &nbsp; <b>滾輪</b>縮放 &nbsp; <b>右鍵拖曳</b>平移 &nbsp; <b>滑鼠移到節點</b>顯示切面"},
    "hint_units": {"en": "MNI152 space (mm, &times;1000 &rarr; &micro;m)", "zh": "MNI152 空間(mm,&times;1000 &rarr; &micro;m)"},
    "lang_button": {"en": "中文", "zh": "EN"},
    "anterior": {"en": "Anterior", "zh": "前"},
    "posterior": {"en": "Posterior", "zh": "後"},
    "superior": {"en": "Superior", "zh": "上"},
    "right_axis": {"en": "Right", "zh": "右"},
}


def mask_to_mesh(mask, affine, downsample=1.0, smooth_iterations=15):
    vol = mask.astype(np.float32)
    if downsample < 1.0:
        vol = zoom(vol, downsample, order=1)
    verts_ijk, faces, _normals, _values = measure.marching_cubes(vol, level=0.5)
    verts_ijk = verts_ijk / downsample
    verts_mm = nib.affines.apply_affine(affine, verts_ijk)
    verts_um = (verts_mm * MM_TO_UM).astype(np.float32)
    tm = trimesh.Trimesh(vertices=verts_um, faces=faces, process=True)
    smoothing.filter_taubin(tm, lamb=0.5, nu=-0.53, iterations=smooth_iterations)
    return tm


def main():
    MESH_DIR.mkdir(parents=True, exist_ok=True)
    HO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading MNI152 brain mask + Harvard-Oxford cortical atlas ...")
    mni_img = datasets.load_mni152_brain_mask()
    ho = datasets.fetch_atlas_harvard_oxford("cort-maxprob-thr25-1mm", data_dir=str(HO_CACHE_DIR))
    ho_img = nib.load(ho.maps) if isinstance(ho.maps, str) else ho.maps
    ho_data = ho_img.get_fdata()
    v1_idx = [i for i, name in enumerate(ho.labels) if "Intracalcarine" in name]
    if not v1_idx:
        raise RuntimeError(f"Intracalcarine Cortex label not found in {ho.labels}")
    v1_mask = np.isin(ho_data, v1_idx)

    print("Building an approximate head-size context shell (dilated brain mask) ...")
    mni_mask_bool = mni_img.get_fdata().astype(bool)
    skull_mask = binary_dilation(mni_mask_bool, iterations=SKULL_MARGIN_MM)

    structures = {
        "root": {
            "mask": mni_mask_bool, "affine": mni_img.affine,
            "downsample": ROOT_DOWNSAMPLE, "smooth": 5,
            "color": "CCCCCC", "name": "Whole-brain outline (MNI152)",
        },
        "skull": {
            "mask": skull_mask, "affine": mni_img.affine,
            "downsample": ROOT_DOWNSAMPLE, "smooth": 5,
            "color": "FFFFFF", "name": f"Approx. head size (brain +{SKULL_MARGIN_MM}mm, not real skull anatomy)",
        },
        "V1": {
            "mask": v1_mask, "affine": ho_img.affine,
            "downsample": 1.0, "smooth": 15,
            "color": "5A8FE0", "name": "Primary visual cortex (calcarine / Intracalcarine cortex)",
        },
    }

    regions_js_parts = []
    manifest = {}
    anchors = {}  # acr -> {"left": [x,y,z], "right": [x,y,z]}
    for acr, s in structures.items():
        print(f"  meshing {acr} ({int(s['mask'].sum())} voxels) ...")
        tm = mask_to_mesh(s["mask"], s["affine"], downsample=s["downsample"], smooth_iterations=s["smooth"])
        obj_path = MESH_DIR / f"{acr}.obj"
        tm.export(obj_path)
        # V1 is bilateral (left+right blobs); a plain centroid collapses
        # toward the midline, floating between the two blobs rather than
        # inside either one. Compute both hemispheres' means so BOTH the
        # crossed and uncrossed branches can anchor to the side they
        # actually terminate on - unlike audition, vision genuinely
        # terminates on both sides from one eye, so no single ANCHOR_SIDE
        # constant is needed here.
        right_verts = tm.vertices[tm.vertices[:, 0] > 0]
        left_verts = tm.vertices[tm.vertices[:, 0] < 0]
        anchors[acr] = {
            "right": (right_verts.mean(axis=0) if len(right_verts) else tm.centroid).tolist(),
            "left": (left_verts.mean(axis=0) if len(left_verts) else tm.centroid).tolist(),
        }
        manifest[acr] = {
            "name": s["name"], "color": s["color"],
            "mesh_path": f"mesh/{acr}.obj", "vertex_count": len(tm.vertices),
            "anchor_um": anchors[acr],
        }
        regions_js_parts.append(mesh_to_region_js(acr, tm, s["color"]))

    (MESH_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    regions_js = "{" + ",".join(regions_js_parts) + "}"
    order_js = json.dumps(["skull", "root", "V1"])

    # derive EXTENT from the actual root mesh bounding box, not a guess
    root_tm = trimesh.load(MESH_DIR / "root.obj")
    extent = float((root_tm.vertices.max(axis=0) - root_tm.vertices.min(axis=0)).max())

    # schematic waypoints in um as [x, y, z, marker_radius_um]; real
    # endpoints anchored to whichever hemisphere of the V1 mesh each branch
    # actually ends on
    vis_waypoints = {
        k: [v["pos"][0] * MM_TO_UM, v["pos"][1] * MM_TO_UM, v["pos"][2] * MM_TO_UM, v["r"] * MM_TO_UM]
        for k, v in VISUAL_SCHEMATIC.items()
    }
    vis_waypoints["V1_R"] = anchors["V1"]["right"] + [0]
    vis_waypoints["V1_L"] = anchors["V1"]["left"] + [0]

    legend_meta = [
        {"acr": "skull", "name_en": manifest["skull"]["name"], "name_zh": f"頭部大小示意(腦部外擴{SKULL_MARGIN_MM}mm,非真實顱骨解剖)",
         "color": "FFFFFF", "outline": True, "default_checked": True},
        {"acr": "root", "name_en": "Whole-brain outline (MNI152)", "name_zh": "全腦輪廓(MNI152)",
         "color": "CCCCCC", "outline": True, "default_checked": True},
        {"acr": "V1", "name_en": manifest["V1"]["name"], "name_zh": "初級視覺皮質(距狀溝皮質)",
         "color": manifest["V1"]["color"], "outline": False, "default_checked": True},
    ]

    three_js = (WEB_LIB_DIR / "three.min.js").read_text(encoding="utf-8")
    orbit_js = (WEB_LIB_DIR / "OrbitControls.js").read_text(encoding="utf-8")

    html = TEMPLATE.format(
        three_js=three_js,
        orbit_js=orbit_js,
        extent=extent,
        regions_js=regions_js,
        order_js=order_js,
        strings_json=json.dumps(STRINGS, ensure_ascii=False),
        legend_meta_json=json.dumps(legend_meta, ensure_ascii=False),
        vis_waypoints_json=json.dumps(vis_waypoints),
        vis_labels_json=json.dumps(VISUAL_LABELS, ensure_ascii=False),
        vis_real_json=json.dumps(["V1_R", "V1_L"]),
        uncrossed_order_json=json.dumps(VISUAL_UNCROSSED_ORDER),
        crossed_order_json=json.dumps(VISUAL_CROSSED_ORDER),
        reflex_order_json=json.dumps(REFLEX_ORDER),
    )

    out_path = OUT_DIR / OUT_FILE
    out_path.write_text(html, encoding="utf-8")
    # without this the bare Cloudflare Pages domain 404s (no index.html)
    (OUT_DIR / "index.html").write_text(
        f'<meta http-equiv="refresh" content="0; url={OUT_FILE}">\n'
        f'<a href="{OUT_FILE}">{OUT_FILE}</a>\n',
        encoding="utf-8",
    )
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


TEMPLATE = """<title>視覺系統</title>
<style>
  :root {{
    --bg: #12151a;
    --panel: rgba(27, 32, 40, 0.86);
    --panel-border: #2b323d;
    --text: #e9edf1;
    --text-dim: #8b96a3;
    --text-faint: #5c6672;
    --accent: #5a8fe0;
    --accent2: #8fe0a0;
    --mono: ui-monospace, "Cascadia Code", "SF Mono", "JetBrains Mono", Consolas, "Liberation Mono", monospace;
    --sans: -apple-system, "Segoe UI", system-ui, Roboto, sans-serif;
  }}

  * {{ box-sizing: border-box; }}

  html, body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    overflow: hidden;
  }}

  #scene {{ position: fixed; inset: 0; display: block; }}
  #scene canvas {{ display: block; width: 100%; height: 100%; }}

  .ui {{ position: fixed; pointer-events: none; z-index: 10; }}

  header.ui {{
    top: 0; left: 0; right: 0;
    padding: 28px 32px 0;
    display: flex; flex-direction: column; gap: 4px;
  }}

  .eyebrow {{
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-faint);
  }}

  h1 {{
    margin: 0;
    font-family: var(--mono);
    font-weight: 600;
    font-size: clamp(20px, 2.6vw, 30px);
    letter-spacing: 0.01em;
    text-wrap: balance;
    color: var(--text);
  }}

  h1 .accent {{ color: var(--accent); }}

  .subtitle {{ font-size: 13px; color: var(--text-dim); max-width: 52ch; }}

  .panel {{
    pointer-events: auto;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    backdrop-filter: blur(10px);
    border-radius: 10px;
  }}

  .legend {{
    left: 24px; bottom: 24px;
    padding: 10px 14px;
    display: flex; flex-direction: column; gap: 2px;
    min-width: 220px;
    max-width: 260px;
    max-height: min(70vh, 560px);
  }}

  .legend-title {{
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-faint);
    padding: 4px 2px 8px;
  }}

  .legend-title--toggle {{
    display: flex; align-items: center; justify-content: space-between;
    cursor: pointer;
    user-select: none;
  }}

  .legend-title--toggle .chevron {{ font-size: 12px; transition: transform 0.15s ease; }}

  .legend-body {{
    display: flex; flex-direction: column; gap: 2px;
    overflow-y: auto;
  }}

  .legend.collapsed .legend-body {{ display: none; }}
  .legend.collapsed .legend-title .chevron {{ transform: rotate(-90deg); }}
  .legend.collapsed {{ max-height: none; }}

  .legend-row {{
    display: flex; align-items: center; gap: 10px;
    padding: 7px 6px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.15s ease;
  }}

  .legend-row:hover {{ background: rgba(255, 255, 255, 0.045); }}

  .legend-row input {{
    appearance: none;
    width: 13px; height: 13px;
    border: 1.5px solid var(--text-faint);
    border-radius: 3px;
    margin: 0; flex: none;
    position: relative;
    cursor: pointer;
  }}

  .legend-row input:checked {{ border-color: var(--accent); background: var(--accent); }}

  .legend-row input:checked::after {{
    content: "";
    position: absolute; left: 3px; top: 0px;
    width: 3px; height: 7px;
    border: solid #12151a;
    border-width: 0 1.6px 1.6px 0;
    transform: rotate(40deg);
  }}

  .swatch {{
    width: 12px; height: 12px;
    border-radius: 3px;
    background: var(--swatch);
    flex: none;
    box-shadow: 0 0 8px color-mix(in srgb, var(--swatch) 65%, transparent);
  }}

  .swatch--outline {{ background: transparent; border: 1.5px solid var(--text-faint); box-shadow: none; }}
  .swatch--wireframe {{ background: transparent; border: 1.5px dashed var(--swatch); box-shadow: none; }}

  .legend-text {{ display: flex; flex-direction: column; line-height: 1.25; }}
  .legend-acr {{ font-family: var(--mono); font-size: 12.5px; color: var(--text); }}
  .legend-name {{ font-size: 11px; color: var(--text-dim); }}

  .legend-row--outline {{ margin-top: 4px; border-top: 1px solid var(--panel-border); padding-top: 10px; }}

  .legend-note {{
    font-size: 10.5px;
    color: var(--text-faint);
    padding: 8px 6px 0;
    line-height: 1.5;
    border-top: 1px solid var(--panel-border);
    margin-top: 4px;
  }}

  .lang-toggle {{
    right: 24px; top: 20px;
    padding: 8px 16px;
    font-family: var(--mono);
    font-size: 12px;
    letter-spacing: 0.04em;
    color: var(--text);
    cursor: pointer;
    z-index: 11;
  }}

  .lang-toggle:hover {{ border-color: var(--accent); color: var(--accent); }}

  .hover-info {{
    right: 24px; top: 132px;
    padding: 12px 14px;
    max-width: 240px;
    display: none;
  }}

  .hover-info.show {{ display: block; }}

  .hover-label {{ font-size: 13px; color: var(--text); line-height: 1.4; }}

  .hint {{
    right: 24px; bottom: 24px;
    padding: 10px 14px;
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--text-faint);
    text-align: right;
    line-height: 1.6;
    letter-spacing: 0.01em;
    max-width: 320px;
  }}

  .hint-title--toggle {{
    display: flex; align-items: center; justify-content: flex-end; gap: 8px;
    cursor: pointer;
    user-select: none;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 10px;
  }}

  .hint-title--toggle .chevron {{ font-size: 12px; transition: transform 0.15s ease; }}

  .hint-body {{ padding-top: 8px; }}

  .hint.collapsed .hint-body {{ display: none; }}
  .hint.collapsed .hint-title--toggle .chevron {{ transform: rotate(-90deg); }}

  .hint b {{ color: var(--text-dim); font-weight: 500; }}

  .loading {{
    position: fixed; inset: 0;
    display: flex; align-items: center; justify-content: center;
    font-family: var(--mono);
    font-size: 12px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-faint);
    z-index: 20;
    background: var(--bg);
    transition: opacity 0.4s ease;
  }}

  .loading.hidden {{ opacity: 0; pointer-events: none; }}

  @media (prefers-reduced-motion: reduce) {{ .loading {{ transition: none; }} }}
</style>

<div id="scene"></div>
<div class="loading" id="loading">Loading meshes&hellip;</div>

<button class="panel lang-toggle ui" id="langToggle" type="button">中文</button>

<header class="ui">
  <span class="eyebrow" id="txtEyebrow">Human &middot; MNI152 space &middot; peripheral&rarr;central pathway</span>
  <h1>視覺系統 <span id="txtTitleSuffix"><span class="accent">Visual</span> &amp; <span style="color:var(--accent2)">Reflex</span> Pathways</span></h1>
  <span class="subtitle" id="txtSubtitle">The visual pathway from right eye to cortex, showing the optic chiasm's <b>partial decussation</b> &mdash; temporal (lateral) retina fibers stay <b>uncrossed</b> (ipsilateral), nasal (medial) retina fibers <b>cross</b> at the chiasm (contralateral); net result, each hemisphere's visual cortex represents the <b>opposite</b> half of the visual field. A reflex branch continues from the chiasm to the superior colliculus and oculomotor nuclei (pupillary / eye-movement reflexes). Solid meshes are real MNI152-space anatomy; wireframe markers are schematic, illustrative placements for structures too small or too deep for any freely available 3D atlas. Hover a node for a locator line + slice plane.</span>
</header>

<div class="panel hover-info ui" id="hoverPanel">
  <div class="legend-title" id="txtHoverTitle">Hovered structure</div>
  <div class="hover-label" id="hoverLabel"></div>
</div>

<div class="panel legend ui collapsed" id="legendPanel">
  <div class="legend-title legend-title--toggle" id="legendToggle">
    <span id="txtStructuresTitle">Structures</span>
    <span class="chevron">&#9660;</span>
  </div>
  <div class="legend-body" id="legendBody">
    <div id="legendList"></div>
    <label class="legend-row legend-row--outline" data-acr="visual">
      <input type="checkbox" id="visualToggle" checked />
      <span class="swatch" style="--swatch:#5a8fe0"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtVisualName">Visual pathway</span>
        <span class="legend-name" id="txtVisualDesc">retina &rarr; chiasm &rarr; LGN &rarr; ... &rarr; V1 (crossed + uncrossed)</span>
      </span>
    </label>
    <label class="legend-row" data-acr="reflex">
      <input type="checkbox" id="reflexToggle" />
      <span class="swatch" style="--swatch:#8fe0a0"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtReflexName">Reflex pathway</span>
        <span class="legend-name" id="txtReflexDesc">chiasm &rarr; superior colliculus &rarr; oculomotor nuclei</span>
      </span>
    </label>
    <label class="legend-row" data-acr="signal">
      <input type="checkbox" id="signalToggle" checked />
      <span class="swatch" style="--swatch:#ffe9a8"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtSignalName">Neural signal</span>
        <span class="legend-name" id="txtSignalDesc">animated light pulse, retina &rarr; visual cortex</span>
      </span>
    </label>
    <div class="legend-note" id="txtLegendNote">Dashed swatch / wireframe sphere = schematic node, not a real segmented structure. Click "Structures" to collapse this panel.</div>
  </div>
</div>

<div class="panel hint ui collapsed" id="hintPanel">
  <div class="hint-title--toggle" id="hintToggle">
    <span id="txtControlsTitle">Controls</span>
    <span class="chevron">&#9660;</span>
  </div>
  <div class="hint-body" id="hintBody">
    <span id="txtHintControls"><b>drag</b> orbit &nbsp; <b>scroll</b> zoom &nbsp; <b>right-drag</b> pan &nbsp; <b>hover</b> a node for a slice plane</span><br />
    <span id="txtHintUnits">MNI152 space (mm, &times;1000 &rarr; &micro;m)</span>
  </div>
</div>

{three_js}
{orbit_js}
<script>
const REGIONS = {regions_js};
const EXTENT = {extent};
const ORDER = {order_js};
</script>
<script>
(function () {{
  function b64ToFloat32(b64) {{
    const bin = atob(b64);
    const buf = new ArrayBuffer(bin.length);
    const view = new Uint8Array(buf);
    for (let i = 0; i < bin.length; i++) view[i] = bin.charCodeAt(i);
    return new Float32Array(buf);
  }}
  function b64ToUint32(b64) {{
    const bin = atob(b64);
    const buf = new ArrayBuffer(bin.length);
    const view = new Uint8Array(buf);
    for (let i = 0; i < bin.length; i++) view[i] = bin.charCodeAt(i);
    return new Uint32Array(buf);
  }}

  const container = document.getElementById("scene");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, window.innerWidth / window.innerHeight, 1, EXTENT * 6);
  // MNI152 RAS: x=Right+, y=Anterior+, z=Superior+. No axis flip needed -
  // +Y is already "up" in the sense that matters for a 3/4 anterolateral view.
  const dist = EXTENT * 1.3;
  camera.position.set(dist * 0.55, -dist * 0.55, dist * 0.5);
  camera.up.set(0, 0, 1);

  const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: false }});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x12151a, 1);
  renderer.outputEncoding = THREE.sRGBEncoding;
  container.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = EXTENT * 0.15;
  controls.maxDistance = EXTENT * 3;
  controls.autoRotate = !reduceMotion;
  controls.autoRotateSpeed = 0.6;
  controls.addEventListener("start", () => {{ controls.autoRotate = false; }});
  controls.target.set(0, 0, 0);

  scene.add(new THREE.HemisphereLight(0xaebfd4, 0x14171c, 0.55));
  const key = new THREE.DirectionalLight(0xffffff, 0.85);
  key.position.set(EXTENT * 0.6, EXTENT * 0.9, EXTENT * 0.7);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0x8fb4ff, 0.3);
  fill.position.set(-EXTENT * 0.7, -EXTENT * 0.2, -EXTENT * 0.5);
  scene.add(fill);

  const STRINGS = {strings_json};
  let LANG = "en";

  // ---- shared canvas-texture text sprite (axis labels + pathway node
  // labels both use this, so language switching can redraw either kind) ----
  function drawTextCanvas(text, color, fontPx) {{
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    const family = getComputedStyle(document.body).fontFamily || "sans-serif";
    ctx.font = `700 ${{fontPx}}px ${{family}}`;
    const pad = fontPx * 0.32;
    const w = Math.ceil(ctx.measureText(text).width) + pad * 2;
    const h = fontPx + pad * 2;
    canvas.width = w; canvas.height = h;
    ctx.font = `700 ${{fontPx}}px ${{family}}`;
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.lineWidth = fontPx * 0.14;
    ctx.strokeStyle = "rgba(18,21,26,0.9)";
    ctx.strokeText(text, w / 2, h / 2);
    ctx.fillStyle = color;
    ctx.fillText(text, w / 2, h / 2);
    return canvas;
  }}

  function makeTextSprite(text, color, fontPx, scaleH, renderOrder) {{
    const canvas = drawTextCanvas(text, color, fontPx);
    const tex = new THREE.CanvasTexture(canvas);
    tex.minFilter = THREE.LinearFilter;
    const mat = new THREE.SpriteMaterial({{ map: tex, depthTest: false, depthWrite: false, transparent: true, opacity: 0.9 }});
    const sprite = new THREE.Sprite(mat);
    sprite.scale.set(scaleH * (canvas.width / canvas.height), scaleH, 1);
    sprite.renderOrder = renderOrder;
    sprite.userData = {{ fontPx, color }};
    return sprite;
  }}

  function updateTextSprite(sprite, text) {{
    const {{ fontPx, color }} = sprite.userData;
    const canvas = drawTextCanvas(text, color, fontPx);
    const oldMap = sprite.material.map;
    const tex = new THREE.CanvasTexture(canvas);
    tex.minFilter = THREE.LinearFilter;
    sprite.material.map = tex;
    sprite.material.needsUpdate = true;
    if (oldMap) oldMap.dispose();
    const scaleH = sprite.scale.y;
    sprite.scale.set(scaleH * (canvas.width / canvas.height), scaleH, 1);
  }}

  // ---- generated legend rows (root/skull/V1), not hand-written ----
  const LEGEND_META = {legend_meta_json};
  const legendDefaults = {{}};
  LEGEND_META.forEach((m) => {{ legendDefaults[m.acr] = m.default_checked; }});

  const meshes = {{}};
  ORDER.forEach((acr) => {{
    const s = REGIONS[acr];
    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(b64ToFloat32(s.pos_b64), 3));
    if (s.norm_b64) {{
      geom.setAttribute("normal", new THREE.BufferAttribute(b64ToFloat32(s.norm_b64), 3));
    }} else {{
      geom.computeVertexNormals();
    }}
    geom.setIndex(new THREE.BufferAttribute(b64ToUint32(s.idx_b64), 1));

    let mat, mesh;
    if (acr === "root") {{
      mat = new THREE.MeshStandardMaterial({{
        color: 0x7c8b99, transparent: true, opacity: 0.1,
        side: THREE.BackSide, depthWrite: false, roughness: 1,
      }});
      mesh = new THREE.Mesh(geom, mat);
      mesh.renderOrder = 10;
    }} else if (acr === "skull") {{
      // approximate head-size context shell, not real skull anatomy - kept
      // extremely subtle (smooth, not wireframe - wireframe on a
      // marching-cubes mesh this dense reads as visual noise) so it reads
      // as "here's roughly how big the head is" without competing with the
      // real anatomy inside it
      mat = new THREE.MeshStandardMaterial({{
        color: 0xffffff, transparent: true, opacity: 0.05,
        side: THREE.BackSide, depthWrite: false, roughness: 1,
      }});
      mesh = new THREE.Mesh(geom, mat);
      mesh.renderOrder = 9;
    }} else {{
      mat = new THREE.MeshStandardMaterial({{ color: parseInt(s.color, 16), roughness: 0.45, metalness: 0.05 }});
      mesh = new THREE.Mesh(geom, mat);
    }}
    mesh.visible = !!legendDefaults[acr];
    scene.add(mesh);
    meshes[acr] = mesh;
  }});

  // ---- collapsible legend panel (it sits over part of the scene) ----
  document.getElementById("legendToggle").addEventListener("click", () => {{
    document.getElementById("legendPanel").classList.toggle("collapsed");
  }});

  // ---- collapsible controls hint panel (starts collapsed) ----
  document.getElementById("hintToggle").addEventListener("click", () => {{
    document.getElementById("hintPanel").classList.toggle("collapsed");
  }});

  const legendList = document.getElementById("legendList");
  LEGEND_META.forEach((m) => {{
    const label = document.createElement("label");
    label.className = "legend-row" + (m.outline ? " legend-row--outline" : "");
    label.dataset.acr = m.acr;
    const swatchClass = m.outline ? "swatch swatch--outline" : "swatch";
    label.innerHTML = `
      <input type="checkbox" ${{m.default_checked ? "checked" : ""}} data-target="${{m.acr}}" />
      <span class="${{swatchClass}}" style="--swatch:#${{m.color}}"></span>
      <span class="legend-text">
        <span class="legend-acr">${{m.acr}}</span>
        <span class="legend-name" data-name-en="${{m.name_en}}" data-name-zh="${{m.name_zh}}">${{m.name_en}}</span>
      </span>`;
    legendList.appendChild(label);
  }});
  document.querySelectorAll("#legendList .legend-row input").forEach((el) => {{
    el.addEventListener("change", () => {{
      const target = meshes[el.dataset.target];
      if (target) target.visible = el.checked;
    }});
  }});

  // ---- axis labels ----
  const AXIS_SPRITES = [];
  (function addAxisLabels() {{
    const A = EXTENT * 0.62, S = EXTENT * 0.5, R = EXTENT * 0.55;
    const specs = [
      {{ key: "anterior", pos: [0, A, 0] }},
      {{ key: "posterior", pos: [0, -A, 0] }},
      {{ key: "superior", pos: [0, 0, S] }},
      {{ key: "right_axis", pos: [R, 0, 0] }},
    ];
    specs.forEach(({{ key, pos }}) => {{
      const sprite = makeTextSprite(STRINGS[key][LANG], "#f2f4f7", 72, EXTENT * 0.075, 999);
      sprite.position.set(...pos);
      scene.add(sprite);
      AXIS_SPRITES.push({{ sprite, key }});
    }});
  }})();

  // ---- shared pathway-drawing helper (schematic tube + nodes + labels) ----
  // HOVER_NODES collects every node (real-mesh endpoints too) across all
  // three branches so a single raycaster can drive the hover leader-line +
  // slice plane below.
  const HOVER_NODES = [];
  let hoveredNode = null;

  function buildPathway(orderedKeys, waypoints, labels, realKeys, color) {{
    const group = new THREE.Group();
    const realSet = new Set(realKeys);

    const pts = orderedKeys.map((k) => new THREE.Vector3(...waypoints[k]));
    const curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.4);
    const tubeGeom = new THREE.TubeGeometry(curve, 200, EXTENT * 0.005, 10, false);
    const tubeMat = new THREE.MeshStandardMaterial({{
      color, emissive: color, emissiveIntensity: 0.4, roughness: 0.4, metalness: 0.1,
    }});
    group.add(new THREE.Mesh(tubeGeom, tubeMat));
    group.userData.curve = curve;

    const colorHex = "#" + color.toString(16).padStart(6, "0");

    // waypoints crowd together near the eye/brainstem entry point; stagger
    // each label along Y (anterior/posterior depth) only - never Z, so each
    // label stays at its node's true superior/inferior height and the
    // on-screen vertical order always matches real anatomy
    orderedKeys.forEach((key, i) => {{
      const p = waypoints[key]; // [x, y, z, radius_um]
      const pos = new THREE.Vector3(p[0], p[1], p[2]);
      const isReal = realSet.has(key);
      if (!isReal) {{
        const r = p[3] || EXTENT * 0.01;
        const markerGeom = new THREE.SphereGeometry(r, 14, 14);
        const markerMat = new THREE.MeshBasicMaterial({{ color, wireframe: true, transparent: true, opacity: 0.85 }});
        const marker = new THREE.Mesh(markerGeom, markerMat);
        marker.position.copy(pos);
        group.add(marker);
      }}
      const label = makeTextSprite(labels[key][LANG], colorHex, 52, EXTENT * 0.032, 998);
      const step = EXTENT * 0.03;
      const yOff = (i % 2 === 0 ? -1 : 1) * step * (1 + Math.floor(i / 2) * 0.4);
      const labelPos = new THREE.Vector3(p[0], p[1] + yOff, p[2]);
      label.position.copy(labelPos);
      group.add(label);

      // invisible, generously-sized hit-test sphere so hover works even on
      // thin schematic nodes and on the (larger, real) mesh endpoints alike
      const hitGeom = new THREE.SphereGeometry(Math.max(p[3] || 0, EXTENT * 0.018), 8, 8);
      const hitMesh = new THREE.Mesh(hitGeom, new THREE.MeshBasicMaterial({{ visible: false }}));
      hitMesh.position.copy(pos);
      group.add(hitMesh);
      HOVER_NODES.push({{ mesh: hitMesh, pos, labelPos, labelSprite: label, text: labels[key], color }});
    }});

    scene.add(group);
    return group;
  }}

  const VIS_WAYPOINTS = {vis_waypoints_json};
  const VIS_LABELS = {vis_labels_json};
  const VIS_REAL = {vis_real_json};
  const UNCROSSED_ORDER = {uncrossed_order_json};
  const CROSSED_ORDER = {crossed_order_json};
  const REFLEX_ORDER = {reflex_order_json};

  // Group 1: the conscious-vision (geniculostriate) pathway - two branches
  // sharing a trunk (retina -> optic nerve -> chiasm) that diverge at the
  // chiasm: uncrossed (temporal retina, stays same side) and crossed
  // (nasal retina, flips side). Both colors echo the reference diagram's
  // red=uncrossed / blue=crossed convention.
  const visualGroup = new THREE.Group();
  const uncrossedPath = buildPathway(UNCROSSED_ORDER, VIS_WAYPOINTS, VIS_LABELS, VIS_REAL, 0xe0725a);
  const crossedPath = buildPathway(CROSSED_ORDER, VIS_WAYPOINTS, VIS_LABELS, VIS_REAL, 0x5a8fe0);
  visualGroup.add(uncrossedPath);
  visualGroup.add(crossedPath);
  visualGroup.userData.curves = [uncrossedPath.userData.curve, crossedPath.userData.curve];
  visualGroup.visible = document.getElementById("visualToggle").checked;
  scene.add(visualGroup);

  // Group 2: the reflex (tectal) branch - pupillary light reflex / eye-
  // movement reflex circuit, entirely schematic, default off (mirrors the
  // secondary-pathway-off precedent from the auditory page's vestibular toggle).
  const reflexGroup = buildPathway(REFLEX_ORDER, VIS_WAYPOINTS, VIS_LABELS, VIS_REAL, 0x8fe0a0);
  reflexGroup.visible = document.getElementById("reflexToggle").checked;

  document.getElementById("visualToggle").addEventListener("change", (e) => {{
    visualGroup.visible = e.target.checked;
  }});
  document.getElementById("reflexToggle").addEventListener("change", (e) => {{
    reflexGroup.visible = e.target.checked;
  }});

  // ---- animated "seeing light" signal: two scattered particle streams
  // (one per curve) traveling retina -> cortex, departing together and
  // diverging at the chiasm, looping. Reflex branch gets no animation,
  // matching the auditory page's precedent (only the primary pathway animates). ----
  const SIGNAL_COLOR = 0xffe9a8;
  const SIGNAL_COUNT = 26; // per curve
  const SIGNAL_DURATION = 2.4; // seconds per retina->cortex sweep
  const SIGNAL_TRAIL = 0.16; // fraction of the sweep the trailing spread covers
  const SIGNAL_JITTER = EXTENT * 0.01;

  const visualCurves = visualGroup.userData.curves;
  const signalGeom = new THREE.BufferGeometry();
  signalGeom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(SIGNAL_COUNT * visualCurves.length * 3), 3));
  const signalMat = new THREE.PointsMaterial({{
    color: SIGNAL_COLOR, size: EXTENT * 0.009, sizeAttenuation: true,
    transparent: true, opacity: 0.95, depthWrite: false, blending: THREE.AdditiveBlending,
  }});
  const signalPoints = new THREE.Points(signalGeom, signalMat);
  signalPoints.renderOrder = 1001;
  scene.add(signalPoints);

  let signalEnabled = true;
  const signalToggle = document.getElementById("signalToggle");
  signalToggle.addEventListener("change", (e) => {{ signalEnabled = e.target.checked; }});

  const clock = new THREE.Clock();
  const posArr = signalGeom.attributes.position.array;

  function updateSignal() {{
    const show = signalEnabled && visualGroup.visible;
    signalPoints.visible = show;
    if (!show) return;
    const cycle = (clock.getElapsedTime() % SIGNAL_DURATION) / SIGNAL_DURATION; // 0..1, repeats
    let idx = 0;
    visualCurves.forEach((curve) => {{
      for (let i = 0; i < SIGNAL_COUNT; i++) {{
        // each particle trails a little behind the lead, spread over
        // SIGNAL_TRAIL of the sweep, so the swarm reads as a scattered
        // pulse with a tail rather than a single dot
        const t = Math.min(0.999, Math.max(0, cycle - (i / SIGNAL_COUNT) * SIGNAL_TRAIL));
        const p = curve.getPointAt(t);
        posArr[idx * 3 + 0] = p.x + (Math.random() - 0.5) * SIGNAL_JITTER;
        posArr[idx * 3 + 1] = p.y + (Math.random() - 0.5) * SIGNAL_JITTER;
        posArr[idx * 3 + 2] = p.z + (Math.random() - 0.5) * SIGNAL_JITTER;
        idx++;
      }}
    }});
    signalGeom.attributes.position.needsUpdate = true;
  }}

  // ---- hover: leader line + coronal slice plane through the hovered node ----
  // Points at whichever node the mouse is over and drops a translucent
  // anterior-posterior (coronal-style) slice plane through it, so you can
  // see roughly where that structure sits front-to-back in the head.
  (function setupHover() {{
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    const hitMeshes = HOVER_NODES.map((n) => n.mesh);

    const lineGeom = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
    const lineMat = new THREE.LineBasicMaterial({{ color: 0xffffff, transparent: true, opacity: 0.95, depthTest: false }});
    const leaderLine = new THREE.Line(lineGeom, lineMat);
    leaderLine.visible = false;
    leaderLine.renderOrder = 1000;
    scene.add(leaderLine);

    const SPAN = EXTENT * 1.3;
    const planeGeom = new THREE.PlaneGeometry(SPAN, SPAN);
    const planeMat = new THREE.MeshBasicMaterial({{
      color: 0xffffff, transparent: true, opacity: 0.15,
      side: THREE.DoubleSide, depthWrite: false,
    }});
    const slicePlane = new THREE.Mesh(planeGeom, planeMat);
    slicePlane.add(new THREE.LineSegments(
      new THREE.EdgesGeometry(planeGeom),
      new THREE.LineBasicMaterial({{ color: 0xffffff, transparent: true, opacity: 0.6 }})
    ));
    slicePlane.rotation.x = Math.PI / 2; // normal along Y -> coronal-style slice
    slicePlane.visible = false;
    slicePlane.renderOrder = 5;
    scene.add(slicePlane);

    const sliceLabel = document.getElementById("hoverLabel");

    function updateHover(node) {{
      hoveredNode = node;
      const on = !!node;
      leaderLine.visible = on;
      slicePlane.visible = on;
      renderer.domElement.style.cursor = on ? "pointer" : "default";
      if (on) {{
        leaderLine.geometry.setFromPoints([node.pos, node.labelPos]);
        leaderLine.geometry.attributes.position.needsUpdate = true;
        slicePlane.position.set(0, node.pos.y, 0);
        sliceLabel.textContent = node.text[LANG].replace(/^[①②③④⑤⑥⑦⑧⑨]+[abc]?\\s*/, "");
        sliceLabel.parentElement.classList.add("show");
      }} else {{
        sliceLabel.parentElement.classList.remove("show");
      }}
    }}

    function onMove(ev) {{
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(hitMeshes, false);
      if (hits.length) {{
        const node = HOVER_NODES.find((n) => n.mesh === hits[0].object);
        if (node !== hoveredNode) updateHover(node);
      }} else if (hoveredNode) {{
        updateHover(null);
      }}
    }}
    renderer.domElement.addEventListener("mousemove", onMove);
    renderer.domElement.addEventListener("mouseleave", () => updateHover(null));
  }})();

  // ---- EN / 中文 toggle: swaps DOM copy + regenerates every canvas-texture
  // label sprite (axis labels, pathway node labels) in the new language ----
  function applyLang() {{
    document.querySelectorAll("[id^='txt']").forEach((el) => {{
      const key = {{
        txtEyebrow: "eyebrow", txtTitleSuffix: "title_suffix", txtSubtitle: "subtitle",
        txtHoverTitle: "hover_title", txtStructuresTitle: "structures_title",
        txtVisualName: "visual_pathway_name", txtVisualDesc: "visual_pathway_desc",
        txtReflexName: "reflex_pathway_name", txtReflexDesc: "reflex_pathway_desc",
        txtSignalName: "signal_name", txtSignalDesc: "signal_desc",
        txtLegendNote: "legend_note", txtHintControls: "hint_controls", txtHintUnits: "hint_units",
        txtControlsTitle: "controls_title",
      }}[el.id];
      if (key) el.innerHTML = STRINGS[key][LANG];
    }});
    document.querySelectorAll("#legendList .legend-name").forEach((el) => {{
      el.textContent = LANG === "zh" ? el.dataset.nameZh : el.dataset.nameEn;
    }});
    langToggleBtn.textContent = STRINGS.lang_button[LANG];

    AXIS_SPRITES.forEach(({{ sprite, key }}) => updateTextSprite(sprite, STRINGS[key][LANG]));
    HOVER_NODES.forEach((n) => updateTextSprite(n.labelSprite, n.text[LANG]));
    if (hoveredNode) {{
      document.getElementById("hoverLabel").textContent =
        hoveredNode.text[LANG].replace(/^[①②③④⑤⑥⑦⑧⑨]+[abc]?\\s*/, "");
    }}
  }}

  const langToggleBtn = document.getElementById("langToggle");
  langToggleBtn.addEventListener("click", () => {{
    LANG = LANG === "en" ? "zh" : "en";
    applyLang();
  }});

  function resize() {{
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }}
  window.addEventListener("resize", resize);

  function animate() {{
    requestAnimationFrame(animate);
    controls.update();
    updateSignal();
    renderer.render(scene, camera);
  }}
  animate();

  document.getElementById("loading").classList.add("hidden");
}})();
</script>
"""


if __name__ == "__main__":
    main()
