"""
Build a self-contained 3D viewer for the human SOMATOSENSORY pathway
(DCML - dorsal column-medial lemniscus), right fingertip to cortex.

Sibling to human_pain.py (which already runs a short DCML branch as a
contrast pathway); this page gives fine touch the full treatment the pain
page gave nociception. Built on the shared viewer_template.py renderer.

HEADLINE FACT - THE OPPOSITE CROSSING PATTERN FROM PAIN. Pain crosses in
the cord within 1-2 segments of entry (anterior white commissure); touch
and proprioception stay UNCROSSED for the entire length of the cord and
only cross in the MEDULLA (internal arcuate fibres). Same thalamus
(VPL), opposite sides of the cord - which is the whole mechanism of
Brown-Sequard hemisection: ipsilateral touch loss, contralateral pain
loss. The second teaching point is SOMATOTOPY: hand fibres run in the
fasciculus CUNEATUS (lateral column), leg fibres in the GRACILIS (medial),
and they stay segregated all the way to a somatotopic S1 - the hand lands
on the lateral convexity of the postcentral gyrus while the pain page's
foot landed on the medial paracentral lobule.

Story side: a right fingertip touches a surface. One side only, matching
the sibling pages. The schematic hand is drawn beside the cervical cord
for legibility and is explicitly labelled NOT TO SCALE - a true-scale arm
would push the hand ~600 mm below the cord entry (the pain page already
demonstrates true body scale; this page is about the crossing, not the
distance).

REAL DATA:
  - Brain: AAL3 via nilearn.datasets.fetch_atlas_aal(version="3v2").
    Verified label indices: Postcentral_L 61 (S1), Thal_VPL_L 129.
  - Whole-brain outline: nilearn's bundled MNI152 brain mask.
  - Spinal cord: PAM50 template, already cached by human_pain.py (same
    release zip). Tract labels used: 3 = right fasciculus cuneatus (the
    hand's ascending column), 1 = right fasciculus gracilis (the leg
    contrast layer).

SCHEMATIC (no free segmentation exists): fingertip mechanoreceptor,
median nerve, C7/T1 dorsal root ganglion, dorsal root entry zone, nucleus
cuneatus, internal arcuate fibres, medial lemniscus waypoints, the leg
receptor + L5 ganglion for the contrast layer, and the hand itself.

ACCURACY RULES - researched deliberately; do not "simplify" them back:
  - The DCML also carries proprioception and vibration, not just touch;
    say "fine touch and proprioception".
  - Nucleus CUNEATUS receives UPPER trunk/limb (cuneatus = lateral
    column); gracilis is LOWER body. Do not swap them.
  - The first synapse is in the medulla - there is NO synapse in the
    DRG or anywhere in the cord.
  - VPL is the body relay (VPM is face; the trigeminal touch route is a
    different page's story and is not drawn here).
  - The schematic hand placement is NOT anatomical scale - say so on the
    node label.

Data licensing: AAL3 (Rolls et al. 2020) license unspecified; PAM50 ships
no license file. Free educational use with citation.

Usage:
    python -m human_atlas.build.human_somatosensory
"""

import json
import zipfile

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
CACHE_DIR = DATA_CACHE_DIR / "human_somatosensory"
AAL_CACHE_DIR = DATA_CACHE_DIR / "human_olfactory"   # AAL3 already lives here
PAM50_CACHE_DIR = DATA_CACHE_DIR / "human_pain"      # PAM50 already lives here
OUT_DIR = OUTPUTS_DIR / "somatosensory_system"
MESH_DIR = OUT_DIR / "mesh"
OUT_FILE = "human_somatosensory_system_3d.html"

ROOT_DOWNSAMPLE = 0.35
CORD_DOWNSAMPLE = 0.5
TRACT_THRESHOLD = 0.25  # PAM50 tract volumes are probabilistic; 0.5 gives slivers

# AAL3 label indices (verified by inspecting the fetched atlas' .indices)
AAL = {
    "S1_L": [61],    # Postcentral_L - hand area sits on its lateral convexity
    "VPL_L": [129],  # Thal_VPL_L
}
# PAM50 atlas volume ids, per side (see atlas/info_label.txt)
PAM50_TRACTS = {
    "FC_R": 3,   # right fasciculus cuneatus - the hand's ascending column
    "FG_R": 1,   # right fasciculus gracilis - leg contrast layer
}

