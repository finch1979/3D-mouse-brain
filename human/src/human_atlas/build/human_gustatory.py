"""
Build a self-contained 3D viewer for the human GUSTATORY system
(taste), tongue taste buds to the primary gustatory cortex.

Sibling to human_somatosensory.py (the reference exemplar for this
renderer) and the rest of the six-system family; built on the shared
viewer_template.py renderer.

HEADLINE FACT - TASTE BARELY CROSSES. Touch, pain, hearing and vision
all cross the midline somewhere (cord, medulla, brainstem, chiasm);
taste is the odd one out: from tongue to cortex the signal stays almost
entirely IPSILATERAL. Three cranial nerves split the tongue by region -
facial (CN VII) for the anterior 2/3 via the chorda tympani,
glossopharyngeal (CN IX) for the posterior 1/3, vagus (CN X) for the
epiglottis - and all three converge on the ROSTRAL (gustatory) part of
the solitary nucleus, climb the central tegmental tract to the
parvocellular VPM (VPMpc, the most medial thalamic nucleus), and end in
the FRONTAL OPERCULUM + ANTERIOR INSULA, together the primary gustatory
cortex. The opt-in second layer shows FLAVOR: smell arriving from the
olfactory cortex to meet taste in the orbitofrontal cortex.

Story side: right side only (x>0 throughout), matching the ipsilateral
rule being taught. Taste buds, peripheral nerve fibres and brainstem
waypoints have no downloadable segmentation, so they are schematic
wireframe markers; the four brain regions are real AAL3 meshes.

REAL DATA:
  - Brain: AAL3 via nilearn.datasets.fetch_atlas_aal(version="3v2").
    Verified label indices (checked against the fetched atlas'
    .indices): Insula_R 34, Frontal_Inf_Oper_R 8, OFClat_R 32,
    Olfactory_R 18. NOTE: 17 is Olfactory_L - easy to mis-grab when
    picking the right-side index.
  - Whole-brain outline: nilearn's bundled MNI152 brain mask.

SCHEMATIC (no free segmentation exists): tongue tip/posterior taste
bud fields, epiglottis, the three cranial nerve gustatory fibre
waypoints, rostral solitary nucleus, central tegmental tract and VPMpc.

ACCURACY RULES - researched deliberately; do not "simplify" them back:
  - Taste is LARGELY ipsilateral end to end - say "barely crosses",
    never "never crosses" (a small contralateral component exists).
  - Only the ROSTRAL solitary nucleus is gustatory; its caudal part is
    visceral-autonomic (the autonomic page's territory).
  - VPMpc is the MOST MEDIAL thalamic nucleus. Do not call it VPL
    (body) or plain VPM (face/touch).
  - Primary gustatory cortex = insula + frontal operculum. It is NOT
    the postcentral "tongue" somatosensory area (that map is touch).
  - Flavor = taste + smell (+ texture/temperature) integrated in the
    orbitofrontal cortex - hence the opt-in olfactory->OFC layer.

Data licensing: AAL3 (Rolls et al. 2020) license unspecified; the
MNI152 mask ships with nilearn. Free educational use with citation.

Usage:
    python -m human_atlas.build.human_gustatory
"""

import json

import nibabel as nib
import numpy as np
import trimesh
from nilearn import datasets
from scipy.ndimage import zoom
from skimage import measure
from trimesh import smoothing

from human_atlas.common.paths import DATA_CACHE_DIR, OUTPUTS_DIR
from human_atlas.render.bake_meshes import mesh_to_region_js
from human_atlas.render.viewer_template import render_viewer_html

MM_TO_UM = 1000.0
AAL_CACHE_DIR = DATA_CACHE_DIR / "human_olfactory"   # AAL3 already lives here
OUT_DIR = OUTPUTS_DIR / "gustatory_system"
MESH_DIR = OUT_DIR / "mesh"
OUT_FILE = "human_gustatory_system_3d.html"

ROOT_DOWNSAMPLE = 0.35

# AAL3 label indices (verified by inspecting the fetched atlas' .indices;
# Olfactory_R is 18 - 17 is Olfactory_L)
AAL = {
    "INS_R": [34],   # Insula_R - anterior insula, primary taste cortex
    "FOP_R": [8],    # Frontal_Inf_Oper_R - frontal operculum, primary taste cortex
    "OLFR_R": [18],  # Olfactory_R - opt-in "flavor" layer
    "OFC_R": [32],   # OFClat_R - orbitofrontal, flavor integration, opt-in layer
}

