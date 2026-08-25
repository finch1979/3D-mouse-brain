"""
Build a self-contained 3D viewer for the human CEREBELLUM & MOTOR CONTROL
page: the cerebro-cerebellar LOOP, left M1 back to left M1.

Sibling to human_somatosensory.py (reference exemplar) on the shared
viewer_template.py renderer. The one teaching point of this page is that
the cerebellum is not a relay station on the way down - it is a LOOP:
cortex &rarr; pons &rarr; cerebellum &rarr; dentate &rarr; red nucleus/VL
&rarr; back to cortex. And it crosses TWICE (middle cerebellar peduncle at
the pontine level, superior cerebellar peduncle decussation in the
midbrain), which - together with the pyramidal decussation below - means
each cerebellar hemisphere steers the IPSILATERAL body via the
CONTRALATERAL cortex.

REAL DATA:
  - Whole-brain outline: nilearn's bundled MNI152 brain mask.
  - Cerebellum: Diedrichsen (2009) probabilistic cerebellar atlas,
    discrete MNI-space segmentation (DiedrichLab, atl-Anatom_space-
    MNI_dseg.nii). Labels 1-34 = the WHOLE cerebellar cortex; already
    cached by human_auditory.py, no download here.
  - Cortex stations: AAL3 via nilearn.datasets.fetch_atlas_aal(version=
    "3v2"), already cached by human_olfactory.py. Verified voxel values:
    Precentral_L 1 (M1), Thal_VL_L 127 (VL), Red_N_L 165.
  - Spinal tract: PAM50 label 6 = WM left ventral spinocerebellar tract,
    already cached by human_pain.py.

SCHEMATIC (no free segmentation exists): pontine nuclei waypoint, middle
cerebellar peduncle crossing, dentate nucleus inside the cerebellar white
matter, superior cerebellar peduncle + its midbrain decussation, loop
closure near M1, leg-proprioception input blob below the cord, and the
spinocerebellar chain's two cord-level nodes (those sit ON the real PAM50
tract mesh).

ACCURACY RULES - researched deliberately; do not "simplify" them back:
  - Double crossing: SCP decussation + pyramidal decussation &rArr; each
    cerebellar hemisphere controls the IPSILATERAL body via the
    contralateral cortex. State it exactly this way.
  - Dentate = output of the lateral (cerebrocerebellar) hemisphere; the
    interposed / vermis circuits are NOT drawn - say so.
  - Pontine nuclei = the biggest cortico-cerebellar relay (~20 million
    neurons); the MCP crossing happens at the pontine level.
  - VL thalamus is the loop's return station to M1 (and premotor).
  - The ventral spinocerebellar tract crosses in the cord and crosses BACK
    in the cerebellar peduncle - but keep this page's copy simple: it just
    "climbs the cord to the cerebellum".
  - The cerebellum mesh is cortical gray matter (Diedrichsen 2009); the
    deep nuclei (dentate ball) are schematic markers inside it.
  - Damage picture: ataxia - intention tremor, dysmetria (walkthrough).

Data licensing: Diedrichsen 2009 (DiedrichLab GitHub, open download); AAL3
(Rolls et al. 2020) license unspecified; PAM50 ships no license file.
Free educational use with citation.

Usage:
    py -3.13 -m human_atlas.build.human_cerebellum
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
CACHE_DIR = DATA_CACHE_DIR / "human_cerebellum"
AAL_CACHE_DIR = DATA_CACHE_DIR / "human_olfactory"   # AAL3 already lives here
PAM50_CACHE_DIR = DATA_CACHE_DIR / "human_pain"      # PAM50 already lives here
CBLM_ATLAS_PATH = (
    DATA_CACHE_DIR / "human_auditory" / "atl-Anatom_space-MNI_dseg.nii"
)
OUT_DIR = OUTPUTS_DIR / "cerebellum_system"
MESH_DIR = OUT_DIR / "mesh"
OUT_FILE = "human_cerebellum_system_3d.html"

ROOT_DOWNSAMPLE = 0.35
TRACT_THRESHOLD = 0.25  # PAM50 tract volumes are probabilistic; 0.5 gives slivers

# Diedrichsen (2009): labels 1-34 cover the entire cerebellar cortex
# (vermis + both hemispheres, lobules I-X).
CBLM_LABELS = list(range(1, 35))

# AAL3 voxel values (verified against the fetched atlas' .indices mapping)
AAL = {
    "M1_L":    [1],    # Precentral_L - motor cortex
    "VL_L":    [127],  # Thal_VL_L - the loop's return station
    "Red_N_L": [165],  # Red_N_L
}
# PAM50 atlas volume id (see atlas/info_label.txt in the human_pain cache)
PAM50_TRACTS = {
    "VSCT_L": 6,   # WM left ventral spinocerebellar tract
}

# Schematic waypoints: (x, y, z) in true MNI mm + marker radius mm.
SCHEMATIC = {
    "PontL":    {"pos": (8, -12, -32),   "r": 4},    # left basis pontis
    "MCPR":     {"pos": (16, -30, -38),  "r": 3},    # right MCP (after pons crossing)
    "DentR":    {"pos": (14, -52, -30),  "r": 4},    # right dentate nucleus
    "SCPr":     {"pos": (8, -40, -24),   "r": 2.5},  # right superior cerebellar peduncle
    "SCPdec":   {"pos": (0, -36, -20),   "r": 2},    # SCP decussation (midbrain)
    "LoopClose": {"pos": (-18, -2, 18),  "r": 2},    # back to left M1
    "SCinput":  {"pos": (-20, -30, -450), "r": 8},   # leg proprioception input layer
}

LABELS = {
    "M1_L":      {"en": "① Left motor cortex (M1)", "zh": "① 左運動皮質(M1)"},
    "PontL":     {"en": "② Pontine nuclei (left basis pontis)", "zh": "② 橋腦核(左基底橋腦)"},
    "MCPR":      {"en": "③ Middle cerebellar peduncle — CROSSES", "zh": "③ 中小腦腳—交叉"},
    "CBLM_R":    {"en": "④ Right cerebellar cortex", "zh": "④ 右小腦皮質"},
    "DentR":     {"en": "⑤ Right dentate nucleus — schematic", "zh": "⑤ 右齒狀核—示意"},
    "SCPr":      {"en": "⑥ Superior cerebellar peduncle", "zh": "⑥ 上小腦腳"},
    "SCPdec":    {"en": "⑦ SCP decussation — crosses AGAIN", "zh": "⑦ 上小腦腳交叉—再交叉"},
    "Red_N_L":   {"en": "⑧ Left red nucleus", "zh": "⑧ 左紅核"},
    "VL_L":      {"en": "⑨ Left VL thalamus", "zh": "⑨ 左視丘腹外側核(VL)"},
    "LoopClose": {"en": "⑩ Back to left M1 — loop closes", "zh": "⑩ 回到左 M1—迴路閉合"},
    "SCinput":   {"en": "⑪ Leg proprioception (contrast layer)", "zh": "⑪ 下肢本體感覺(對照)"},
    "VSCTa":     {"en": "⑫a Left ventral spinocerebellar tract — climbing", "zh": "⑫a 左腹側脊髓小腦束—上行"},
    "VSCTb":     {"en": "⑫b Left ventral spinocerebellar tract — mid-cord", "zh": "⑫b 左腹側脊髓小腦束—中段"},
    "CBLM_L":    {"en": "left cerebellar cortex — spinocerebellar input terminus", "zh": "左小腦皮質—脊髓小腦輸入終點"},
}

STRINGS = {
    "eyebrow": {"en": "Human &middot; MNI152 + PAM50 &middot; M1&rarr;pons&rarr;cerebellum&rarr;M1 loop",
                "zh": "人體 &middot; MNI152 + PAM50 &middot; M1&rarr;橋腦&rarr;小腦&rarr;M1 迴路"},
    "title_main": {"en": "Cerebellum &amp; motor control", "zh": "小腦與運動控制"},
    "title_suffix": {"en": '<span class="accent">The loop</span> — cortex&rarr;pons&rarr;cerebellum&rarr;back to cortex',
                     "zh": '<span class="accent">迴路</span>—皮質&rarr;橋腦&rarr;小腦&rarr;回到皮質'},
    "subtitle": {
        "en": "The cerebellum is not a relay on the way down — it is a <b>LOOP</b>: cortex &rarr; <b>pons</b> &rarr; cerebellum &rarr; <b>dentate</b> &rarr; red nucleus/<b>VL thalamus</b> &rarr; back to cortex. It crosses <b>TWICE</b> (middle cerebellar peduncle, then the superior cerebellar peduncle decussation in the midbrain), so the <b>right</b> cerebellum steers the <b>right</b> body. And it predicts and corrects movement in real time — timing, coordination, error correction. Solid meshes are real anatomy (<b>Diedrichsen 2009</b> cerebellar atlas, AAL3, PAM50); wireframe markers are schematic. Hover a node for its slice.",
        "zh": "小腦不是下行路徑上的中繼站—它是一個<b>迴路</b>:皮質 &rarr; <b>橋腦</b> &rarr; 小腦 &rarr; <b>齒狀核</b> &rarr; 紅核／<b>視丘 VL 核</b> &rarr; 回到皮質。它交叉<b>兩次</b>(中小腦腳、以及中腦的上小腦腳交叉),所以<b>右</b>側小腦掌管<b>右</b>側身體。它在即時預測並修正動作—時序、協調、誤差校正。實心網格是真實解剖(<b>Diedrichsen 2009</b> 小腦Atlas、AAL3、PAM50);線框標記為示意。滑鼠移到節點可看切面。",
    },
    "walk_title": {"en": "Pathway walkthrough &nbsp;1&ndash;3", "zh": "路徑逐段說明 &nbsp;1&ndash;3"},
    "walk_0": {
        "en": (
            '<span class="step-tag">1 &middot; The way in — cortico-pontine fibres and the MCP crossing</span>'
            "① The <b>left motor cortex (M1)</b> plans a movement &rarr; <b>cortico-pontine fibres</b> descend through the internal capsule and cerebral peduncle &rarr; ② they synapse in the <b>pontine nuclei</b> of the left basis pontis &mdash; the biggest cortico-cerebellar relay in the brain, roughly <b>20 million neurons</b>.<br />"
            "③ The pontine axons cross the midline <b>right there, at the pontine level</b>, and stream into the cerebellum as the <b>middle cerebellar peduncle</b> &mdash; ④ delivering the plan to the <b>right cerebellar cortex</b>."
        ),
        "zh": (
            '<span class="step-tag">1 &middot; 入口—皮質橋腦纖維與中小腦腳交叉</span>'
            "① <b>左側運動皮質(M1)</b>規劃動作 &rarr; <b>皮質橋腦纖維</b>經內囊與大腦腳下行 &rarr; ② 在<b>左基底橋腦</b>的<b>橋腦核</b>換元&mdash;這是腦中最大的皮質–小腦中繼站,約有 <b>2000 萬顆神經元</b>。<br />"
            "③ 橋腦核發出的軸突<b>就在橋腦的高度越過中線</b>,形成<b>中小腦腳</b>進入小腦 &mdash; ④ 把計畫送到<b>右側小腦皮質</b>。"
        ),
    },
    "walk_1": {
        "en": (
            '<span class="step-tag">2 &middot; The way out — dentate, SCP, and the second crossing</span>'
            "⑤ The cerebellar output of the lateral (cerebrocerebellar) hemisphere converges on the <b>right dentate nucleus</b> (the interposed/vermis circuits are not drawn here) &rarr; ⑥ out along the <b>superior cerebellar peduncle</b> &rarr; ⑦ and <span style=\"color:var(--accent)\">crosses the midline AGAIN</span> at the <b>SCP decussation</b> in the midbrain.<br />"
            "⑧ Now on the left: the fibres reach the <b>red nucleus</b> and ⑨ the <b>VL thalamus</b> &mdash; the loop&rsquo;s return station to M1 and premotor cortex &rarr; ⑩ back toward <b>left M1</b>. Loop closed.<br />"
            "<b>Double crossing:</b> the SCP decussation plus the pyramidal decussation below mean each cerebellar hemisphere controls the <b>IPSILATERAL body via the contralateral cortex</b> &mdash; that is why a right cerebellar lesion shows up as right-sided clumsiness."
        ),
        "zh": (
            '<span class="step-tag">2 &middot; 出口—齒狀核、上小腦腳、第二次交叉</span>'
            "⑤ 外側(大腦小腦)半球的輸出匯入<b>右側齒狀核</b>(栓狀/球狀核與蚓部迴路不在本頁繪製)&rarr; ⑥ 沿<b>上小腦腳</b>離開小腦 &rarr; ⑦ 在中腦的<b>上小腦腳交叉</b><span style=\"color:var(--accent)\">再次越過中線</span>。<br />"
            "⑧ 回到左側:纖維抵達<b>紅核</b>與 ⑨ <b>視丘 VL 核</b>&mdash;迴路回到 M1 與前運動皮質的轉運站 &rarr; ⑩ 回到<b>左側 M1</b>。迴路閉合。<br />"
            "<b>雙重交叉:</b>上小腦腳交叉加上下方的錐體交叉,代表<b>每個小腦半球經由對側皮質控制同側身體</b>&mdash;這就是為什麼右側小腦病變表現為右側動作笨拙。"
        ),
    },
    "walk_2": {
        "en": (
            '<span class="step-tag">3 &middot; What it computes — prediction vs feedback</span>'
            "The loop lets the cerebellum run <b>feedforward prediction</b>: it learns how the body will respond to a motor command and issues corrections <b>before</b> sensory feedback arrives &mdash; that is timing, coordination, and error correction in real time.<br />"
            "<b>Input layer (opt-in).</b> Toggle the spinocerebellar chain to watch leg proprioception climb the cord: the <b>ventral spinocerebellar tract</b> simply climbs the cord to the cerebellum, giving the loop an on-line report of what the body actually did.<br />"
            "<b>When it fails:</b> cerebellar damage produces <b>ataxia</b> &mdash; intention tremor, dysmetria (movements that overshoot or undershoot), slurred timing. The loop, broken."
        ),
        "zh": (
            '<span class="step-tag">3 &middot; 它在算什麼—預測 vs 回饋</span>'
            "這個迴路讓小腦做<b>前饋預測</b>:它學會身體會如何回應某個運動指令,並在感覺回傳<b>之前</b>就送出修正&mdash;即時的時序、協調與誤差校正。<br />"
            "<b>輸入層(自行開啟)。</b>打開脊髓小腦鏈,看下肢本體感覺沿脊髓上行:<b>腹側脊髓小腦束</b>沿脊髓爬向小腦,把「身體實際做了什麼」即時回報給迴路。<br />"
            "<b>當它壞掉:</b>小腦損傷造成<b>運動失調(ataxia)</b>&mdash;意向性顫抖、辨距不良(動作過衝或不足)、節奏含糊。迴路斷了。"
        ),
    },
    "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
    "structures_title": {"en": "Structures", "zh": "結構"},
    "pathways_title": {"en": "Pathways", "zh": "路徑"},
    "legend_note": {
        "en": "Wireframe sphere = schematic node, not a segmented structure. The cerebellum mesh is cortical gray matter (Diedrichsen 2009); the dentate nucleus marker is schematic inside it. Sources: DiedrichsenLab cerebellar atlas (open), AAL3 (license unspecified), PAM50 (no license file) &mdash; educational use with citation.",
        "zh": "線框球體＝示意節點,並非分割出的解剖構造。小腦網格是皮質灰質(Diedrichsen 2009);內部的齒狀核標記為示意。來源:DiedrichLab 小腦Atlas(開放)、AAL3(授權未明)、PAM50(無授權聲明)&mdash;教學使用並引用出處。",
    },
    "cpcc_name": {"en": "Cerebro-cerebellar loop", "zh": "皮質–小腦迴路"},
    "cpcc_desc": {"en": "M1 &rarr; pons &rarr; CEREBELLUM &rarr; dentate &rarr; CROSSES again &rarr; red nucleus/VL &rarr; M1",
                  "zh": "M1&rarr;橋腦&rarr;小腦&rarr;齒狀核&rarr;再交叉&rarr;紅核/VL&rarr;M1"},
    "spino_name": {"en": "Spinocerebellar input (contrast)", "zh": "脊髓小腦輸入(對照)"},
    "spino_desc": {"en": "leg proprioception climbs the cord to the cerebellum", "zh": "下肢本體感覺沿脊髓上行至小腦"},
    "signal_name": {"en": "Neural signal", "zh": "神經訊號"},
    "signal_desc": {"en": "animated pulse around the full loop, M1 &rarr; M1", "zh": "動畫脈衝繞行整個迴路,M1&rarr;M1"},
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
            "PAM50 cache not found - run `py -3.13 -m human_atlas.build.human_pain` first")
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

    if not CBLM_ATLAS_PATH.exists():
        raise RuntimeError(
            "Diedrichsen cerebellar atlas not cached - run "
            "`py -3.13 -m human_atlas.build.human_auditory` first")

    atlas_dir, template_dir = fetch_pam50()
    print(f"PAM50 at {template_dir.parent.name}")

    print("Loading MNI152 brain mask + AAL3 atlas + Diedrichsen cerebellar atlas ...")
    mni_img = datasets.load_mni152_brain_mask()
    aal = datasets.fetch_atlas_aal(version="3v2", data_dir=str(AAL_CACHE_DIR))
    aal_img = nib.load(aal.maps) if isinstance(aal.maps, str) else aal.maps
    aal_data = aal_img.get_fdata()
    cereb_img = nib.load(str(CBLM_ATLAS_PATH))
    cereb_data = cereb_img.get_fdata()

    structures = {
        "root": {
            "mask": mni_img.get_fdata().astype(bool), "affine": mni_img.affine,
            "downsample": ROOT_DOWNSAMPLE, "smooth": 5,
            "color": "CCCCCC", "name": "Whole-brain outline (MNI152)",
        },
        "CBLM": {
            "mask": np.isin(cereb_data, CBLM_LABELS), "affine": cereb_img.affine,
            "downsample": 1.0, "smooth": 8,
            "color": "6F8FE0", "name": "Cerebellar cortex (Diedrichsen 2009)",
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
        "root":    ("CCCCCC", "Whole-brain outline (MNI152)", "全腦輪廓(MNI152)", True, True),
        "CBLM":    ("6F8FE0", "Cerebellar cortex, whole (Diedrichsen 2009)", "小腦皮質全部(Diedrichsen 2009)", False, True),
        "M1_L":    ("9FB3C8", "Motor cortex / M1, left (AAL3 precentral)", "左運動皮質／M1(AAL3 中央前回)", False, True),
        "Red_N_L": ("E0705A", "Red nucleus, left (AAL3)", "左紅核(AAL3)", False, True),
        "VL_L":    ("E0A458", "VL thalamus, left (AAL3)", "左視丘腹外側核(AAL3)", False, True),
        "VSCT_L":  ("7FC99A", "Ventral spinocerebellar tract, left (PAM50)", "左腹側脊髓小腦束(PAM50)", False, False),
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
    order = ["root", "CBLM", "M1_L", "Red_N_L", "VL_L", "VSCT_L"]

    # extent over ALL meshes (brain + cord-level tract) so the camera frames the figure
    extent = max(float(np.ptp(tm.vertices, axis=0).max()) for tm in tms.values())

    # ---- waypoints: schematic + real-mesh anchors ----
    wp = {k: [v["pos"][0] * MM_TO_UM, v["pos"][1] * MM_TO_UM,
              v["pos"][2] * MM_TO_UM, v["r"] * MM_TO_UM]
          for k, v in SCHEMATIC.items()}
    wp["M1_L"] = hemi_anchor(tms["M1_L"], "left") + [0]
    wp["Red_N_L"] = hemi_anchor(tms["Red_N_L"], "left") + [0]
    wp["VL_L"] = hemi_anchor(tms["VL_L"], "left") + [0]
    wp["CBLM_R"] = hemi_anchor(tms["CBLM"], "right") + [0]
    wp["CBLM_L"] = hemi_anchor(tms["CBLM"], "left") + [0]
    wp["VSCTa"] = tract_anchor(tms["VSCT_L"], -200, "left") + [0]
    wp["VSCTb"] = tract_anchor(tms["VSCT_L"], -350, "left") + [0]
    real_keys = ["CBLM_R", "CBLM_L", "M1_L", "Red_N_L", "VL_L", "VSCTa", "VSCTb"]

    cpcc_order = ["M1_L", "PontL", "MCPR", "CBLM_R", "DentR",
                  "SCPr", "SCPdec", "Red_N_L", "VL_L", "LoopClose"]
    spino_order = ["SCinput", "VSCTa", "VSCTb", "CBLM_L"]
    pathways = [
        {"id": "cpcc", "name_key": "cpcc_name", "desc_key": "cpcc_desc",
         "color": "0x6f8fe0", "default_checked": True, "chains": [cpcc_order]},
        {"id": "spino", "name_key": "spino_name", "desc_key": "spino_desc",
         "color": "0x7fc99a", "default_checked": False, "chains": [spino_order]},
    ]

    legend_meta = [
        {"acr": a, "name_en": meta[a][1], "name_zh": meta[a][2],
         "color": meta[a][0], "outline": meta[a][3], "default_checked": meta[a][4]}
        for a in order
    ]

    html = render_viewer_html({
        "title": "小腦與運動控制",
        "accent": "6f8fe0",
        "extent": extent,
        "regions_js": regions_js,
        "order": order,
        "strings": STRINGS,
        "legend_meta": legend_meta,
        "pathways": pathways,
        "labels": LABELS,
        "waypoints": wp,
        "real": real_keys,
        "signal": {"pathway": "cpcc", "color": "0xffd48a", "duration": 3.0},
        "walk": [
            {"key": "walk_0", "color": "#6f8fe0"},
            {"key": "walk_1", "color": "#e0705a"},
            {"key": "walk_2", "color": "#7fc99a"},
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