# Schematic waypoints: (x, y, z) in true MNI mm + marker radius mm.
# Right side (x>0) until the medulla crossing, then left, like the signal.
SCHEMATIC = {
    "Fingertip": {"pos": (63, -20, -128), "r": 3},
    "HAND":      {"pos": (55, -15, -135), "r": 12},   # not-to-scale hand blob
    "MedianN":   {"pos": (45, -22, -132), "r": 3},
    "DRG":       {"pos": (24, -32, -140), "r": 4},
    "DREZ":      {"pos": (14, -37, -143), "r": 2},
    "NucCuneat": {"pos": (7, -40, -62), "r": 3.5},
    "IntArc":    {"pos": (0, -37, -50), "r": 2.5},
    "MedLem":    {"pos": (-8, -30, -26), "r": 2.5},
    "LegRec":    {"pos": (24, -30, -520), "r": 9},
    "DRGls":     {"pos": (16, -35, -512), "r": 3},
    "NucGrac":   {"pos": (3, -41, -64), "r": 3},
}

LABELS = {
    "Fingertip": {"en": "① Mechanoreceptor (right fingertip)", "zh": "① 機械受器(右指尖)"},
    "HAND":      {"en": "right hand — schematic, not to scale", "zh": "右手—示意,非等比例"},
    "MedianN":   {"en": "② Median nerve", "zh": "② 正中神經"},
    "DRG":       {"en": "③ C7/T1 dorsal root ganglion — no synapse", "zh": "③ C7/T1 背根神經節—不換神經元"},
    "DREZ":      {"en": "④ Dorsal root entry (C6–T1)", "zh": "④ 背根進入脊髓(C6–T1)"},
    "FC_R":      {"en": "⑤ Right fasciculus cuneatus — UNCROSSED", "zh": "⑤ 右楔狀束—不交叉"},
    "FC0":       {"en": "fasciculus cuneatus (upper cervical)", "zh": "楔狀束(頸髓上段)"},
    "FC2":       {"en": "fasciculus cuneatus (C6–T1 entry)", "zh": "楔狀束(C6–T1 進入)"},
    "NucCuneat": {"en": "⑥ Nucleus cuneatus (medulla) — first synapse", "zh": "⑥ 楔狀核(延髓)—第一個突觸"},
    "IntArc":    {"en": "⑦ Internal arcuate fibres — CROSSES", "zh": "⑦ 內弓狀纖維—交叉"},
    "MedLem":    {"en": "⑧ Medial lemniscus", "zh": "⑧ 內側蹄系"},
    "VPL_L":     {"en": "⑨ Left VPL thalamus", "zh": "⑨ 左腹後外側核(視丘)"},
    "S1_L":      {"en": "⑩ Left S1 — hand area, lateral convexity", "zh": "⑩ 左 S1—手部區,外側凸面"},
    "LegRec":    {"en": "⑪ Leg afferent (contrast)", "zh": "⑪ 下肢傳入(對照)"},
    "DRGls":     {"en": "⑫ L5 dorsal root ganglion", "zh": "⑫ L5 背根神經節"},
    "FG_R":      {"en": "⑬ Right fasciculus gracilis — medial", "zh": "⑬ 右薄束—內側"},
    "FG0":       {"en": "fasciculus gracilis (sacral ascent)", "zh": "薄束(薦段上行)"},
    "FG2":       {"en": "fasciculus gracilis (cervical)", "zh": "薄束(頸段)"},
    "NucGrac":   {"en": "⑭ Nucleus gracilis — joins the same crossing", "zh": "⑭ 薄束核—匯入同一交叉"},
}

