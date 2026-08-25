"""
Build a self-contained 3D viewer for the human VESTIBULAR system, right
inner ear to its four central outputs. Built on the shared
viewer_template.py renderer (see build/human_somatosensory.py for the
reference usage).

STORY - ONE SENSE, FOUR DESTINATIONS, NO BIG CROSSING. The right ear's
balance organs fire constantly. Everything converges on the vestibular
nuclei (lateral pons/medulla, floor of the 4th ventricle) and then splits
into four SIMULTANEOUS outputs, all drawn on the right because vestibular
signals do not decussate the way auditory/DCML signals do:
  (a) vestibulocerebellum (flocculonodular lobule, Lobule X) - calibration;
  (b) medial longitudinal fasciculus -> oculomotor nuclei - the
      vestibulo-ocular reflex (VOR) keeps gaze stable when the head turns
      (drawn on one side, but the reflex itself is bilateral);
  (c) thalamus (VPL/VL) -> parieto-insular vestibular cortex (posterior
      insula) - the CONSCIOUS readout: dizziness/vertigo;
  (d) lateral vestibulospinal tract (Deiters) -> spinal cord - antigravity
      extensor tone on the same side.

REAL DATA:
  - Whole-brain outline: nilearn's bundled MNI152 brain mask.
  - Cerebellum: Diedrichsen (2009) probabilistic cerebellar atlas,
    discrete MNI-space segmentation, from
    github.com/DiedrichsenLab/cerebellar_atlases - ALREADY CACHED by
    human_auditory.py. Labels 26/27/28 = Left_X/Vermis_X/Right_X give the
    vestibulocerebellum (CBLX); labels 1-34 together give the whole
    cerebellum (CBLM, translucent context).
  - Spinal cord tract: PAM50 label 19 = WM right lateral vestibulospinal
    tract, already cached by human_pain.py (probabilistic; threshold 0.25).
  - Cortex: AAL3 (version 3v2) index 34 = Insula_R, already cached by
    human_olfactory.py. PIVC sits in the posterior insula.

SCHEMATIC (no free segmentation exists): semicircular canals + otoliths,
Scarpa's ganglion, vestibular nuclei, MLF/oculomotor complex, vestibular
thalamus. The three canal RINGS drawn at the inner-ear node are wireframe
torus orientation hints only - one roughly horizontal (lateral canal), two
vertical at ~ +/-60 deg (anterior/posterior canals) - NOT anatomically
measured shapes or angles.

ACCURACY RULES - researched deliberately; do not "simplify" them back:
  - Vestibular nuclei sit LATERALLY in the pons/medulla at the FLOOR OF
    THE 4TH VENTRICLE - not medially, not ventrally.
  - VOR works through the MLF and is BILATERAL - one side is drawn for
    legibility and the label says bilateral. Do not "fix" it to one side.
  - The LATERAL vestibulospinal tract (Deiters) drives extensor/
    ANTIGRAVITY tone ipsilaterally.
  - Conscious vertigo is a CORTICAL readout (PIVC, posterior insula) of
    mismatch between vestibular/visual/proprioceptive inputs - not the
    raw vestibular signal itself.
  - The canal rings are schematic orientation hints, not measured anatomy.

Data licensing: Diedrichsen (2009) cerebellar atlas from DiedrichsenLab
GitHub; AAL3 (Rolls et al. 2020) license unspecified; PAM50 ships no
license file. Free educational use with citation.

Usage:
    py -3.13 -m human_atlas.build.human_vestibular
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
CEREB_CACHE_DIR = DATA_CACHE_DIR / "human_auditory"   # Diedrichsen atlas lives here
AAL_CACHE_DIR = DATA_CACHE_DIR / "human_olfactory"    # AAL3 already lives here
PAM50_CACHE_DIR = DATA_CACHE_DIR / "human_pain"       # PAM50 already lives here
OUT_DIR = OUTPUTS_DIR / "vestibular_system"
MESH_DIR = OUT_DIR / "mesh"
OUT_FILE = "human_vestibular_system_3d.html"

ROOT_DOWNSAMPLE = 0.35
TRACT_THRESHOLD = 0.25  # PAM50 tract volumes are probabilistic; 0.5 gives slivers

# Diedrichsen (2009) discrete cerebellar segmentation labels
LOBULE_X_LABELS = [26, 27, 28]          # Left_X / Vermis_X / Right_X
WHOLE_CEREBELLUM_LABELS = list(range(1, 35))

# AAL3 label indices (verified against the fetched atlas' .indices)
AAL = {
    "INS_R": [34],  # Insula_R - PIVC sits in the posterior insula
}
PAM50_TRACTS = {
    "VST_R": 19,  # WM right lateral vestibulospinal tract (Deiters)
}

# Schematic waypoints: (x, y, z) in true MNI mm + marker radius mm.
# Right side (x>0) throughout - vestibular outputs stay ipsilateral.
# Canals2 anchors the caption/hover for the schematic canal rings (radius 0
# + listed as "real" => no extra wireframe ball; the rings themselves are
# drawn by the page's custom JS).
SCHEMATIC = {
    "Canals":   {"pos": (54, -22, -28), "r": 5},   # inner ear
    "Canals2":  {"pos": (51, -20, -25), "r": 0},   # canal-ring caption anchor
    "Scarpa":   {"pos": (47, -29, -33), "r": 2},   # vestibular ganglion
    "VestNuc":  {"pos": (12, -40, -46), "r": 5},   # vestibular nuclei
    "MLF":      {"pos": (2, -27, -12), "r": 2.5},  # MLF / oculomotor nuclei
    "ThalVest": {"pos": (10, -20, -6), "r": 3},    # vestibular thalamus VPL/VL
}

LABELS = {
    "Canals":   {"en": "① Semicircular canals & otoliths (right ear)",
                 "zh": "① 半規管與耳石器(右內耳)"},
    "Canals2":  {"en": "three semicircular canals (schematic)",
                 "zh": "三半規管(示意)"},
    "Scarpa":   {"en": "② Scarpa's ganglion (CN VIII, vestibular)",
                 "zh": "② 前庭神經節(Scarpa 氏,CN VIII)"},
    "VestNuc":  {"en": "③ Vestibular nuclei (floor of 4th ventricle)",
                 "zh": "③ 前庭神經核(第四腦室底)"},
    "CBLX":     {"en": "④ Vestibulocerebellum (flocculonodular)",
                 "zh": "④ 前庭小腦(絨球小結葉)"},
    "MLF":      {"en": "⑤ MLF → oculomotor nuclei (VOR, bilateral)",
                 "zh": "⑤ 內側縱束→動眼神經核(VOR,雙側)"},
    "ThalVest": {"en": "⑥ Vestibular thalamus (VPL/VL)",
                 "zh": "⑥ 前庭視丘(VPL/VL)"},
    "INS_R":    {"en": "⑦ PIVC — parieto-insular vestibular cortex",
                 "zh": "⑦ 後島葉皮質(PIVC)"},
    "VSTa":     {"en": "⑧ Lateral vestibulospinal tract (Deiters)",
                 "zh": "⑧ 外側前庭脊髓束(Deiters 氏)"},
    "VSTb":     {"en": "same tract, lumbar cord — extensor tone",
                 "zh": "同一束,腰髓—伸肌張力"},
}

STRINGS = {
    "eyebrow": {"en": "Human &middot; MNI152 + PAM50 &middot; inner ear&rarr;nuclei&rarr;4 outputs",
                "zh": "人腦 &middot; MNI152 + PAM50 &middot; 內耳&rarr;神經核&rarr;四條輸出"},
    "title_main": {"en": "Vestibular system", "zh": "前庭系統"},
    "title_suffix": {"en": '<span class="accent">Balance</span> — one sense, four destinations',
                     "zh": '<span class="accent">平衡</span>—一種感覺、四個去處'},
    "subtitle": {
        "en": (
            "The right ear's balance organs fire constantly. From the <b>vestibular nuclei</b> "
            "(lateral pons/medulla, floor of the fourth ventricle) the signal splits into "
            "<b>four simultaneous outputs</b>: up the <b>MLF</b> to the oculomotor nuclei so gaze stays "
            "locked when the head turns (<b>VOR</b>); to the <b>flocculonodular cerebellum</b> for "
            "balance calibration; through the <b>thalamus (VPL/VL)</b> to the <b>posterior insula</b> "
            "&mdash; the conscious readout you experience as dizziness; and down the <b>lateral "
            "vestibulospinal tract</b> to crank up antigravity extensor tone. Unlike hearing or touch, "
            "vestibular output stays <b>ipsilateral</b> &mdash; no big midline crossing. Solid meshes are "
            "real anatomy (Diedrichsen 2009 cerebellar atlas, PAM50 cord tract, AAL3 cortex); wireframes "
            "are schematic. Hover a node for a slice plane."
        ),
        "zh": (
            "右耳的平衡受器持續放電。訊號湧入位於橋腦／延髓外側、<b>第四腦室底</b>的<b>前庭神經核</b>之後,"
            "同時分出<b>四條輸出</b>:沿<b>內側縱束(MLF)</b>上達動眼神經核,讓頭轉動時視線仍鎖定目標"
            "(<b>前庭動眼反射 VOR</b>);通往<b>絨球小結葉(前庭小腦)</b>校準平衡;經<b>視丘(VPL/VL)</b>上達"
            "<b>後島葉</b>&mdash;你「感覺到頭暈」的意識讀值;以及沿<b>外側前庭脊髓束</b>下行,拉高抗重力的"
            "伸肌張力。與聽覺、觸覺不同,前庭輸出<b>維持同側</b>&mdash;沒有大範圍的中線交叉。實心網格是"
            "真實解剖(Diedrichsen 2009 小腦圖譜、PAM50 脊髓徑、AAL3 皮質);線框為示意。滑鼠移到節點可顯示切面。"
        ),
    },
    "walk_title": {"en": "Pathway walkthrough &nbsp;1&ndash;3", "zh": "路徑逐段說明 &nbsp;1&ndash;3"},
    "walk_0": {
        "en": (
            '<span class="step-tag">1 &middot; Peripheral sensor — rotation and gravity, right ear</span>'
            "① The three <b>semicircular canals</b> sense <b>angular acceleration</b> of the head "
            "(turning, nodding, tilting) via the cupula in each ampulla; the two <b>otolith organs</b> "
            "(utricle, saccule) sense <b>linear acceleration and the direction of gravity</b> via their "
            "otoconial membranes. Together they convert head motion into hair-cell firing &rarr; "
            "② cell bodies in <b>Scarpa&apos;s ganglion</b>, the vestibular half of CN VIII &mdash; a ganglion, "
            "not a relay, so <b>nothing synapses here</b> &rarr; ③ the axons enter the brainstem at the "
            "pontomedullary junction."
        ),
        "zh": (
            '<span class="step-tag">1 &middot; 周邊受器—旋轉與重力,右內耳</span>'
            "① 三條<b>半規管</b>經壺腹內的膠頂,感測頭部的<b>角加速度</b>(轉頭、點頭、側傾);兩個<b>耳石器</b>"
            "(橢圓囊、球囊)則以耳石膜感測<b>直線加速度與重力方向</b>。它們合力將頭部運動轉成毛細胞放電 &rarr; "
            "② 細胞本體位於 <b>Scarpa 氏前庭神經節</b>(第八對腦神經的前庭支)&mdash;神經節不是中繼站,"
            "<b>這裡不換神經元</b> &rarr; ③ 軸突在橋延交界處進入腦幹。"
        ),
    },
    "walk_1": {
        "en": (
            '<span class="step-tag">2 &middot; Vestibular nuclei — four outputs begin here (default-on layers)</span>'
            '④ All fibres terminate in the <b>vestibular nuclei</b>, sitting <b>lateral</b> in the pons '
            'and medulla at the <b>floor of the fourth ventricle</b>. From here the story forks. The teal '
            'tube climbs straight to the flocculonodular lobule (on by default). The blue tube runs the '
            '<b>medial longitudinal fasciculus</b> to the oculomotor nuclei &mdash; drawn on one side only, but '
            'the <b>VOR is bilateral</b>: turn the head right and both eyes swing left in lockstep, gaze '
            'unchanged. The green layer (toggle it on) descends as the <b>lateral vestibulospinal tract</b> '
            '(Deiters) to the spinal cord, raising <b>antigravity extensor tone</b> on the same side so you '
            'do not topple.'
        ),
        "zh": (
            '<span class="step-tag">2 &middot; 前庭神經核—四條輸出由此展開(預設開啟的圖層)</span>'
            '④ 所有纖維止於<b>前庭神經核</b>&mdash;位於橋腦與延髓的<b>外側</b>、<b>第四腦室底</b>。故事從這裡分岔。'
            '藍綠色的管路直上絨球小結葉(預設開啟)。藍色管路沿<b>內側縱束(MLF)</b>到達動眼神經核&mdash;'
            '圖中只畫單側,但 <b>VOR 是雙側的</b>:頭向右轉,兩眼同步轉向左,視線不動。綠色圖層(請自行開啟)'
            '沿<b>外側前庭脊髓束</b>(Deiters 氏)下行入脊髓,提高同側<b>抗重力伸肌張力</b>,讓你不致傾倒。'
        ),
    },
    "walk_2": {
        "en": (
            '<span class="step-tag">3 &middot; Opt-in layers — feeling dizzy vs. calibrating the reflexes</span>'
            "The purple layer (opt-in) relays through the <b>vestibular thalamus (VPL/VL)</b> to the "
            "<b>parieto-insular vestibular cortex (PIVC)</b> in the posterior insula. Balance becomes "
            "<b>conscious</b> here: vertigo is not the raw vestibular signal but a <b>cortical readout of "
            "mismatch</b> between vestibular, visual and proprioceptive inputs &mdash; which is why motion "
            "sickness and BPPV feel like movement that is not happening. The teal cerebellar branch closes "
            "the loop: the <b>vestibulocerebellum</b> continuously recalibrates the reflexes driven by the "
            "nuclei, tuning VOR gain and postural tone from experience."
        ),
        "zh": (
            '<span class="step-tag">3 &middot; 自行開啟的圖層—感覺頭暈 vs. 校正反射</span>'
            "紫色圖層(自行開啟)經<b>前庭視丘(VPL/VL)</b>中繼,抵達後島葉的<b>島蓋前庭皮質(PIVC)</b>。"
            "平衡在此成為<b>意識</b>:眩暈並非原始的前庭訊號,而是皮質對前庭、視覺、本體感覺<b>互相矛盾之處的讀值</b>"
            "&mdash;所以暈車、耳石症會讓你「感覺到」其實沒發生的移動。藍綠色的小腦分支負責收尾:"
            "<b>前庭小腦</b>持續依經驗重新校準神經核所驅動的反射,調整 VOR 增益與姿勢張力。"
        ),
    },
    "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
    "structures_title": {"en": "Structures", "zh": "結構"},
    "pathways_title": {"en": "Pathways", "zh": "路徑"},
    "legend_note": {"en": "Dashed swatch / wireframe sphere = schematic node, not a real segmented structure. Click &quot;Structures&quot; to collapse this panel.",
                    "zh": "虛線色塊／線框球體＝示意節點,並非真實分割出的解剖構造。點擊「結構」可收合此面板。"},
    "vest_cblm_name": {"en": "Vestibulocerebellar", "zh": "前庭小腦路徑"},
    "vest_cblm_desc": {"en": "nuclei &rarr; flocculonodular lobule (calibration)",
                       "zh": "神經核&rarr;絨球小結葉(校準)"},
    "vest_vor_name": {"en": "VOR (vestibulo-ocular)", "zh": "前庭動眼反射(VOR)"},
    "vest_vor_desc": {"en": "nuclei &rarr; MLF &rarr; oculomotor nuclei, bilateral",
                      "zh": "神經核&rarr;內側縱束&rarr;動眼神經核,雙側"},
    "vest_thal_name": {"en": "Conscious balance (PIVC)", "zh": "意識平衡(PIVC)"},
    "vest_thal_desc": {"en": "nuclei &rarr; thalamus VPL/VL &rarr; posterior insula",
                       "zh": "神經核&rarr;視丘 VPL/VL&rarr;後島葉"},
    "vest_spinal_name": {"en": "Lateral vestibulospinal", "zh": "外側前庭脊髓束"},
    "vest_spinal_desc": {"en": "nuclei &rarr; cord — ipsilateral extensor tone",
                         "zh": "神經核&rarr;脊髓—同側伸肌張力"},
    "signal_name": {"en": "Neural signal", "zh": "神經訊號"},
    "signal_desc": {"en": "animated pulse, ear &rarr; vestibulocerebellum", "zh": "動畫訊號,內耳&rarr;前庭小腦"},
    "controls_title": {"en": "Controls", "zh": "操作說明"},
    "hint_controls": {"en": "<b>drag</b> orbit &nbsp; <b>scroll</b> zoom &nbsp; <b>right-drag</b> pan &nbsp; <b>hover</b> a node for a slice plane",
                      "zh": "<b>拖曳</b>旋轉 &nbsp; <b>滾輪</b>縮放 &nbsp; <b>右鍵拖曳</b>平移 &nbsp; <b>滑鼠移到節點</b>顯示切面"},
    "hint_units": {"en": "MNI152 + PAM50 space (mm, &times;1000 &rarr; &micro;m)",
                   "zh": "MNI152 + PAM50 空間(mm,&times;1000 &rarr; &micro;m)"},
    "lang_button": {"en": "中文", "zh": "EN"},
    "anterior": {"en": "Anterior", "zh": "前"},
    "posterior": {"en": "Posterior", "zh": "後"},
    "superior": {"en": "Superior", "zh": "上"},
    "right_axis": {"en": "Right", "zh": "右"},
}

CUSTOM_JS = """
// three semicircular canals: wireframe rings at the inner-ear node -
// schematic orientation hints only (one roughly horizontal, two vertical
// at ~ +/-60 deg), NOT anatomically measured; toggles with vest_cblm
(function () {
  const c = WAYPOINTS.Canals;
  const rots = [
    [Math.PI / 2, 0, 0],
    [0, Math.PI / 3, 0],
    [0, -Math.PI / 3, 0],
  ];
  rots.forEach((r) => {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(EXTENT * 0.012, EXTENT * 0.0012, 8, 40),
      new THREE.MeshBasicMaterial({ color: 0x5ac0c0, wireframe: true, transparent: true, opacity: 0.5 })
    );
    ring.position.set(c[0], c[1], c[2]);
    ring.rotation.set(r[0], r[1], r[2]);
    pathwayGroups.vest_cblm.add(ring);
  });
  // whole cerebellum is context: soften the template's opaque material
  const cb = meshes.CBLM;
  cb.material.transparent = true;
  cb.material.opacity = 0.32;
  cb.material.depthWrite = false;
  cb.material.needsUpdate = true;
  cb.renderOrder = 4;
})();
"""


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

    cereb_path = CEREB_CACHE_DIR / "atl-Anatom_space-MNI_dseg.nii"
    if not cereb_path.exists():
        raise RuntimeError(
            "Diedrichsen cerebellar atlas not cached - run "
            "`py -3.13 -m human_atlas.build.human_auditory` first")

    print("Loading MNI152 brain mask, Diedrichsen cerebellar atlas, AAL3, PAM50 ...")
    mni_img = datasets.load_mni152_brain_mask()
    cereb_img = nib.load(str(cereb_path))
    cereb_data = cereb_img.get_fdata()
    aal = datasets.fetch_atlas_aal(version="3v2", data_dir=str(AAL_CACHE_DIR))
    aal_img = nib.load(aal.maps) if isinstance(aal.maps, str) else aal.maps
    aal_data = aal_img.get_fdata()
    atlas_dir, _template_dir = fetch_pam50()

    structures = {
        "root": {
            "mask": mni_img.get_fdata().astype(bool), "affine": mni_img.affine,
            "downsample": ROOT_DOWNSAMPLE, "smooth": 5,
            "color": "CCCCCC", "name": "Whole-brain outline (MNI152)",
        },
        "CBLM": {
            "mask": np.isin(cereb_data, WHOLE_CEREBELLUM_LABELS), "affine": cereb_img.affine,
            "downsample": 1.0, "smooth": 8,
            "color": "6F8FE0", "name": "Whole cerebellum (Diedrichsen 2009)",
        },
        "CBLX": {
            "mask": np.isin(cereb_data, LOBULE_X_LABELS), "affine": cereb_img.affine,
            "downsample": 1.0, "smooth": 15,
            "color": "5AC0C0", "name": "Vestibulocerebellum, lobule X (Diedrichsen 2009)",
        },
        "VST_R": {
            "mask": nib.load(str(atlas_dir / f"PAM50_atlas_{PAM50_TRACTS['VST_R']:02d}.nii.gz")).get_fdata() > TRACT_THRESHOLD,
            "affine": nib.load(str(atlas_dir / f"PAM50_atlas_{PAM50_TRACTS['VST_R']:02d}.nii.gz")).affine,
            "downsample": 1.0, "smooth": 8,
            "color": "7FC99A", "name": "Lateral vestibulospinal tract, right (PAM50)",
        },
        "INS_R": {
            "mask": np.isin(aal_data, AAL["INS_R"]), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 15,
            "color": "C9A8FF", "name": "Posterior insula, right (AAL3) — PIVC",
        },
    }

    # per-structure display metadata: (color, name_en, name_zh, outline?, default on?)
    meta = {
        "root":  ("CCCCCC", "Whole-brain outline (MNI152)", "全腦輪廓(MNI152)", True, True),
        "CBLM":  ("6F8FE0", "Whole cerebellum (Diedrichsen 2009)", "全小腦(Diedrichsen 2009 圖譜)", False, False),
        "CBLX":  ("5AC0C0", "Vestibulocerebellum, lobule X (Diedrichsen 2009)", "前庭小腦—第X小葉(Diedrichsen 2009)", False, True),
        "VST_R": ("7FC99A", "Lateral vestibulospinal tract, right (PAM50)", "右外側前庭脊髓束(PAM50)", False, False),
        "INS_R": ("C9A8FF", "Posterior insula, right (AAL3) — PIVC", "右後島葉(AAL3)—PIVC", False, False),
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
    order = ["root", "CBLM", "CBLX", "VST_R", "INS_R"]

    # extent over ALL meshes (brain + cerebellum + cord tract) so the camera
    # frames the whole figure
    extent = max(float(np.ptp(tm.vertices, axis=0).max()) for tm in tms.values())

    # ---- waypoints: schematic + real-mesh anchors ----
    wp = {k: [v["pos"][0] * MM_TO_UM, v["pos"][1] * MM_TO_UM,
              v["pos"][2] * MM_TO_UM, v["r"] * MM_TO_UM]
          for k, v in SCHEMATIC.items()}
    wp["CBLX"] = hemi_anchor(tms["CBLX"], "right") + [0]
    wp["INS_R"] = hemi_anchor(tms["INS_R"], "right") + [0]
    wp["VSTa"] = tract_anchor(tms["VST_R"], -100, "right") + [0]  # cervical
    wp["VSTb"] = tract_anchor(tms["VST_R"], -220, "right") + [0]  # thoracic/lumbar

    cblm_chain = ["Canals", "Canals2", "Scarpa", "VestNuc", "CBLX"]
    vor_chain = ["VestNuc", "MLF"]
    thal_chain = ["VestNuc", "ThalVest", "INS_R"]
    spinal_chain = ["VestNuc", "VSTa", "VSTb"]
    real_keys = ["CBLX", "INS_R", "VSTa", "VSTb", "Canals2"]

    pathways = [
        {"id": "vest_cblm", "name_key": "vest_cblm_name", "desc_key": "vest_cblm_desc",
         "color": "0x5ac0c0", "default_checked": True, "chains": [cblm_chain]},
        {"id": "vest_vor", "name_key": "vest_vor_name", "desc_key": "vest_vor_desc",
         "color": "0x5a8fe0", "default_checked": True, "chains": [vor_chain]},
        {"id": "vest_thal", "name_key": "vest_thal_name", "desc_key": "vest_thal_desc",
         "color": "0xc9a8ff", "default_checked": False, "chains": [thal_chain]},
        {"id": "vest_spinal", "name_key": "vest_spinal_name", "desc_key": "vest_spinal_desc",
         "color": "0x7fc99a", "default_checked": False, "chains": [spinal_chain]},
    ]

    legend_meta = [
        {"acr": a, "name_en": meta[a][1], "name_zh": meta[a][2],
         "color": meta[a][0], "outline": meta[a][3], "default_checked": meta[a][4]}
        for a in order
    ]

    html = render_viewer_html({
        "title": "前庭系統",
        "accent": "5ac0c0",
        "extent": extent,
        "regions_js": regions_js,
        "order": order,
        "strings": STRINGS,
        "legend_meta": legend_meta,
        "pathways": pathways,
        "labels": LABELS,
        "waypoints": wp,
        "real": real_keys,
        "signal": {"pathway": "vest_cblm", "color": "0xffd48a", "duration": 2.4},
        "walk": [
            {"key": "walk_0", "color": "#5ac0c0"},
            {"key": "walk_1", "color": "#5a8fe0"},
            {"key": "walk_2", "color": "#c9a8ff"},
        ],
        "custom_js": CUSTOM_JS,
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
