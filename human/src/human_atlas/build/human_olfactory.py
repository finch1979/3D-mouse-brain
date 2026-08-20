"""
Build a self-contained 3D viewer for the human olfactory pathway
(peripheral -> central). Third sibling to human_auditory.py and
human_visual.py - same architecture, same rigor about real anatomy vs.
schematic placeholders.

HEADLINE FACT this page exists to teach: olfaction is the one sensory
system that BYPASSES THE THALAMUS. Primary olfactory cortex receives
direct input from the olfactory bulb with no obligatory thalamic relay,
unlike vision/audition/touch (Wilson & Sullivan, Neuron 2005, "Perception
without a Thalamus"; Gottfried & Zald 2005 meta-analysis; Courtiol &
Wilson 2015). The mediodorsal thalamus DOES participate, but as a
parallel, secondary route (primary olfactory cortex -> MD -> orbitofrontal
cortex) implicated in odor ATTENTION rather than baseline detection - it's
drawn here as a separately toggleable pathway so the detour olfaction gets
to skip is visible by comparison.

IMPORTANT laterality note - the olfactory pathway is STRICTLY IPSILATERAL,
with NO decussation anywhere. Each nostril projects to the same-side
olfactory bulb; the tract and both the lateral and medial olfactory striae
stay ipsilateral all the way to primary olfactory cortex (PLOS Biology
2020; StatPearls NBK556051; this is exactly why clinical smell testing is
done one nostril at a time). The anterior commissure carries a MODULATORY
interhemispheric link between the two anterior olfactory nuclei/bulbs -
that is not a decussation of the main sensory pathway and is deliberately
not drawn. Unlike the auditory page (full crossing at the trapezoid body)
and the visual page (partial crossing at the optic chiasm), the notable
fact here is the ABSENCE of a crossing - so don't "helpfully" add one, and
don't mirror any branch to the left side.

Real data sources (all MNI152 space):
  - Whole-brain outline: nilearn's bundled MNI152 brain mask.
  - Everything else: AAL3 (Rolls et al., NeuroImage 2020) via
    nilearn.datasets.fetch_atlas_aal(version="3v2"). Unusually for these
    pages, MOST central olfactory targets have real atlas data - contrast
    with the auditory page (2 real structures) and visual page (1).
    Verified label indices:
      Olfactory_L/R           17, 18       -> primary olfactory cortex
      Amygdala_L/R            45, 46       -> olfactory amygdala target
      ParaHippocampal_L/R     43, 44       -> entorhinal cortex proxy
      Thal_MDm/MDl_L/R        135-138      -> mediodorsal thalamus
      OFCmed_L/R, OFCpost_L/R 25,26,29,30  -> olfactory orbitofrontal cortex

Caveats on those real parcels, so nothing is misrepresented:
  - AAL3 "Olfactory" is one combined parcel covering the olfactory-cortex
    region (including the olfactory tubercle); it is NOT a piriform-only or
    tubercle-only label.
  - "ParaHippocampal" is a COARSE PROXY for entorhinal cortex. True
    entorhinal parcellation needs FreeSurfer's Desikan-Killiany atlas -
    same full-suite impracticality on this Windows box that ruled out
    FreeSurfer's thalamic-nuclei atlas for MGN (auditory page) and LGN
    (visual page).
  - OFC uses OFCmed + OFCpost only (the posterior-medial "olfactory OFC"
    territory), not all four AAL3 OFC subparcels.

Necessarily SCHEMATIC (no freely downloadable MNI mask exists - checked):
olfactory epithelium, olfactory nerve / fila olfactoria, olfactory bulb,
olfactory tract, olfactory trigone, anterior olfactory nucleus. The
olfactory bulb in particular is notoriously unsegmentable on standard MRI
(~77 mm^3, plus sinus susceptibility artifact); the only open tool is
Deep-MI's per-subject segmentation model, not a static atlas.

All real meshes are scaled from mm to micrometers (x1000), matching the
rest of this project's human-mesh convention.

Usage:
    python -m human_atlas.build.human_olfactory
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
CACHE_DIR = DATA_CACHE_DIR / "human_olfactory"
OUT_DIR = OUTPUTS_DIR / "olfactory_system"
MESH_DIR = OUT_DIR / "mesh"
OUT_FILE = "human_olfactory_system_3d.html"

ROOT_DOWNSAMPLE = 0.35  # whole-brain mask is ~2M voxels; downsample before marching cubes
SKULL_MARGIN_MM = 9  # dilation margin (mm, ~1mm/voxel) for the approx. head-size context shell

# AAL3 label indices, verified by direct inspection of the fetched atlas.
AAL_OLFACTORY = [17, 18]
AAL_AMYGDALA = [45, 46]
AAL_PARAHIPPOCAMPAL = [43, 44]
AAL_THAL_MD = [135, 136, 137, 138]
AAL_OFC = [25, 26, 29, 30]  # OFCmed_L/R, OFCpost_L/R

# Approximate, illustrative MNI coordinates (mm, RAS) + an approximate
# marker radius (mm) for structures with no practical open mesh source.
# Right side only - the pathway never crosses (see laterality note above).
OLF_SCHEMATIC = {
    "Epithelium": {"pos": (7, 34, -48), "r": 4},
    "CN1": {"pos": (6, 28, -40), "r": 1.5},
    "Bulb": {"pos": (6, 24, -32), "r": 3.5},
    "AON": {"pos": (6, 16, -28), "r": 2},
    "Tract": {"pos": (8, 8, -26), "r": 1.5},
    "Trigone": {"pos": (10, 2, -22), "r": 2},
}
OLF_TRUNK = ["Epithelium", "CN1", "Bulb", "AON", "Tract", "Trigone"]
# Group 1 - the direct, thalamus-bypassing olfactory pathway. Three
# branches sharing the trunk, each terminating on a REAL mesh.
OLF_AMY_ORDER = OLF_TRUNK + ["OLFC", "AMY"]
OLF_ENT_ORDER = OLF_TRUNK + ["OLFC", "ENT"]
OLF_OFC_ORDER = OLF_TRUNK + ["OLFC", "OFC"]
# Group 2 - the parallel, secondary route through mediodorsal thalamus.
THALAMIC_ORDER = OLF_TRUNK + ["OLFC", "MD", "OFC"]

OLFACTORY_LABELS = {
    "Epithelium": {"en": "① Olfactory epithelium (right nasal cavity)", "zh": "①嗅覺上皮(右鼻腔)"},
    "CN1": {"en": "② Olfactory nerve (CN I) — through cribriform plate", "zh": "②嗅神經(第一對腦神經)—穿過篩板"},
    "Bulb": {"en": "③ Olfactory bulb", "zh": "③嗅球"},
    "AON": {"en": "④ Anterior olfactory nucleus", "zh": "④前嗅核"},
    "Tract": {"en": "⑤ Olfactory tract", "zh": "⑤嗅束"},
    "Trigone": {"en": "⑥ Olfactory trigone — striae diverge", "zh": "⑥嗅三角—嗅紋分岔"},
    "OLFC": {"en": "⑦ Primary olfactory cortex (no thalamic relay)", "zh": "⑦初級嗅覺皮質(不經視丘轉接)"},
    "AMY": {"en": "⑧a Olfactory amygdala", "zh": "⑧a嗅覺杏仁核"},
    "ENT": {"en": "⑧b Entorhinal cortex → hippocampus", "zh": "⑧b內嗅皮質→海馬迴"},
    "OFC": {"en": "⑧c Orbitofrontal cortex — direct", "zh": "⑧c眶額皮質—直接路徑"},
    "MD": {"en": "⑧d Mediodorsal thalamus — attention route", "zh": "⑧d背內側視丘—注意力路徑"},
}

# All static UI copy, en/zh. Node-label sprites (OLFACTORY_LABELS above)
# are translated separately since they're baked into canvas textures, not DOM text.
STRINGS = {
    "eyebrow": {"en": "Human &middot; MNI152 space &middot; peripheral&rarr;central pathway",
                "zh": "人腦 &middot; MNI152 空間 &middot; 周邊&rarr;中樞路徑"},
    "title_suffix": {"en": '<span class="accent">Olfactory</span> &amp; <span style="color:var(--accent2)">Thalamic</span> Pathways',
                      "zh": '<span class="accent">嗅覺</span>與<span style="color:var(--accent2)">視丘</span>路徑'},
    "subtitle": {
        "en": "The olfactory pathway from right nasal cavity to cortex. Olfaction is the one sensory system that <b>bypasses the thalamus</b> &mdash; primary olfactory cortex receives bulb input <b>directly</b>, with no obligatory thalamic relay, and projects straight on to the amygdala, entorhinal cortex and orbitofrontal cortex. Toggle the <b>thalamic route</b> to see the parallel, secondary detour through the mediodorsal thalamus (linked to odor attention rather than detection). Note also that this pathway <b>never crosses the midline</b> &mdash; unlike hearing and vision, each nostril's signal stays strictly on its own side, which is why smell is tested one nostril at a time. Solid meshes are real MNI152-space anatomy (AAL3 atlas); wireframe markers are schematic, illustrative placements for structures too small or too deep for any freely available 3D atlas. Hover a node for a locator line + slice plane.",
        "zh": "從右鼻腔到皮質的嗅覺路徑。嗅覺是唯一<b>不經過視丘</b>的感覺系統&mdash;初級嗅覺皮質<b>直接</b>接收來自嗅球的訊號,不需要視丘轉接,並直接投射到杏仁核、內嗅皮質與眶額皮質。開啟<b>視丘路徑</b>可以看到經過背內側視丘的平行次要繞道(與氣味的注意力有關,而非偵測本身)。另外要注意,這條路徑<b>從不跨越中線</b>&mdash;不像聽覺與視覺,每個鼻孔的訊號都嚴格留在同側,這也是臨床上嗅覺要一次測一邊鼻孔的原因。實心網格是真實的 MNI152 空間解剖構造(AAL3 圖譜);線框標記是示意性的,代表目前沒有任何免費 3D 圖譜可用的過小或過深結構的概略位置。將滑鼠移到節點上可顯示指示線與切面。",
    },
    "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
    "structures_title": {"en": "Structures", "zh": "結構"},
    "legend_note": {"en": "Dashed swatch / wireframe sphere = schematic node, not a real segmented structure. Click &quot;Structures&quot; to collapse this panel.",
                     "zh": "虛線色塊／線框球體＝示意節點,並非真實分割出的解剖構造。點擊「結構」可收合此面板。"},
    "olfactory_pathway_name": {"en": "Olfactory pathway", "zh": "嗅覺路徑"},
    "olfactory_pathway_desc": {"en": "bulb &rarr; olfactory cortex &rarr; amygdala / entorhinal / OFC", "zh": "嗅球&rarr;嗅覺皮質&rarr;杏仁核／內嗅／眶額"},
    "thalamic_pathway_name": {"en": "Thalamic route", "zh": "視丘路徑"},
    "thalamic_pathway_desc": {"en": "the secondary detour: olfactory cortex &rarr; MD thalamus &rarr; OFC", "zh": "次要繞道:嗅覺皮質&rarr;背內側視丘&rarr;眶額皮質"},
    "signal_name": {"en": "Neural signal", "zh": "神經訊號"},
    "signal_desc": {"en": "animated odor pulse, epithelium &rarr; cortex", "zh": "動畫氣味訊號,嗅覺上皮&rarr;皮質"},
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
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading MNI152 brain mask + AAL3 atlas ...")
    mni_img = datasets.load_mni152_brain_mask()
    aal = datasets.fetch_atlas_aal(version="3v2", data_dir=str(CACHE_DIR))
    aal_img = nib.load(aal.maps) if isinstance(aal.maps, str) else aal.maps
    aal_data = aal_img.get_fdata()

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
        "OLFC": {
            "mask": np.isin(aal_data, AAL_OLFACTORY), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 15,
            "color": "8FBF7F", "name": "Primary olfactory cortex (AAL3 olfactory region)",
        },
        "AMY": {
            "mask": np.isin(aal_data, AAL_AMYGDALA), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 15,
            "color": "E0A458", "name": "Amygdala (olfactory amygdala target)",
        },
        "ENT": {
            "mask": np.isin(aal_data, AAL_PARAHIPPOCAMPAL), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 15,
            "color": "C98FBF", "name": "Entorhinal cortex (parahippocampal proxy)",
        },
        "MD": {
            "mask": np.isin(aal_data, AAL_THAL_MD), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 15,
            "color": "D094D9", "name": "Mediodorsal thalamus (AAL3 Thal_MDm + Thal_MDl)",
        },
        "OFC": {
            "mask": np.isin(aal_data, AAL_OFC), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 15,
            "color": "6FB0E0", "name": "Orbitofrontal cortex (AAL3 OFCmed + OFCpost)",
        },
    }

    regions_js_parts = []
    manifest = {}
    anchors = {}  # acr -> {"left": [x,y,z], "right": [x,y,z]}
    for acr, s in structures.items():
        voxels = int(s["mask"].sum())
        if voxels == 0:
            raise RuntimeError(f"{acr} mask is empty - label indices or affine are wrong")
        print(f"  meshing {acr} ({voxels} voxels) ...")
        tm = mask_to_mesh(s["mask"], s["affine"], downsample=s["downsample"], smooth_iterations=s["smooth"])
        obj_path = MESH_DIR / f"{acr}.obj"
        tm.export(obj_path)
        # The AAL3 structures are all bilateral (left+right blobs); a plain
        # centroid collapses toward the midline, floating between the two
        # blobs rather than inside either one. Compute per-hemisphere means
        # so the pathway can anchor inside the blob it actually terminates
        # in - always the RIGHT one here, since olfaction never crosses.
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
    order_js = json.dumps(["skull", "root", "OLFC", "AMY", "ENT", "MD", "OFC"])

    # derive EXTENT from the actual root mesh bounding box, not a guess
    root_tm = trimesh.load(MESH_DIR / "root.obj")
    extent = float((root_tm.vertices.max(axis=0) - root_tm.vertices.min(axis=0)).max())

    # schematic waypoints in um as [x, y, z, marker_radius_um]; every real
    # endpoint anchors to the RIGHT hemisphere blob (ipsilateral, no crossing)
    olf_waypoints = {
        k: [v["pos"][0] * MM_TO_UM, v["pos"][1] * MM_TO_UM, v["pos"][2] * MM_TO_UM, v["r"] * MM_TO_UM]
        for k, v in OLF_SCHEMATIC.items()
    }
    for acr in ("OLFC", "AMY", "ENT", "MD", "OFC"):
        olf_waypoints[acr] = anchors[acr]["right"] + [0]

    legend_meta = [
        {"acr": "skull", "name_en": manifest["skull"]["name"], "name_zh": f"頭部大小示意(腦部外擴{SKULL_MARGIN_MM}mm,非真實顱骨解剖)",
         "color": "FFFFFF", "outline": True, "default_checked": True},
        {"acr": "root", "name_en": "Whole-brain outline (MNI152)", "name_zh": "全腦輪廓(MNI152)",
         "color": "CCCCCC", "outline": True, "default_checked": True},
        {"acr": "OLFC", "name_en": manifest["OLFC"]["name"], "name_zh": "初級嗅覺皮質(AAL3 嗅覺區)",
         "color": manifest["OLFC"]["color"], "outline": False, "default_checked": True},
        {"acr": "AMY", "name_en": manifest["AMY"]["name"], "name_zh": "杏仁核(嗅覺杏仁核目標)",
         "color": manifest["AMY"]["color"], "outline": False, "default_checked": True},
        {"acr": "OFC", "name_en": manifest["OFC"]["name"], "name_zh": "眶額皮質(AAL3 OFCmed + OFCpost)",
         "color": manifest["OFC"]["color"], "outline": False, "default_checked": True},
        {"acr": "ENT", "name_en": manifest["ENT"]["name"], "name_zh": "內嗅皮質(以海馬旁迴代替)",
         "color": manifest["ENT"]["color"], "outline": False, "default_checked": True},
        {"acr": "MD", "name_en": manifest["MD"]["name"], "name_zh": "背內側視丘(AAL3 Thal_MDm + Thal_MDl)",
         "color": manifest["MD"]["color"], "outline": False, "default_checked": False},
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
        olf_waypoints_json=json.dumps(olf_waypoints),
        olf_labels_json=json.dumps(OLFACTORY_LABELS, ensure_ascii=False),
        olf_real_json=json.dumps(["OLFC", "AMY", "ENT", "MD", "OFC"]),
        amy_order_json=json.dumps(OLF_AMY_ORDER),
        ent_order_json=json.dumps(OLF_ENT_ORDER),
        ofc_order_json=json.dumps(OLF_OFC_ORDER),
        thalamic_order_json=json.dumps(THALAMIC_ORDER),
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


TEMPLATE = """<title>嗅覺系統</title>
<style>
  :root {{
    --bg: #12151a;
    --panel: rgba(27, 32, 40, 0.86);
    --panel-border: #2b323d;
    --text: #e9edf1;
    --text-dim: #8b96a3;
    --text-faint: #5c6672;
    --accent: #8fbf7f;
    --accent2: #d094d9;
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
  <h1>嗅覺系統 <span id="txtTitleSuffix"><span class="accent">Olfactory</span> &amp; <span style="color:var(--accent2)">Thalamic</span> Pathways</span></h1>
  <span class="subtitle" id="txtSubtitle">The olfactory pathway from right nasal cavity to cortex. Olfaction is the one sensory system that <b>bypasses the thalamus</b> &mdash; primary olfactory cortex receives bulb input <b>directly</b>, with no obligatory thalamic relay, and projects straight on to the amygdala, entorhinal cortex and orbitofrontal cortex. Toggle the <b>thalamic route</b> to see the parallel, secondary detour through the mediodorsal thalamus (linked to odor attention rather than detection). Note also that this pathway <b>never crosses the midline</b> &mdash; unlike hearing and vision, each nostril's signal stays strictly on its own side, which is why smell is tested one nostril at a time. Solid meshes are real MNI152-space anatomy (AAL3 atlas); wireframe markers are schematic, illustrative placements for structures too small or too deep for any freely available 3D atlas. Hover a node for a locator line + slice plane.</span>
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
    <label class="legend-row legend-row--outline" data-acr="olfactory">
      <input type="checkbox" id="olfactoryToggle" checked />
      <span class="swatch" style="--swatch:#8fbf7f"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtOlfactoryName">Olfactory pathway</span>
        <span class="legend-name" id="txtOlfactoryDesc">bulb &rarr; olfactory cortex &rarr; amygdala / entorhinal / OFC</span>
      </span>
    </label>
    <label class="legend-row" data-acr="thalamic">
      <input type="checkbox" id="thalamicToggle" />
      <span class="swatch" style="--swatch:#d094d9"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtThalamicName">Thalamic route</span>
        <span class="legend-name" id="txtThalamicDesc">the secondary detour: olfactory cortex &rarr; MD thalamus &rarr; OFC</span>
      </span>
    </label>
    <label class="legend-row" data-acr="signal">
      <input type="checkbox" id="signalToggle" checked />
      <span class="swatch" style="--swatch:#e8f5a8"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtSignalName">Neural signal</span>
        <span class="legend-name" id="txtSignalDesc">animated odor pulse, epithelium &rarr; cortex</span>
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
  // MNI152 RAS: x=Right+, y=Anterior+, z=Superior+. The whole olfactory
  // pathway sits on the ventral surface of the frontal/temporal lobes, so
  // the sibling pages' view-from-above would bury it behind the brain -
  // this one looks up from anterior-right-BELOW instead, and sits closer
  // since the structures are small and clustered.
  const dist = EXTENT * 1.35;
  camera.position.set(dist * 0.5, dist * 0.6, -dist * 0.45);
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
  // centred on the ventral-frontal olfactory region, not the brain's centroid
  controls.target.set(0, EXTENT * 0.05, -EXTENT * 0.1);

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

  // ---- generated legend rows (root/skull + the AAL3 structures) ----
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
  // branches so a single raycaster can drive the hover leader-line + slice
  // plane below. Nodes on the shared trunk repeat across branches; the
  // raycaster just picks whichever hit sphere is nearest, which is fine.
  const HOVER_NODES = [];
  let hoveredNode = null;

  // labelKeys: which of orderedKeys get a label + marker + hit sphere. The
  // branches all share a long trunk, so each curve is drawn full-length
  // (the signal needs to travel the whole way) but only ONE of them labels
  // the trunk - otherwise every trunk node gets 3-4 sprites stacked on top
  // of itself.
  function buildPathway(orderedKeys, waypoints, labels, realKeys, color, labelKeys) {{
    const group = new THREE.Group();
    const realSet = new Set(realKeys);
    const labelSet = new Set(labelKeys || orderedKeys);

    const pts = orderedKeys.map((k) => new THREE.Vector3(...waypoints[k]));
    const curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.4);
    const tubeGeom = new THREE.TubeGeometry(curve, 200, EXTENT * 0.005, 10, false);
    const tubeMat = new THREE.MeshStandardMaterial({{
      color, emissive: color, emissiveIntensity: 0.4, roughness: 0.4, metalness: 0.1,
    }});
    group.add(new THREE.Mesh(tubeGeom, tubeMat));
    group.userData.curve = curve;

    const colorHex = "#" + color.toString(16).padStart(6, "0");

    // waypoints crowd together along the olfactory tract; stagger each
    // label along Y (anterior/posterior depth) only - never Z, so each
    // label stays at its node's true superior/inferior height and the
    // on-screen vertical order always matches real anatomy
    orderedKeys.forEach((key, i) => {{
      if (!labelSet.has(key)) return;
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
      const label = makeTextSprite(labels[key][LANG], colorHex, 52, EXTENT * 0.026, 998);
      // this pathway is compact (the whole trunk spans ~35mm), so labels
      // need a wider stagger than the auditory/visual pages to stay legible
      const step = EXTENT * 0.045;
      const yOff = (i % 2 === 0 ? -1 : 1) * step * (1 + Math.floor(i / 2) * 0.5);
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

  const OLF_WAYPOINTS = {olf_waypoints_json};
  const OLF_LABELS = {olf_labels_json};
  const OLF_REAL = {olf_real_json};
  const AMY_ORDER = {amy_order_json};
  const ENT_ORDER = {ent_order_json};
  const OFC_ORDER = {ofc_order_json};
  const THALAMIC_ORDER = {thalamic_order_json};

  // Group 1: the direct, thalamus-bypassing olfactory pathway - three
  // branches sharing the trunk (epithelium -> CN I -> bulb -> AON -> tract
  // -> trigone), then primary olfactory cortex, then out to amygdala,
  // entorhinal cortex and orbitofrontal cortex with NO thalamic relay.
  // Each branch curve runs the full length (so the signal sweeps the whole
  // pathway), but only the amygdala branch labels the shared trunk - the
  // other two label just their own endpoint.
  const olfactoryGroup = new THREE.Group();
  const amyPath = buildPathway(AMY_ORDER, OLF_WAYPOINTS, OLF_LABELS, OLF_REAL, 0x8fbf7f, AMY_ORDER);
  const entPath = buildPathway(ENT_ORDER, OLF_WAYPOINTS, OLF_LABELS, OLF_REAL, 0x8fbf7f, ["ENT"]);
  const ofcPath = buildPathway(OFC_ORDER, OLF_WAYPOINTS, OLF_LABELS, OLF_REAL, 0x8fbf7f, ["OFC"]);
  olfactoryGroup.add(amyPath);
  olfactoryGroup.add(entPath);
  olfactoryGroup.add(ofcPath);
  olfactoryGroup.userData.curves = [
    amyPath.userData.curve, entPath.userData.curve, ofcPath.userData.curve,
  ];
  olfactoryGroup.visible = document.getElementById("olfactoryToggle").checked;
  scene.add(olfactoryGroup);

  // Group 2: the parallel secondary route via mediodorsal thalamus, default
  // off - toggling it against group 1's direct olfactory-cortex-to-OFC line
  // is the whole point of the page.
  const thalamicGroup = buildPathway(THALAMIC_ORDER, OLF_WAYPOINTS, OLF_LABELS, OLF_REAL, 0xd094d9, ["MD"]);
  thalamicGroup.visible = document.getElementById("thalamicToggle").checked;

  document.getElementById("olfactoryToggle").addEventListener("change", (e) => {{
    olfactoryGroup.visible = e.target.checked;
  }});
  document.getElementById("thalamicToggle").addEventListener("change", (e) => {{
    thalamicGroup.visible = e.target.checked;
  }});

  // ---- animated "smelling something" signal: scattered particle streams
  // (one per group-1 branch) traveling epithelium -> cortex, departing
  // together and diverging after primary olfactory cortex, looping. The
  // thalamic route gets no animation, matching the sibling pages'
  // precedent that only the primary pathway animates. ----
  const SIGNAL_COLOR = 0xe8f5a8;
  const SIGNAL_COUNT = 22; // per curve
  const SIGNAL_DURATION = 2.6; // seconds per epithelium->cortex sweep
  const SIGNAL_TRAIL = 0.16; // fraction of the sweep the trailing spread covers
  const SIGNAL_JITTER = EXTENT * 0.01;

  const olfactoryCurves = olfactoryGroup.userData.curves;
  const signalGeom = new THREE.BufferGeometry();
  signalGeom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(SIGNAL_COUNT * olfactoryCurves.length * 3), 3));
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
    const show = signalEnabled && olfactoryGroup.visible;
    signalPoints.visible = show;
    if (!show) return;
    const cycle = (clock.getElapsedTime() % SIGNAL_DURATION) / SIGNAL_DURATION; // 0..1, repeats
    let idx = 0;
    olfactoryCurves.forEach((curve) => {{
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
        sliceLabel.textContent = node.text[LANG].replace(/^[①②③④⑤⑥⑦⑧⑨]+[abcd]?\\s*/, "");
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
        txtOlfactoryName: "olfactory_pathway_name", txtOlfactoryDesc: "olfactory_pathway_desc",
        txtThalamicName: "thalamic_pathway_name", txtThalamicDesc: "thalamic_pathway_desc",
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
        hoveredNode.text[LANG].replace(/^[①②③④⑤⑥⑦⑧⑨]+[abcd]?\\s*/, "");
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