STRINGS = {
    "eyebrow": {"en": "Human &middot; MNI152 + PAM50 &middot; fingertip&rarr;medulla&rarr;S1",
                "zh": "人體 &middot; MNI152 + PAM50 &middot; 指尖&rarr;延髓&rarr;S1"},
    "title_main": {"en": "Somatosensory system", "zh": "體感覺系統"},
    "title_suffix": {"en": '<span class="accent">Fine touch</span> — the dorsal column&ndash;medial lemniscus pathway',
                     "zh": '<span class="accent">精細觸覺</span>—背柱內側蹄系路徑'},
    "subtitle": {
        "en": "A right fingertip touches a surface. Fine touch and proprioception take the <b>DCML</b>: up the <b>fasciculus cuneatus</b> without crossing a single synapse or the midline for the <b>entire spinal cord</b> — the first synapse only arrives in the medulla, and only there do the fibres cross. That is the exact opposite of the pain pathway (crosses immediately in the cord), and the two together are why a cord hemisection (<b>Brown-S&eacute;quard</b>) splits touch from pain to opposite sides. Solid meshes are real anatomy (AAL3 brain, PAM50 cord); wireframe markers are schematic. The hand is drawn beside the cervical cord for legibility — <b>not to scale</b> — the pain page shows the true-scale body.",
        "zh": "右手指尖碰觸表面。精細觸覺與本體感覺走<b>背柱內側蹄系(DCML)</b>:沿<b>楔狀束</b>上行,<b>整條脊髓</b>都不交叉、也不換神經元—第一個突觸要等到延髓才出現,也只有在延髓纖維才越過中線。這與痛覺路徑(進脊髓立刻交叉)完全相反;兩者合起來,正是脊髓半切(<b>Brown-S&eacute;quard 症候群</b>)會把觸覺與痛覺分到兩側的原因。實心網格是真實解剖(AAL3 腦部、PAM50 脊髓);線框標記為示意。為了清楚呈現,手畫在頸髓旁邊—<b>非等比例</b>;真實身體比例請看痛覺頁。",
    },
    "walk_title": {"en": "Pathway walkthrough &nbsp;1&ndash;3", "zh": "路徑逐段說明 &nbsp;1&ndash;3"},
    "walk_0": {
        "en": (
            '<span class="step-tag">1 &middot; First-order neuron — up the whole cord without crossing</span>'
            "① A mechanoreceptor in the right fingertip fires (Meissner corpuscles for light touch, Merkel discs for steady pressure, Pacinian for vibration) &rarr; ② the <b>median nerve</b> carries it up the arm &rarr; its cell body sits in the ③ <b>C7/T1 dorsal root ganglion</b> &mdash; a ganglion, not a relay, so <b>nothing synapses here</b> &rarr; ④ the axon enters the cord at the dorsal root and turns straight upward.<br />"
            "⑤ It ascends the <b>entire spinal cord</b> in the <b>right fasciculus cuneatus</b> &mdash; uncrossed, and without a single synapse. Hand and upper-limb fibres run in the <b>lateral</b> column (cuneatus); lower-body fibres run in the <b>medial</b> gracilis. That side-by-side ordering is real somatotopy, and it is preserved all the way to cortex."
        ),
        "zh": (
            '<span class="step-tag">1 &middot; 第一級神經元—整條脊髓上行、完全不交叉</span>'
            "① 右指尖的機械受器放電(輕觸是梅斯納氏小體、穩定壓力是梅克爾氏盤、振動是巴氏小體)&rarr; ② <b>正中神經</b>沿手臂上行 &rarr; 細胞本體在 ③ <b>C7/T1 背根神經節</b>&mdash;神經節不是中繼站,<b>這裡不換神經元</b> &rarr; ④ 軸突從背根進入脊髓後直接轉向上行。<br />"
            "⑤ 沿<b>整條脊髓</b>在<b>右側楔狀束</b>內上行&mdash;不交叉、也沒有任何突觸。手與上肢的纖維走<b>外側</b>的楔狀束;下半身的纖維走<b>內側</b>的薄束。這種並排排序是真實的體位定位,而且一路保留到皮質。"
        ),
    },
    "walk_1": {
        "en": (
            '<span class="step-tag">2 &middot; Second-order neuron — the crossing happens in the medulla</span>'
            "⑥ The first synapse in the entire pathway: the <b>nucleus cuneatus</b> in the <b>medulla</b> (the leg fibres synapse next door in the nucleus gracilis).<br />"
            'Second-order axons sweep forward as the ⑦ <b>internal arcuate fibres</b> and <span style="color:var(--accent)">cross the midline</span>, then stack up as the ⑧ <b>medial lemniscus</b> &mdash; so everything above the medulla already represents the <b>opposite</b> side of the body.<br />'
            "Compare the pain page: pain crossed <b>immediately</b>, in the cord. Touch crosses <b>late</b>, in the medulla. One lesion, two sensory losses on opposite sides &mdash; that is <b>Brown-S&eacute;quard syndrome</b>."
        ),
        "zh": (
            '<span class="step-tag">2 &middot; 第二級神經元—交叉發生在延髓</span>'
            "⑥ 整條路徑的第一個突觸:<b>延髓</b>的<b>楔狀核</b>(下肢的纖維則在旁邊的薄束核換元)。<br />"
            '第二級軸突向前掃過,形成 ⑦ <b>內弓狀纖維</b>並<span style="color:var(--accent)">越過中線</span>,接著疊成 ⑧ <b>內側蹄系</b>&mdash;所以延髓以上的每一站,代表的都是<b>對側</b>身體。<br />'
            "對照痛覺頁:痛覺<b>立刻</b>在脊髓內交叉;觸覺<b>很晚</b>才在延髓交叉。一處病灶、兩種感覺分別喪失在兩側&mdash;這就是 <b>Brown-S&eacute;quard 症候群</b>。"
        ),
    },
    "walk_2": {
        "en": (
            '<span class="step-tag">3 &middot; Third-order neuron — a body map on the postcentral gyrus</span>'
            "⑨ The medial lemniscus ends in the <b>left VPL</b> nucleus of the thalamus &mdash; the same relay the pain pathway used, one floor below the cortex.<br />"
            "⑩ Third-order fibres project to <b>left S1</b>, the postcentral gyrus. The hand&rsquo;s territory sits on the <b>lateral convexity</b> &mdash; compare the pain page, where the foot mapped to the <b>medial</b> paracentral lobule. Cortical territory follows use, not skin area: the hand and lips are enormous on the homunculus, the trunk nearly invisible.<br />"
            "<b>Contrast layer (opt-in).</b> Toggle the leg afferent to watch lower-body touch climb the <b>gracilis</b>, one slot medial to the hand fibres, reaching the same crossing and the same VPL &mdash; the map stays ordered, foot medial to hand, the whole way up."
        ),
        "zh": (
            '<span class="step-tag">3 &middot; 第三級神經元—中央後回上的身體地圖</span>'
            "⑨ 內側蹄系止於視丘的<b>左側 VPL 核</b>&mdash;與痛覺路徑相同的中繼站,就在皮質樓下一層。<br />"
            "⑩ 第三級纖維投射到<b>左側 S1</b>(中央後回)。手部的領域在<b>外側凸面</b>&mdash;對照痛覺頁:腳映射在<b>內側</b>的中央旁小葉。皮質領域跟著使用量走,而不是皮膚面積:小人圖上的手與嘴唇巨大,軀幹幾乎看不見。<br />"
            "<b>對照層(自行開啟)。</b>打開下肢傳入,看下半身觸覺沿<b>薄束</b>上行,在手部纖維內側一個位置,抵達同一個交叉、同一個 VPL&mdash;整路上地圖始終保持有序:腳在手的內側。"
        ),
    },
    "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
    "structures_title": {"en": "Structures", "zh": "結構"},
    "pathways_title": {"en": "Pathways", "zh": "路徑"},
    "legend_note": {"en": "Dashed swatch / wireframe sphere = schematic node, not a real segmented structure. Click &quot;Structures&quot; to collapse this panel.",
                    "zh": "虛線色塊／線框球體＝示意節點,並非真實分割出的解剖構造。點擊「結構」可收合此面板。"},
    "dcml_name": {"en": "Fine touch (DCML)", "zh": "精細觸覺(DCML)"},
    "dcml_desc": {"en": "fingertip &rarr; cuneatus &rarr; CROSSES in medulla &rarr; S1", "zh": "指尖&rarr;楔狀核&rarr;延髓交叉&rarr;S1"},
    "gracilis_name": {"en": "Leg contrast (gracilis)", "zh": "下肢對照(薄束)"},
    "gracilis_desc": {"en": "lower body, one slot medial — same crossing", "zh": "下半身,內側一個位置—同一交叉"},
    "signal_name": {"en": "Neural signal", "zh": "神經訊號"},
    "signal_desc": {"en": "animated touch pulse, fingertip &rarr; S1", "zh": "動畫觸覺訊號,指尖&rarr;S1"},
    "controls_title": {"en": "Controls", "zh": "操作說明"},
    "hint_controls": {"en": "<b>drag</b> orbit &nbsp; <b>scroll</b> zoom &nbsp; <b>right-drag</b> pan &nbsp; <b>hover</b> a node for a slice plane",
                      "zh": "<b>拖曳</b>旋轉 &nbsp; <b>滾輪</b>縮放 &nbsp; <b>右鍵拖曳</b>平移 &nbsp; <b>滑鼠移到節點</b>顯示切面"},
    "hint_units": {"en": "MNI152 + PAM50 space (mm, &times;1000 &rarr; &micro;m)", "zh": "MNI152 + PAM50 空間(mm,&times;1000 &rarr; &micro;m)"},
    "lang_button": {"en": "中文", "zh": "EN"},
    "anterior": {"en": "Anterior", "zh": "前"},
    "posterior": {"en": "Posterior", "zh": "後"},
    "superior": {"en": "Superior", "zh": "上"},
    "right_axis": {"en": "Right", "zh": "右"},
}