# Schematic waypoints: (x, y, z) in true MNI mm + marker radius mm.
# RIGHT side only (x>0) - taste stays ipsilateral, like the story says.
SCHEMATIC = {
    "TongueAnt": {"pos": (22, 38, -52), "r": 4},     # anterior 2/3 tongue tip taste buds
    "TonguePost": {"pos": (8, 30, -46), "r": 3.5},   # posterior 1/3
    "Epi":       {"pos": (2, 22, -42), "r": 2.5},    # epiglottis
    "CN7":       {"pos": (13, -26, -40), "r": 2.5},  # facial nerve gustatory fibres
    "CN9":       {"pos": (10, -30, -46), "r": 2.5},  # glossopharyngeal
    "CN10":      {"pos": (8, -32, -50), "r": 2},     # vagus
    "Sol":       {"pos": (7, -34, -48), "r": 3},     # rostral solitary nucleus - the three CNs converge here
    "CTT":       {"pos": (5, -27, -28), "r": 2},     # central tegmental tract
    "VPMpc":     {"pos": (12, -20, -8), "r": 3.5},   # parvocellular VPM
}

LABELS = {
    "TongueAnt": {"en": "① Taste buds — anterior 2/3 tongue", "zh": "① 味蕾(舌前 2/3)"},
    "CN7":       {"en": "② Facial nerve taste fibres (CN VII)", "zh": "② 顏面神經味覺纖維(CN VII)"},
    "Sol":       {"en": "③ Solitary nucleus — gustatory (rostral) part", "zh": "③ 孤束核—味覺部"},
    "CTT":       {"en": "④ Central tegmental tract", "zh": "④ 中央蓋膜束"},
    "VPMpc":     {"en": "⑤ VPMpc — most medial thalamic nucleus", "zh": "⑤ 腹後內側核內側小細胞部(VPMpc)"},
    "FOP_R":     {"en": "⑥ Frontal operculum", "zh": "⑥ 額蓋部"},
    "INS_R":     {"en": "⑦ Insula — primary gustatory cortex", "zh": "⑦ 島葉—初級味覺皮質"},
    "TonguePost": {"en": "⑧ Taste buds — posterior 1/3", "zh": "⑧ 舌後 1/3 味蕾"},
    "CN9":       {"en": "⑨ Glossopharyngeal nerve (CN IX)", "zh": "⑨ 舌咽神經(CN IX)"},
    "Epi":       {"en": "⑩ Epiglottis", "zh": "⑩ 會厭"},
    "CN10":      {"en": "⑪ Vagus nerve (CN X)", "zh": "⑪ 迷走神經(CN X)"},
    "OLFR_R":    {"en": "Olfactory cortex", "zh": "嗅皮質"},
    "OFC_R":     {"en": "Orbitofrontal cortex — flavor integration", "zh": "眶額葉皮質—風味整合"},
}

