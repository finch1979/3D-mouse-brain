"""
Build a self-contained 3D viewer for the human AUTONOMIC nervous system:
the hypothalamus as integrator, its sympathetic (thoracolumbar) and
parasympathetic (craniosacral) arms, and the vagal afferent return.

Sibling to human_somatosensory.py (the verified reference user of the
shared viewer_template.py renderer); this page gives autonomic outflow
the same treatment. Story: ONE midline hypothalamus commands TWO arms.
SYMPATHETIC (thoracolumbar): hypothalamus -> down the cord ->
intermediate zone / IML column (T1-L2, PAM50 intermediate zone, REAL)
-> sympathetic chain ganglia (schematic beads alongside the cord) ->
heart (accelerate) + gut (inhibit). PARASYMPATHETIC (craniosacral):
dorsal motor nucleus of vagus (medulla, schematic) -> vagus nerve
(CN X, schematic tube) -> heart (slow) + gut (activate). HEADLINE FACT:
about 80% of vagus fibres are SENSORY - organs report upward to the
nucleus tractus solitarii far more than the brain commands downward,
so the afferents get their own return chain. Sacral (S2-S4) outflow
ships as an opt-in layer.

REAL DATA:
  - Brain outline: nilearn.datasets.load_mni152_brain_mask().
  - Spinal cord: PAM50 template, already cached by human_pain.py (same
    release zip).
  - Intermediate zone: PAM50 atlas labels 33 (GM right) / 32 (GM left),
    threshold 0.25 (probabilistic volumes; 0.5 gives slivers). The
    RIGHT side is meshed (IML_R) and anchors all real waypoints,
    including the sacral-level one near the cord taper.

SCHEMATIC (no free segmentation exists): hypothalamus (bilateral pair
simplified to one midline blob), dorsal motor nucleus of vagus, nucleus
tractus solitarii, sympathetic chain beads, heart, stomach & gut, vagus
nerve tube + separate afferent-return waypoints, sacral ganglion.
Organs hang below / anterior to the cord for legibility - NOT TO SCALE;
the figure is not body scale.

ACCURACY RULES - researched deliberately; do not "simplify" them back:
  - PAM50 labels 32/33 are the cord INTERMEDIATE ZONE; the
    intermediolateral COLUMN (T1-L2) is its thoracic part. Phrase it as
    "intermediate zone / IML column".
  - Sympathetic chain (paravertebral) vs prevertebral ganglia are NOT
    distinguished here - say "chain ganglia".
  - Vagus preganglionic output = dorsal motor nucleus (+ nucleus
    ambiguus contributes too, not drawn).
  - NTS is the vagal AFFERENT relay; its rostral part is the gustatory
    relay (cross-reference the gustatory page).
  - About 80% of vagus fibres are afferent - KEEP the "about"
    (published estimates range 60-90%).
  - Organs are schematic blobs positioned for legibility; distances on
    this figure are not anatomical scale.

Data licensing: nilearn's bundled MNI152 brain mask ships with nilearn;
PAM50 ships no license file. Free educational use with citation.

Usage:
    python -m human_atlas.build.human_autonomic
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
PAM50_CACHE_DIR = DATA_CACHE_DIR / "human_pain"      # PAM50 already lives here
OUT_DIR = OUTPUTS_DIR / "autonomic_system"
MESH_DIR = OUT_DIR / "mesh"
OUT_FILE = "human_autonomic_system_3d.html"

ROOT_DOWNSAMPLE = 0.35
CORD_DOWNSAMPLE = 0.5
TRACT_THRESHOLD = 0.25  # PAM50 tract volumes are probabilistic; 0.5 gives slivers

# PAM50 atlas volume ids (see atlas/info_label.txt):
# 33 = GM right intermediate zone, 32 = GM left intermediate zone.
# The intermediate zone houses preganglionic autonomic neurons; its
# thoracic part IS the intermediolateral (IML) column, T1-L2.
PAM50_TRACTS = {
    "IML_R": 33,
}

# Schematic waypoints: (x, y, z) in true MNI mm + marker radius mm.
# Cord spans roughly z -562..-67; organs hang below/anterior to the
# cord - schematic placement, NOT TO SCALE.
SCHEMATIC = {
    "Hypothal": {"pos": (4, -2, -10), "r": 6},     # bilateral pair -> one midline blob
    "DMNX":     {"pos": (5, -35, -55), "r": 3},    # dorsal motor nucleus of vagus
    "NTS":      {"pos": (8, -37, -50), "r": 2.5},  # nucleus tractus solitarii
    # sympathetic chain beads alongside the cord (thoracic -> lumbar)
    "SC1":      {"pos": (13, -28, -130), "r": 2.5},
    "SC2":      {"pos": (13, -28, -200), "r": 2.5},
    "SC3":      {"pos": (13, -28, -270), "r": 2.5},
    "SC4":      {"pos": (13, -28, -340), "r": 2.5},
    "SC5":      {"pos": (13, -28, -410), "r": 2.5},
    "Heart":    {"pos": (30, -8, -350), "r": 16},
    "Gut":      {"pos": (18, -2, -490), "r": 20},
    # vagus nerve efferent waypoints
    "VG1":      {"pos": (22, -18, -100), "r": 2},
    "VG2":      {"pos": (28, -12, -220), "r": 2},
    # vagal AFFERENT return - distinct keys so labels don't collide
    "VAg1":     {"pos": (27, -14, -180), "r": 1.5},
    "VAg2":     {"pos": (20, -22, -90), "r": 1.5},
    # sacral parasympathetic (opt-in layer)
    "SacN":     {"pos": (12, -42, -530), "r": 2.5},
}

# NOTE: the shared template reads LABELS[key] for EVERY waypoint key in a
# chain (buildChain has no guard), so every key above plus every real-mesh
# anchor below gets an entry here.
LABELS = {
    "Hypothal": {"en": "① Hypothalamus — the integrator", "zh": "① 下視丘—整合中樞"},
    "DMNX":     {"en": "⑥ Dorsal motor nucleus of vagus", "zh": "⑥ 迷走神經背核"},
    "NTS":      {"en": "⑧ Nucleus tractus solitarii", "zh": "⑧ 孤束核"},
    "SC1":      {"en": "③ Sympathetic chain ganglia", "zh": "③ 交感神經鏈"},
    "SC2":      {"en": "③ Sympathetic chain ganglia", "zh": "③ 交感神經鏈"},
    "SC3":      {"en": "③ Sympathetic chain ganglia", "zh": "③ 交感神經鏈"},
    "SC4":      {"en": "③ Sympathetic chain ganglia", "zh": "③ 交感神經鏈"},
    "SC5":      {"en": "③ Sympathetic chain ganglia", "zh": "③ 交感神經鏈"},
    "Heart":    {"en": "④ Heart — schematic, not to scale", "zh": "④ 心臟—示意,非等比例"},
    "Gut":      {"en": "⑤ Stomach & gut — schematic, not to scale", "zh": "⑤ 胃腸—示意,非等比例"},
    "VG1":      {"en": "⑦ Vagus nerve (CN X)", "zh": "⑦ 迷走神經(CN X)"},
    "VG2":      {"en": "⑦ Vagus nerve (CN X)", "zh": "⑦ 迷走神經(CN X)"},
    "VAg1":     {"en": "Visceral afferents (~80% of vagus)", "zh": "內臟傳入(約 80% 迷走纖維)"},
    "VAg2":     {"en": "Visceral afferents (~80% of vagus)", "zh": "內臟傳入(約 80% 迷走纖維)"},
    "SacN":     {"en": "Sacral parasympathetic (S2–S4)", "zh": "薦骨副交感(S2–S4)"},
    "IMLa":     {"en": "② Intermediate zone / IML column (T1–L2)", "zh": "② 中間外側柱(T1–L2)"},
    "IMLb":     {"en": "② Intermediate zone / IML column (T1–L2)", "zh": "② 中間外側柱(T1–L2)"},
    "IMLc":     {"en": "② Intermediate zone / IML column (T1–L2)", "zh": "② 中間外側柱(T1–L2)"},
    "IMLs":     {"en": "Sacral parasympathetic outflow (S2–S4)", "zh": "薦骨副交感輸出(S2–S4)"},
}

STRINGS = {
    "eyebrow": {"en": "Human &middot; MNI152 + PAM50 &middot; hypothalamus&rarr;organs",
                "zh": "人體 &middot; MNI152 + PAM50 &middot; 下視丘&rarr;內臟"},
    "title_main": {"en": "Autonomic nervous system", "zh": "自律神經系統"},
    "title_suffix": {
        "en": '<span class="accent">Accelerate vs slow</span> — two arms, one integrator',
        "zh": '<span class="accent">加速與減慢</span>—兩臂系統,一個整合中樞'},
    "subtitle": {
        "en": (
            'The <b>hypothalamus</b> integrates the whole autonomic system. Its <b>sympathetic</b> arm is '
            "thoracolumbar: commands descend the spinal cord to the <b>intermediate zone / IML column "
            '(T1&ndash;L2)</b>, jump to the <b>sympathetic chain ganglia</b>, and race out to <b>accelerate '
            "the heart</b> and <b>inhibit the gut</b>. Its <b>parasympathetic</b> arm is craniosacral: the "
            "<b>vagus nerve</b> (CN X, from the dorsal motor nucleus) <b>slows the heart</b> and "
            "<b>activates the gut</b>, with a sacral (S2&ndash;S4) outflow below. Headline fact: about "
            "<b>80% of vagus fibres are sensory</b> — the body reports upward to the <b>nucleus tractus "
            "solitarii</b> more than the brain commands downward. Solid meshes are real anatomy (PAM50 "
            "cord + intermediate zone); wireframe balls are schematic, and the organs hang below the cord "
            "<b>not to scale</b>. Hover any node for a slice."
        ),
        "zh": (
            "<b>下視丘</b>整合整個自律神經系統。<b>交感</b>臂為胸腰段:命令沿脊髓下行到<b>中間帶／中間外側柱"
            "(T1–L2)</b>,跳接到<b>交感鏈神經節</b>,再到<b>心臟加速</b>、<b>胃腸抑制</b>。<b>副交感</b>臂為腦薦段:"
            "<b>迷走神經(CN X,起自迷走神經背核)</b>負責<b>減慢心跳</b>、<b>促進胃腸</b>,下方還有薦骨(S2–S4)輸出。"
            "重點事實:約 <b>80% 的迷走纖維是感覺纖維</b>—身體向<b>孤束核</b>上報的訊息,比腦下達的命令更多。"
            "實心網格是真實解剖(PAM50 脊髓+中間帶);線框球為示意,器官懸在脊髓下方—<b>非等比例</b>。"
            "滑鼠移到任一節點可顯示切面。"
        ),
    },
    "walk_title": {"en": "Pathway walkthrough &nbsp;1&ndash;3", "zh": "路徑逐段說明 &nbsp;1&ndash;3"},
    "walk_0": {
        "en": (
            '<span class="step-tag">1 &middot; Sympathetic — thoracolumbar outflow, accelerate</span>'
            "① The <b>hypothalamus</b> weighs body state (temperature, blood pressure, stress) and issues a "
            "command &rarr; axons descend the <b>entire spinal cord</b> &rarr; ② they synapse in the "
            "<b>intermediate zone / IML column</b>, the thoracolumbar (<b>T1&ndash;L2</b>) part of the PAM50 "
            "intermediate zone — where the preganglionic sympathetic neurons sit.<br />"
            '③ Fibres exit and climb the <b>sympathetic chain</b>, the row of ganglia strung alongside the '
            "cord (paravertebral; prevertebral ganglia are not distinguished here) &rarr; ④ to the "
            '<b>heart</b>: rate and contractility <span style="color:#7fc99a">up</span>; and onward via '
            'SC3&ndash;SC5 to ⑤ the <b>gut</b>: motility <span style="color:#7fc99a">down</span>. Fight or '
            "flight: blood to muscle, glucose mobilized."
        ),
        "zh": (
            '<span class="step-tag">1 &middot; 交感—胸腰輸出,加速</span>'
            "① <b>下視丘</b>衡量身體狀態(體溫、血壓、壓力)並下達命令 &rarr; 軸突沿<b>整條脊髓</b>下行 &rarr; ② 在"
            "<b>中間帶／中間外側柱</b>的胸腰段(<b>T1–L2</b>)換元——這正是 PAM50 中間帶、節前交感神經元所在。<br />"
            "③ 纖維離開脊髓,爬上脊髓旁成串的<b>交感鏈神經節</b>(椎旁節;此處不區分椎前節)&rarr; ④ 到<b>心臟</b>:"
            '心率與收縮力<span style="color:#7fc99a">上升</span>;另經 SC3–SC5 到 ⑤ <b>胃腸</b>:蠕動'
            '<span style="color:#7fc99a">下降</span>。戰或逃:血液導向肌肉、動員血糖。'
        ),
    },
    "walk_1": {
        "en": (
            '<span class="step-tag">2 &middot; Vagus — cranial outflow, and the 80% sensory return</span>'
            "⑥ Preganglionic parasympathetic neurons sit in the <b>dorsal motor nucleus of the vagus</b> in "
            "the medulla (the nucleus ambiguus contributes too — not drawn) &rarr; ⑦ the <b>vagus nerve "
            "(CN X)</b>, the longest cranial nerve, wanders down to ④ the <b>heart</b>: rate "
            '<span style="color:#6fb0e0">down</span>; and to ⑤ the <b>gut</b>: digestion '
            '<span style="color:#6fb0e0">up</span>. Rest and digest.<br />'
            "But most of the vagus runs the <b>other way</b>: about <b>80%</b> of its fibres are "
            "<b>sensory</b> (estimates span 60&ndash;90%, so keep the &ldquo;about&rdquo;) — the pale-blue "
            "return chain shows visceral afferents climbing from the gut wall to ⑧ the <b>nucleus tractus "
            "solitarii (NTS)</b>, the vagal afferent relay that forwards visceral status to the "
            "hypothalamus. (The rostral NTS is also the taste relay — see the gustatory page.)"
        ),
        "zh": (
            '<span class="step-tag">2 &middot; 迷走神經—腦部輸出,與 80% 感覺回傳</span>'
            "⑥ 副交感節前神經元位於延髓的<b>迷走神經背核</b>(疑核也有貢獻——未繪出)&rarr; ⑦ <b>迷走神經"
            '(CN X)</b>——最長的腦神經——下行到 ④ <b>心臟</b>:心率<span style="color:#6fb0e0">減慢</span>;到 ⑤ '
            '<b>胃腸</b>:消化<span style="color:#6fb0e0">促進</span>。休息與消化。<br />'
            "但迷走神經大部分纖維其實<b>反向而行</b>:約 <b>80%</b> 是<b>感覺纖維</b>(估計值在 60–90% 之間,"
            "所以保留「約」)——淺藍回傳鏈顯示內臟傳入纖維從胃腸壁爬上 ⑧ <b>孤束核(NTS)</b>,迷走的感覺中繼站,"
            "再轉送內臟狀態給下視丘。(孤束核吻端同時是味覺中繼站——請見味覺頁。)"
        ),
    },
    "walk_2": {
        "en": (
            '<span class="step-tag">3 &middot; Craniosacral principle — and the hypothalamus above it all</span>'
            "The two arms act in <b>complement</b>: sympathetic = thoracolumbar, <b>accelerate</b>; "
            "parasympathetic = craniosacral, <b>slow &amp; activate</b>. The cranial half is the vagus; the "
            "sacral half (S2&ndash;S4, preganglionic neurons in the sacral intermediate gray) supplies the "
            "pelvic organs and lower gut — toggle the opt-in <b>sacral layer</b> to trace it.<br />"
            "① Above both arms sits the <b>hypothalamus</b> — an almond-sized forebrain structure that "
            "integrates <b>temperature</b>, <b>hormones</b> and <b>autonomic tone</b> into coherent "
            "commands. Everything below the cord on this figure — hearts, guts, ganglia — is a "
            "<b>schematic blob</b>, placed for legibility, <b>not to scale</b>."
        ),
        "zh": (
            '<span class="step-tag">3 &middot; 腦薦原則—以及統御一切的下視丘</span>'
            "兩臂作用互補:<b>交感</b>=胸腰段,<b>加速</b>;<b>副交感</b>=腦薦段,<b>減慢與促進</b>。腦部的一半是迷走"
            "神經;薦部的一半(S2–S4,節前神經元在薦髓中間灰質)支配骨盆器官與下半段胃腸——開啟自行加選的"
            "<b>薦骨層</b>即可追蹤。<br />"
            "① 兩臂之上坐著<b>下視丘</b>——杏仁大小的前腦構造,把<b>體溫</b>、<b>荷爾蒙</b>與<b>自律張力</b>"
            "整合成一致的命令。本圖脊髓以下的一切——心臟、胃腸、神經節——都是<b>示意球體</b>,為了易讀而擺放,"
            "<b>非等比例</b>。"
        ),
    },
    "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
    "structures_title": {"en": "Structures", "zh": "結構"},
    "pathways_title": {"en": "Pathways", "zh": "路徑"},
    "legend_note": {"en": "Dashed swatch / wireframe sphere = schematic node, not a real segmented structure. Click &quot;Structures&quot; to collapse this panel.",
                    "zh": "虛線色塊／線框球體＝示意節點,並非真實分割出的解剖構造。點擊「結構」可收合此面板。"},
    "symp_name": {"en": "Sympathetic (thoracolumbar)", "zh": "交感(胸腰段)"},
    "symp_desc": {"en": "hypothalamus &rarr; IML column (T1&ndash;L2) &rarr; chain ganglia &rarr; heart / gut",
                  "zh": "下視丘&rarr;中間外側柱(T1–L2)&rarr;交感鏈&rarr;心臟／胃腸"},
    "vagus_name": {"en": "Parasympathetic — vagus (CN X)", "zh": "副交感—迷走神經(CN X)"},
    "vagus_desc": {"en": "DMNX &rarr; vagus &rarr; heart (slow) + gut (activate)",
                   "zh": "迷走神經背核&rarr;迷走神經&rarr;心臟(減慢)+胃腸(促進)"},
    "vagus_aff_name": {"en": "Vagal afferents (~80% sensory)", "zh": "迷走傳入(約 80% 感覺)"},
    "vagus_aff_desc": {"en": "gut &rarr; NTS — the body reports upward",
                       "zh": "胃腸&rarr;孤束核—身體向上回報"},
    "sacral_name": {"en": "Sacral parasympathetic (S2–S4)", "zh": "薦骨副交感(S2–S4)"},
    "sacral_desc": {"en": "opt-in: sacral cord &rarr; pelvic organs / gut",
                    "zh": "自行開啟:薦髓&rarr;骨盆器官／胃腸"},
    "signal_name": {"en": "Sympathetic signal", "zh": "交感訊號"},
    "signal_desc": {"en": "animated pulse: hypothalamus &rarr; IML column",
                    "zh": "動畫脈衝:下視丘&rarr;中間外側柱"},
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


def tract_anchor(tm, z_mm, side, window=8.0):
    """A point ON a full-length cord tract at a given spinal height (um).

    Fallback-tolerant: near the cord taper (sacral levels) a window may
    miss entirely, so fall back to the nearest vertex on that side.
    """
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

    atlas_dir, template_dir = fetch_pam50()
    print(f"PAM50 at {template_dir.parent.name}")

    print("Loading MNI152 brain mask ...")
    mni_img = datasets.load_mni152_brain_mask()

    cord_img = nib.load(str(template_dir / "PAM50_cord.nii.gz"))
    structures = {
        "root": {
            "mask": mni_img.get_fdata().astype(bool), "affine": mni_img.affine,
            "downsample": ROOT_DOWNSAMPLE, "smooth": 5,
            "color": "CCCCCC", "name": "Whole-brain outline (MNI152)",
        },
        "cord": {
            "mask": cord_img.get_fdata() > 0.5, "affine": cord_img.affine,
            "downsample": CORD_DOWNSAMPLE, "smooth": 5,
            "color": "BBBBBB", "name": "Spinal cord outline (PAM50)",
        },
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
        "IML_R": ("7fc99a", "Right intermediate zone / IML (PAM50)",
                  "右中間帶／中間外側柱(PAM50)", False, True),
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

    # ---- waypoints: schematic + real-mesh anchors ----
    wp = {k: [v["pos"][0] * MM_TO_UM, v["pos"][1] * MM_TO_UM,
              v["pos"][2] * MM_TO_UM, v["r"] * MM_TO_UM]
          for k, v in SCHEMATIC.items()}
    iml_levels = []
    for k, z_mm in [("IMLa", -150), ("IMLb", -230), ("IMLc", -310)]:
        wp[k] = tract_anchor(tms["IML_R"], z_mm, "right") + [0]
        iml_levels.append(k)
    # sacral level: the cord tapers here, so tract_anchor's nearest-vertex
    # fallback decides; kept as its own key so labels never collide.
    wp["IMLs"] = tract_anchor(tms["IML_R"], -520, "right") + [0]
    real_keys = iml_levels + ["IMLs"]

    touch_symp_down = ["Hypothal"] + iml_levels           # command descends to T1-L2
    touch_chain_heart = ["SC1", "SC2", "SC3", "Heart"]
    touch_chain_gut = ["SC3", "SC4", "SC5", "Gut"]

    pathways = [
        {"id": "symp", "name_key": "symp_name", "desc_key": "symp_desc",
         "color": "0x7fc99a", "default_checked": True,
         "chains": [touch_symp_down, touch_chain_heart, touch_chain_gut]},
        {"id": "vagus", "name_key": "vagus_name", "desc_key": "vagus_desc",
         "color": "0x6fb0e0", "default_checked": True,
         "chains": [["DMNX", "VG1", "VG2", "Heart", "Gut"]]},
        {"id": "vagus_aff", "name_key": "vagus_aff_name", "desc_key": "vagus_aff_desc",
         "color": "0x9fd0e8", "default_checked": True,
         "chains": [["Gut", "VAg1", "VAg2", "NTS"]]},
        {"id": "sacral", "name_key": "sacral_name", "desc_key": "sacral_desc",
         "color": "0x6fb0e0", "default_checked": False,
         "chains": [["IMLs", "SacN", "Gut"]]},
    ]

    legend_meta = [
        {"acr": a, "name_en": meta[a][1], "name_zh": meta[a][2],
         "color": meta[a][0], "outline": meta[a][3], "default_checked": meta[a][4]}
        for a in order
    ]

    # extent over ALL meshes (brain + cord), but the schematic organs hang
    # deeper than any mesh bbox relative to the scene centre, so give the
    # deepest waypoint headroom too - otherwise the gut clips out of frame
    mesh_extent = max(float(np.ptp(tm.vertices, axis=0).max()) for tm in tms.values())
    organ_reach = max(max(abs(c) for c in v[:3]) + v[3] for v in wp.values())
    extent = max(mesh_extent, organ_reach * 1.3)
    print(f"  extent {extent:.0f} um "
          f"(mesh bbox {mesh_extent:.0f}, organ reach {organ_reach:.0f})")

    html = render_viewer_html({
        "title": "自律神經系統",
        "accent": "7fc99a",
        "extent": extent,
        "regions_js": regions_js,
        "order": order,
        "strings": STRINGS,
        "legend_meta": legend_meta,
        "pathways": pathways,
        "labels": LABELS,
        "waypoints": wp,
        "real": real_keys,
        "signal": {"pathway": "symp", "color": "0xffd48a", "duration": 2.6},
        "walk": [
            {"key": "walk_0", "color": "#7fc99a"},
            {"key": "walk_1", "color": "#6fb0e0"},
            {"key": "walk_2", "color": "#9fd0e8"},
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