def fetch_pam50():
    """Reuse the PAM50 release already downloaded by human_pain.py."""
    if not PAM50_CACHE_DIR.exists():
        raise RuntimeError(
            "PAM50 cache not found - run `python -m human_atlas.build.human_pain` first")
    template = next(PAM50_CACHE_DIR.glob("**/template/PAM50_cord.nii.gz"), None)
    if template is None:
        # zip present but not extracted yet - extract it now
        zips = list(PAM50_CACHE_DIR.glob("PAM50-*.zip"))
        if not zips:
            raise RuntimeError("PAM50 zip not found in human_pain cache")
        with zipfile.ZipFile(zips[0]) as z:
            z.extractall(PAM50_CACHE_DIR)
        template = next(PAM50_CACHE_DIR.glob("**/template/PAM50_cord.nii.gz"), None)
    if template is None:
        raise RuntimeError("PAM50 extract failed - PAM50_cord.nii.gz not found")
    return template.parent.parent / "atlas", template.parent


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


def tract_anchor(tm, z_mm, side, window=8.0):
    """A point ON a full-length cord tract at a given spinal height (um)."""
    v = tm.vertices
    z = z_mm * MM_TO_UM
    w = window * MM_TO_UM
    sel = v[(np.abs(v[:, 2] - z) < w) & ((v[:, 0] > 0) if side == "right" else (v[:, 0] < 0))]
    if not len(sel):
        side_v = v[(v[:, 0] > 0) if side == "right" else (v[:, 0] < 0)]
        idx = np.argmin(np.abs(side_v[:, 2] - z))
        return side_v[idx].tolist()
    return sel.mean(axis=0).tolist()