STRINGS = {
    "eyebrow": {"en": "Human &middot; MNI152 &middot; tongue&rarr;solitary nucleus&rarr;insula",
                "zh": "人體 &middot; MNI152 &middot; 舌&rarr;孤束核&rarr;島葉"},
    "title_main": {"en": "Gustatory system", "zh": "味覺系統"},
    "title_suffix": {"en": '<span class="accent">Taste</span> &mdash; the sense that barely crosses the midline',
                     "zh": '<span class="accent">味覺</span>&mdash;幾乎不越過中線的感官'},
    "subtitle": {
        "en": "A sip of coffee fires three nerves at once: taste buds on the <b>anterior 2/3</b> of the tongue ride the <b>facial nerve (CN VII)</b>, the <b>posterior 1/3</b> rides the <b>glossopharyngeal (CN IX)</b>, and the <b>epiglottis</b> reports through the <b>vagus (CN X)</b>. All three converge on the <b>rostral (gustatory) solitary nucleus</b>, climb the <b>central tegmental tract</b> to the most medial thalamic relay (<b>VPMpc</b>), and end in the <b>insula + frontal operculum</b> &mdash; the primary gustatory cortex. Alone among the senses on this site, taste runs <b>ipsilateral</b> the whole way &mdash; it barely crosses the midline at all. Enable the <b>flavor</b> layer to watch smell join taste in the orbitofrontal cortex. Solid meshes are real anatomy (AAL3); wireframe markers are schematic. <b>Hover</b> a node for a slice plane.",
        "zh": "喝一口咖啡,三條神經同時放電:舌<b>前 2/3</b> 味蕾走<b>顏面神經(CN VII)</b>,<b>後 1/3</b> 走<b>舌咽神經(CN IX)</b>,<b>會厭</b>則由<b>迷走神經(CN X)</b>回報。三者會合於<b>孤束核吻側(味覺部)</b>,沿<b>中央蓋膜束</b>上行至視丘最內側的中繼站(<b>VPMpc</b>),終點在<b>島葉＋額蓋部</b>&mdash;初級味覺皮質。與本站其他感官都不同,味覺全程<b>同側</b>&mdash;它幾乎不越過中線。開啟<b>風味</b>圖層,看嗅覺在眶額葉皮質與味覺會合。實心網格是真實解剖(AAL3);線框標記為示意。<b>滑鼠移到節點</b>可顯示切面。",
    },
    "walk_title": {"en": "Pathway walkthrough &nbsp;1&ndash;3", "zh": "路徑逐段說明 &nbsp;1&ndash;3"},
    "walk_0": {
        "en": (
            '<span class="step-tag">1 &middot; Periphery — one tongue, three cranial nerves</span>'
            "① Taste buds on the <b>anterior two-thirds</b> of the tongue send their fibres via the chorda tympani into ② the <b>facial nerve (CN VII)</b> &rarr; ⑧ taste buds on the <b>posterior one-third</b> feed ⑨ the <b>glossopharyngeal nerve (CN IX)</b> &rarr; and ⑩ taste buds on the <b>epiglottis</b> ride ⑪ the <b>vagus nerve (CN X)</b>.<br />"
            "Three nerves, one map. Each carries taste from its own strip of tongue; all three cell bodies sit in ganglia just outside the brainstem, and <b>nothing synapses until they reach it</b>."
        ),
        "zh": (
            '<span class="step-tag">1 &middot; 周邊—一條舌頭,三條腦神經</span>'
            "① 舌<b>前三分之二</b>的味蕾經鼓索匯入 ② <b>顏面神經(CN VII)</b> &rarr; ⑧ 舌<b>後三分之一</b>的味蕾交給 ⑨ <b>舌咽神經(CN IX)</b> &rarr; 而 ⑩ <b>會厭</b>上的味蕾則搭上 ⑪ <b>迷走神經(CN X)</b>。<br />"
            "三條神經、同一張地圖:各自攜帶舌頭不同區域的味覺;三者的細胞本體都在腦幹外的神經節,<b>進入腦幹之前不換任何一個突觸</b>。"
        ),
    },
    "walk_1": {
        "en": (
            '<span class="step-tag">2 &middot; Brainstem relay — the ipsilateral rule</span>'
            "② All three nerves deliver taste to ③ the <b>rostral (gustatory) part of the solitary nucleus</b> in the medulla &mdash; the first synapse of the whole pathway. (Its caudal part handles visceral-autonomic traffic instead &mdash; that is the autonomic page&rsquo;s territory.)<br />"
            "④ Second-order fibres climb the <b>central tegmental tract</b> to ⑤ <b>VPMpc</b>, the most medial sliver of the thalamus.<br />"
            '<span style="color:var(--accent)">Notice what does not happen:</span> unlike touch, pain, hearing or vision, the signal <b>stays on the right side all the way up</b> &mdash; taste is almost entirely ipsilateral, barely crossing the midline anywhere.'
        ),
        "zh": (
            '<span class="step-tag">2 &middot; 腦幹中繼—同側規則</span>'
            "② 三條神經把味覺送進延髓 ③ <b>孤束核吻側(味覺部)</b>&mdash;整條路徑的第一個突觸。(尾側部處理的是內臟自主神經訊息&mdash;那是自主神經頁的領域。)<br />"
            "④ 第二級纖維沿<b>中央蓋膜束</b>上行,抵達視丘最內側的 ⑤ <b>VPMpc</b>。<br />"
            '<span style="color:var(--accent)">注意什麼事沒有發生:</span>與觸覺、痛覺、聽覺、視覺不同,訊號<b>一路上始終留在右側</b>&mdash;味覺幾乎完全同側,在任何地方都極少越過中線。'
        ),
    },
    "walk_2": {
        "en": (
            '<span class="step-tag">3 &middot; Cortex — taste becomes flavor</span>'
            "⑤ VPMpc projects to ⑥ the <b>frontal operculum</b> and ⑦ the <b>anterior insula</b> &mdash; together the <b>primary gustatory cortex</b> (not the postcentral &ldquo;tongue&rdquo; area of S1 &mdash; that map is touch, not taste).<br />"
            "<b>Flavor layer (opt-in).</b> Switch it on to see smell arrive from the <b>olfactory cortex</b> and meet taste in the <b>orbitofrontal cortex</b> &mdash; where taste + smell (+ texture and temperature) fuse into <b>flavor</b>. That fusion is why a blocked nose flattens the taste of dinner."
        ),
        "zh": (
            '<span class="step-tag">3 &middot; 皮質—味覺成為風味</span>'
            "⑤ VPMpc 投射到 ⑥ <b>額蓋部</b>與 ⑦ <b>前島葉</b>&mdash;合稱<b>初級味覺皮質</b>(不是中央後回的「舌區」&mdash;那張地圖是觸覺,不是味覺)。<br />"
            "<b>風味層(自行開啟)。</b>開啟後可看到嗅覺訊號從<b>嗅皮質</b>抵達,在<b>眶額葉皮質</b>與味覺相遇&mdash;味覺＋嗅覺(再加上口感與溫度)在此融合成<b>風味</b>。這也是為什麼鼻塞時,晚餐食之無味。"
        ),
    },
    "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
    "structures_title": {"en": "Structures", "zh": "結構"},
    "pathways_title": {"en": "Pathways", "zh": "路徑"},
    "legend_note": {"en": "Dashed swatch / wireframe sphere = schematic node, not a real segmented structure. Click &quot;Structures&quot; to collapse this panel.",
                    "zh": "虛線色塊／線框球體＝示意節點,並非真實分割出的解剖構造。點擊「結構」可收合此面板。"},
    "gustatory_name": {"en": "Gustatory (taste)", "zh": "味覺路徑"},
    "gustatory_desc": {"en": "tongue &rarr; solitary nucleus &rarr; VPMpc &rarr; insula &mdash; ipsilateral",
                       "zh": "舌&rarr;孤束核&rarr;VPMpc&rarr;島葉&mdash;同側"},
    "flavor_name": {"en": "Flavor (taste + smell)", "zh": "風味(味覺＋嗅覺)"},
    "flavor_desc": {"en": "smell joins taste in the orbitofrontal cortex",
                    "zh": "嗅覺在眶額葉皮質與味覺會合"},
    "signal_name": {"en": "Neural signal", "zh": "神經訊號"},
    "signal_desc": {"en": "animated taste pulse, tongue &rarr; insula", "zh": "動畫味覺訊號,舌&rarr;島葉"},
    "controls_title": {"en": "Controls", "zh": "操作說明"},
    "hint_controls": {"en": "<b>drag</b> orbit &nbsp; <b>scroll</b> zoom &nbsp; <b>right-drag</b> pan &nbsp; <b>hover</b> a node for a slice plane",
                      "zh": "<b>拖曳</b>旋轉 &nbsp; <b>滾輪</b>縮放 &nbsp; <b>右鍵拖曳</b>平移 &nbsp; <b>滑鼠移到節點</b>顯示切面"},
    "hint_units": {"en": "MNI152 space (mm, &times;1000 &rarr; &micro;m)",
                   "zh": "MNI152 空間(mm,&times;1000 &rarr; &micro;m)"},
    "lang_button": {"en": "中文", "zh": "EN"},
    "anterior": {"en": "Anterior", "zh": "前"},
    "posterior": {"en": "Posterior", "zh": "後"},
    "superior": {"en": "Superior", "zh": "上"},
    "right_axis": {"en": "Right", "zh": "右"},
}