def main():
    MESH_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    atlas_dir, template_dir = fetch_pam50()
    print(f"PAM50 at {template_dir.parent.name}")

    print("Loading MNI152 brain mask + AAL3 atlas ...")
    mni_img = datasets.load_mni152_brain_mask()
    aal = datasets.fetch_atlas_aal(version="3v2", data_dir=str(AAL_CACHE_DIR))
    aal_img = nib.load(aal.maps) if isinstance(aal.maps, str) else aal.maps
    aal_data = aal_img.get_fdata()

    structures = {
        "root": {
            "mask": mni_img.get_fdata().astype(bool), "affine": mni_img.affine,
            "downsample": ROOT_DOWNSAMPLE, "smooth": 5,
            "color": "CCCCCC", "name": "Whole-brain outline (MNI152)",
        },
        "cord": {
            "mask": nib.load(str(template_dir / "PAM50_cord.nii.gz")).get_fdata() > 0.5,
            "affine": nib.load(str(template_dir / "PAM50_cord.nii.gz")).affine,
            "downsample": CORD_DOWNSAMPLE, "smooth": 5,
            "color": "BBBBBB", "name": "Spinal cord outline (PAM50)",
        },
    }
    for acr, ids in AAL.items():
        structures[acr] = {
            "mask": np.isin(aal_data, ids), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 15, "color": "888888", "name": acr,
        }
    for acr, lid in PAM50_TRACTS.items():
        img = nib.load(str(atlas_dir / f"PAM50_atlas_{lid:02d}.nii.gz"))
        structures[acr] = {
            "mask": img.get_fdata() > TRACT_THRESHOLD, "affine": img.affine,
            "downsample": 1.0, "smooth": 8, "color": "888888", "name": acr,
        }

    # per-structure display metadata: (color, name_en, name_zh, outline?, default on?)
    meta = {
        "root":  ("CCCCCC", "Whole-brain outline (MNI152)", "全腦輪廓(MNI152)", True, True),
        "cord":  ("BBBBBB", "Spinal cord outline (PAM50)", "脊髓輪廓(PAM50)", True, True),
        "FC_R":  ("C9A8FF", "Right fasciculus cuneatus (PAM50)", "右楔狀束(PAM50)", False, True),
        "VPL_L": ("E0A458", "VPL thalamus, left (AAL3)", "左腹後外側核(AAL3)", False, True),
        "S1_L":  ("D0A0A0", "Postcentral gyrus / S1, left (AAL3)", "左中央後迴／S1(AAL3)", False, True),
        "FG_R":  ("8A6FC0", "Right fasciculus gracilis (PAM50)", "右薄束(PAM50)", False, False),
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
    order = ["root", "cord"] + [a for a in meta if a not in ("root", "cord")]

    # extent over ALL meshes (brain + cord) so the camera frames the figure
    extent = max(float(np.ptp(tm.vertices, axis=0).max()) for tm in tms.values())

    # ---- waypoints: schematic + real-mesh anchors ----
    wp = {k: [v["pos"][0] * MM_TO_UM, v["pos"][1] * MM_TO_UM,
              v["pos"][2] * MM_TO_UM, v["r"] * MM_TO_UM]
          for k, v in SCHEMATIC.items()}
    fc_levels, fg_levels = [], []
    for i, z in enumerate([-90, -115, -140]):
        k = "FC_R" if i == 1 else f"FC{i}"
        wp[k] = tract_anchor(tms["FC_R"], z, "right") + [0]
        fc_levels.append(k)
    for i, z in enumerate([-480, -300, -120]):
        k = "FG_R" if i == 1 else f"FG{i}"
        wp[k] = tract_anchor(tms["FG_R"], z, "right") + [0]
        fg_levels.append(k)
    wp["VPL_L"] = hemi_anchor(tms["VPL_L"], "left") + [0]
    wp["S1_L"] = hemi_anchor(tms["S1_L"], "left") + [0]

    touch_order = ["Fingertip", "MedianN", "DRG", "DREZ"] + fc_levels + \
        ["NucCuneat", "IntArc", "MedLem", "VPL_L", "S1_L"]
    leg_order = ["LegRec", "DRGls"] + fg_levels + ["NucGrac"]
    real_keys = fc_levels + fg_levels + ["VPL_L", "S1_L"]

    pathways = [
        {"id": "dcml", "name_key": "dcml_name", "desc_key": "dcml_desc",
         "color": "0xc9a8ff", "default_checked": True, "chains": [touch_order]},
        {"id": "gracilis", "name_key": "gracilis_name", "desc_key": "gracilis_desc",
         "color": "0x8a6fc0", "default_checked": False, "chains": [leg_order]},
    ]

    legend_meta = [
        {"acr": a, "name_en": meta[a][1], "name_zh": meta[a][2],
         "color": meta[a][0], "outline": meta[a][3], "default_checked": meta[a][4]}
        for a in order
    ]

    html = render_viewer_html({
        "title": "體感覺系統",
        "accent": "c9a8ff",
        "extent": extent,
        "regions_js": regions_js,
        "order": order,
        "strings": STRINGS,
        "legend_meta": legend_meta,
        "pathways": pathways,
        "labels": LABELS,
        "waypoints": wp,
        "real": real_keys,
        "signal": {"pathway": "dcml", "color": "0xffd48a", "duration": 2.4},
        "walk": [
            {"key": "walk_0", "color": "#c9a8ff"},
            {"key": "walk_1", "color": "#e0a458"},
            {"key": "walk_2", "color": "#6fb0e0"},
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