def fetch_aal():
    """Reuse the AAL3v2 release already downloaded by human_olfactory.py."""
    return datasets.fetch_atlas_aal(version="3v2", data_dir=str(AAL_CACHE_DIR))


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


def hemi_anchor(tm, side):
    """Mean vertex of one hemisphere's blob (um)."""
    v = tm.vertices
    sel = v[v[:, 0] > 0] if side == "right" else v[v[:, 0] < 0]
    return (sel.mean(axis=0) if len(sel) else tm.centroid).tolist()


def main():
    MESH_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading MNI152 brain mask + AAL3 atlas ...")
    mni_img = datasets.load_mni152_brain_mask()
    aal = fetch_aal()
    aal_img = nib.load(aal.maps) if isinstance(aal.maps, str) else aal.maps
    aal_data = aal_img.get_fdata()

    structures = {
        "root": {
            "mask": mni_img.get_fdata().astype(bool), "affine": mni_img.affine,
            "downsample": ROOT_DOWNSAMPLE, "smooth": 5,
            "color": "CCCCCC", "name": "Whole-brain outline (MNI152)",
        },
    }
    for acr, ids in AAL.items():
        structures[acr] = {
            "mask": np.isin(aal_data, ids), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 15, "color": "888888", "name": acr,
        }

    # per-structure display metadata: (color, name_en, name_zh, outline?, default on?)
    meta = {
        "root":   ("CCCCCC", "Whole-brain outline (MNI152)", "全腦輪廓(MNI152)", True, True),
        "INS_R":  ("E08FB0", "Anterior insula, right - primary taste cortex (AAL3)", "右前島葉—初級味覺皮質(AAL3)", False, True),
        "FOP_R":  ("E0A0C0", "Frontal operculum, right (AAL3)", "右額蓋部(AAL3)", False, True),
        "OLFR_R": ("8FBF7F", "Olfactory cortex, right (AAL3) - flavor layer", "右嗅皮質(AAL3)—風味層", False, False),
        "OFC_R":  ("8FBF7F", "Orbitofrontal cortex (OFClat), right (AAL3) - flavor layer", "右眶額葉皮質(OFClat)(AAL3)—風味層", False, False),
    }

    regions_js_parts, manifest, tms = [], {}, {}
    for acr, s in structures.items():
        voxels = int(s["mask"].sum())
        if voxels == 0:
            raise RuntimeError(f"{acr} mask is empty - wrong label index or threshold")
        color = meta[acr][0]
        print(f"  meshing {acr} ({voxels} voxels) ...")
        tm = mask_to_mesh(s["mask"], s["affine"], downsample=s["downsample"],
                          smooth_iterations=s["smooth"])
        tm.export(MESH_DIR / f"{acr}.obj")
        tms[acr] = tm
        manifest[acr] = {
            "name": meta[acr][1], "color": color,
            "mesh_path": f"mesh/{acr}.obj", "vertex_count": len(tm.vertices),
        }
        regions_js_parts.append(mesh_to_region_js(acr, tm, color))

    (MESH_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    regions_js = "{" + ",".join(regions_js_parts) + "}"
    order = ["root"] + list(AAL.keys())

    # extent over ALL meshes so the camera frames the figure
    extent = max(float(np.ptp(tm.vertices, axis=0).max()) for tm in tms.values())

    # ---- waypoints: schematic + real-mesh anchors ----
    wp = {k: [v["pos"][0] * MM_TO_UM, v["pos"][1] * MM_TO_UM,
              v["pos"][2] * MM_TO_UM, v["r"] * MM_TO_UM]
          for k, v in SCHEMATIC.items()}
    for acr in ("FOP_R", "INS_R", "OLFR_R", "OFC_R"):
        wp[acr] = hemi_anchor(tms[acr], "right") + [0]

    gust_order = ["TongueAnt", "CN7", "Sol", "CTT", "VPMpc", "FOP_R", "INS_R"]
    pathways = [
        {"id": "gustatory", "name_key": "gustatory_name", "desc_key": "gustatory_desc",
         "color": "0xe08fb0", "default_checked": True,
         "chains": [gust_order,
                    ["TonguePost", "CN9", "Sol"],
                    ["Epi", "CN10", "Sol"]]},
        {"id": "flavor", "name_key": "flavor_name", "desc_key": "flavor_desc",
         "color": "0x8fbf7f", "default_checked": False,
         "chains": [["OLFR_R", "OFC_R"]]},
    ]

    legend_meta = [
        {"acr": a, "name_en": meta[a][1], "name_zh": meta[a][2],
         "color": meta[a][0], "outline": meta[a][3], "default_checked": meta[a][4]}
        for a in order
    ]

    html = render_viewer_html({
        "title": "味覺系統",
        "accent": "e08fb0",
        "extent": extent,
        "regions_js": regions_js,
        "order": order,
        "strings": STRINGS,
        "legend_meta": legend_meta,
        "pathways": pathways,
        "labels": LABELS,
        "waypoints": wp,
        "real": ["FOP_R", "INS_R", "OLFR_R", "OFC_R"],
        "signal": {"pathway": "gustatory", "color": "0xffd48a", "duration": 2.4},
        "walk": [
            {"key": "walk_0", "color": "#e08fb0"},
            {"key": "walk_1", "color": "#e0a458"},
            {"key": "walk_2", "color": "#8fbf7f"},
        ],
    })

    out_path = OUT_DIR / OUT_FILE
    out_path.write_text(html, encoding="utf-8")
    # without this the bare Cloudflare Pages domain 404s (no index.html)
    (OUT_DIR / "index.html").write_text(
        f'<meta http-equiv="refresh" content="0; url={OUT_FILE}">\n'
        f'<a href="{OUT_FILE}">{OUT_FILE}</a>\n',
        encoding="utf-8",
    )
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
