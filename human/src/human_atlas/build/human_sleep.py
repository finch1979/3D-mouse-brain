"""
Build a self-contained 3D viewer for the human SLEEP & AROUSAL systems:
the ascending reticular activating system's two arms, the VLPO sleep
switch, and the SCN circadian clock - the flip-flop switch model.

STORY - WAKEFULNESS IS GENERATED, SLEEP IS ACTIVE INHIBITION.
Wakefulness is produced by a handful of small brainstem/basal forebrain
nuclei, each flooding the forebrain with its own transmitter:
acetylcholine from the PPT/LDT through the thalamic gate (thalamic arm),
noradrenaline from the locus coeruleus via the basal forebrain
(monoaminergic arm), serotonin from the raphe nuclei and dopamine from the
VTA joining the same diffuse projection. Sleep is NOT passive shutdown:
the ventrolateral preoptic nucleus (VLPO) releases GABA/galanin onto ALL
of those nuclei, while they inhibit the VLPO back - mutual inhibition =
bistability = a flip-flop switch, not a dimmer, which is why transitions
between waking and sleep are fast. Orexin/hypocretin neurons stabilise
the wake side; losing them causes narcolepsy type 1. The suprachiasmatic
nucleus (SCN), fed by light via the retinohypothalamic tract, times when
the switch is allowed to flip.

REAL DATA:
  - Brain outline: nilearn's bundled MNI152 brain mask.
  - Neuromodulatory nuclei: AAL3v2 via nilearn.datasets.fetch_atlas_aal(
    version="3v2"). Verified label indices: LC_L 167, LC_R 168,
    Raphe_D 169, Raphe_M 170, VTA_L 159, VTA_R 160. AAL3 genuinely
    segments these nuclei - they are REAL meshes. They are TINY (single-
    digit voxel counts at the atlas' native resolution); smoothing stays
    low (3 Taubin iterations) so they don't get erased.
  - Thalamus: Harvard-Oxford SUBCORTICAL atlas via
    datasets.fetch_atlas_harvard_oxford("sub-maxprob-thr25-1mm"),
    label 4 (Left Thalamus) + 15 (Right Thalamus) - shown translucent
    grey as "the gate", default ON.

SCHEMATIC (no free segmentation exists): brainstem reticular formation,
PPT/LDT cholinergic nuclei, basal forebrain, diffuse cortical endpoints,
VLPO (not in ANY free atlas - the hypothalamus has no free segmentation),
retina and SCN. Wireframe balls + tubes mark them.

ACCURACY RULES - researched deliberately; do not "simplify" them back:
  - AAL3v2 really does segment the LC (167/168), dorsal & median raphe
    (169/170) and VTA (159/160) - say these are REAL meshes. The LC mesh
    is minuscule; do not inflate or over-smooth it.
  - VLPO is schematic. Hypothalamic nuclei have no free segmentation.
  - Flip-flop: VLPO and the arousal nuclei MUTUALLY inhibit - bistable,
    hence fast state transitions. Orexin/Hcrt neurons (lateral
    hypothalamus) stabilise the wake side; their loss = narcolepsy type 1.
  - Thalamic gating centrally involves the thalamic reticular nucleus,
    which is NOT segmented here - the Harvard-Oxford thalamus drawn is
    the gate's bulk, say so.
  - SCN = circadian pacemaker; light arrives via the retinohypothalamic
    tract; the melatonin pathway via the pineal gland is NOT drawn.
  - Do NOT claim "the LC stops firing in sleep": LC firing is highest in
    quiet waking and LOWEST in REM sleep - it tones down, it does not
    simply switch off. Phrase carefully.
  - The raphe (serotonin) and VTA (dopamine) are real meshes explained in
    the walkthrough and legend; no separate tubes are drawn for them.
  - The VLPO pathway is drawn to the LEFT LC but its inhibition applies
    to ALL arousal nuclei - the text must say this.

Data licensing: AAL3 (Rolls et al. 2020) license unspecified; Harvard-
Oxford is non-commercial (FSL). Free educational use with citation.

Usage:
    python -m human_atlas.build.human_sleep
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
OUT_DIR = OUTPUTS_DIR / "sleep_arousal"
MESH_DIR = OUT_DIR / "mesh"
OUT_FILE = "human_sleep_arousal_3d.html"

ROOT_DOWNSAMPLE = 0.35
AAL_CACHE_DIR = DATA_CACHE_DIR / "human_olfactory"   # AAL3 already lives here
HO_CACHE_DIR = DATA_CACHE_DIR / "human_auditory"     # HO subcortical already lives here

# AAL3v2 label ids (verified against the fetched atlas' .indices)
AAL_VERIFIED = {
    "LC_R": 168, "LC_L": 167,
    "Raphe_D": 169, "Raphe_M": 170,
    "VTA_R": 160, "VTA_L": 159,
}
# Harvard-Oxford subcortical label list positions (verified)
HO_THAL_VERIFIED = {"Left Thalamus": 4, "Right Thalamus": 15}

# Schematic waypoints: (x, y, z) in true MNI mm + marker radius mm.
SCHEMATIC = {
    "RF":      {"pos": (4, -34, -40), "r": 5},
    "PPT":     {"pos": (5, -28, -16), "r": 3},
    "BF":      {"pos": (10, 8, -6), "r": 3},
    "CORTEX":  {"pos": (0, -10, 45), "r": 28},
    "CORTEXm": {"pos": (-8, -14, 42), "r": 26},
    "VLPO":    {"pos": (3, 6, -8), "r": 4},
    "VLPOx":   {"pos": (5, -14, -18), "r": 2},
    "Eye":     {"pos": (24, 2, -10), "r": 4},
    "SCN":     {"pos": (6, 3, -5), "r": 2.5},
    "SCNv":    {"pos": (4, 5, -7), "r": 1.5},
}
# Used only if the AAL3 LC masks turn out empty (they don't today).
LC_FALLBACK_SCHEMATIC = {
    "LC_R": {"pos": (5, -34, -21), "r": 3},
    "LC_L": {"pos": (-5, -34, -21), "r": 3},
}

LABELS = {
    "RF":      {"en": "① Brainstem reticular formation", "zh": "① 腦幹網狀結構"},
    "PPT":     {"en": "② PPT/LDT cholinergic nuclei", "zh": "② 橋腦被蓋膽鹼性核(PPT/LDT)"},
    "THAL":    {"en": "③ Thalamus — the gate", "zh": "③ 視丘—閘門"},
    "CORTEX":  {"en": "④ Diffuse cortical projection", "zh": "④ 廣泛皮質投射"},
    "CORTEXm": {"en": "④ Diffuse cortical projection (monoaminergic arm)",
                "zh": "④ 廣泛皮質投射(單胺臂)"},
    "LC_R":    {"en": "⑤ Locus coeruleus (noradrenaline)", "zh": "⑤ 藍斑核(正腎上腺素)"},
    "BF":      {"en": "⑥ Basal forebrain", "zh": "⑥ 基底前腦"},
    "LC_L":    {"en": "→ inhibits ALL the arousal nuclei", "zh": "→ 抑制所有覺醒核團"},
    "VLPO":    {"en": "⑦ VLPO (sleep switch, GABA)", "zh": "⑦ VLPO(睡眠開關,GABA)"},
    "VLPOx":   {"en": "toward the brainstem arousal nuclei", "zh": "往腦幹覺醒核團"},
    "Eye":     {"en": "⑧ Retina", "zh": "⑧ 視網膜"},
    "SCN":     {"en": "⑨ Suprachiasmatic nucleus (clock)", "zh": "⑨ 視交叉上核(SCN,時鐘)"},
    "SCNv":    {"en": "→ times the VLPO switch", "zh": "→ 計時 VLPO 開關"},
}

STRINGS = {
    "eyebrow": {"en": "Human &middot; MNI152 &middot; reticular formation&rarr;thalamus&rarr;cortex",
                "zh": "人類 &middot; MNI152 &middot; 網狀結構&rarr;視丘&rarr;皮質"},
    "title_main": {"en": "Sleep & arousal", "zh": "睡眠與覺醒"},
    "title_suffix": {"en": '<span class="accent">The flip-flop switch</span> — two arms up, one switch down',
                     "zh": '<span class="accent">翻轉開關</span>—兩臂上行、一開關反轉'},
    "subtitle": {
        "en": (
            "Wakefulness is not the brain&rsquo;s resting state — it is actively generated by a handful of "
            "tiny nuclei, each flooding the forebrain with its own transmitter: acetylcholine from the "
            "<b>PPT/LDT</b> through the <b>thalamic gate</b>, noradrenaline from the <b>locus coeruleus</b>, "
            "serotonin from the <b>raphe nuclei</b>, dopamine from the <b>VTA</b>. Sleep is not passive "
            "shutdown but <b>active inhibition</b> of all of them by the VLPO — the two sides mutually "
            "inhibit, so the circuit is a <b>flip-flop</b>, not a dimmer: waking&rarr;sleep transitions are fast. "
            "The SCN clock times the switch. Solid meshes are real anatomy — AAL3 even segments the "
            "locus coeruleus, raphe and VTA!; wireframe markers are schematic. Hover a node for a slice plane."
        ),
        "zh": (
            "覺醒不是大腦的待機狀態——它由少數幾個微小核團主動產生,每個核團用自己的傳導物質淹沒前腦:"
            "<b>PPT/LDT</b> 的乙醯膽鹼經<b>視丘閘門</b>上行、<b>藍斑核</b>的正腎上腺素、<b>縫核</b>的血清素、"
            "<b>腹側被蓋區(VTA)</b>的多巴胺。睡眠也不是被動關機,而是 VLPO 對這些核團的<b>主動抑制</b>——"
            "兩邊互相抑制,電路因此是<b>翻轉開關(flip-flop)</b>而非調光器:清醒與睡眠之間的切換才會如此迅速。"
            "視交叉上核的時鐘為開關計時。實心網格是真實解剖——AAL3 連藍斑核、縫核與腹側被蓋區都有分割!"
            ";線框標記為示意。滑鼠移到節點可顯示切面。"
        ),
    },
    "walk_title": {"en": "Sleep-switch walkthrough &nbsp;1&ndash;3", "zh": "睡眠開關逐段說明 &nbsp;1&ndash;3"},
    "walk_0": {
        "en": (
            '<span class="step-tag">1 &middot; Two ascending arousal arms — wakefulness is generated</span>'
            "① The <b>brainstem reticular formation</b> drives ② the <b>PPT/LDT cholinergic nuclei</b>; their axons "
            "gate the ③ <b>thalamus</b> — open the gate and tonic excitation floods ④ the entire cortex. That is the "
            "<b>thalamic arm</b>.<br />"
            "⑤ The <b>locus coeruleus</b> sends noradrenaline to the ⑥ <b>basal forebrain</b> and diffusely to cortex — "
            "the <b>monoaminergic arm</b>. Two more REAL meshes ride along in the legend: the <b>raphe nuclei</b> "
            "(serotonin) and the <b>VTA</b> (dopamine) join the same diffuse projection; their tubes are omitted to "
            "keep the figure readable.<br />"
            "Thalamic gating properly involves the <b>thalamic reticular nucleus</b>, which no free atlas segments — "
            "the Harvard-Oxford thalamus shown here is the gate&rsquo;s bulk."
        ),
        "zh": (
            '<span class="step-tag">1 &middot; 兩條上行覺醒臂—覺醒是被產生的</span>'
            "① <b>腦幹網狀結構</b>驅動 ② <b>橋腦被蓋膽鹼性核(PPT/LDT)</b>;其軸突控制 ③ <b>視丘</b>閘門——閘門一開,"
            "張力性興奮便淹沒 ④ 整個皮質。這是<b>視丘臂</b>。<br />"
            "⑤ <b>藍斑核</b>把正腎上腺素送往 ⑥ <b>基底前腦</b>並瀰散至皮質——<b>單胺臂</b>。圖例中還有兩個真實網格同行:"
            "<b>縫核</b>(血清素)與 <b>VTA</b>(多巴胺)加入同一條瀰散投射;為保持圖面可讀,未畫出它們的路徑管。<br />"
            "視丘閘控的核心其實是<b>視丘網狀核</b>,但免費 atlas 皆未分割——此處顯示的 Harvard-Oxford 視丘是閘門的主體。"
        ),
    },
    "walk_1": {
        "en": (
            '<span class="step-tag">2 &middot; The flip-flop switch — sleep is active inhibition</span>'
            "Toggle on ⑦ the <b>VLPO</b> layer: this small hypothalamic nucleus releases <b>GABA and galanin</b> onto "
            "<b>ALL</b> of the arousal nuclei above — switching them off. Because the arousal nuclei simultaneously "
            "inhibit the VLPO right back, the circuit is bistable: a true <b>flip-flop</b>. You are either awake or "
            "asleep, with fast decisive transitions — not a dimmer sliding through half-states.<br />"
            "The wake side is stabilised by <b>orexin/hypocretin</b> neurons in the lateral hypothalamus; losing them "
            "causes <b>narcolepsy type 1</b>. Nuance: locus coeruleus firing is <b>highest in quiet waking and lowest "
            "in REM</b> — it tones down gradually; it does not simply stop."
        ),
        "zh": (
            '<span class="step-tag">2 &middot; 翻轉開關—睡眠是主動抑制</span>'
            "開啟 ⑦ <b>VLPO</b> 圖層:這個小小的下視丘核團對上述<b>所有</b>覺醒核團釋放 <b>GABA 與甘丙素(galanin)</b>,"
            "把它們整組關掉。由於覺醒核團也同時回頭抑制 VLPO,電路成雙穩態:真正的<b>翻轉開關</b>——要嘛清醒、要嘛睡著,"
            "切換快速而果斷;不是在半夢半醒間滑動的調光器。<br />"
            "清醒端由外側下視丘的<b>食慾素/ hypocretin</b> 神經元固定;失去它們就是<b>第一型猝睡症</b>。精確地說:"
            "藍斑核放電在安靜清醒時<b>最高</b>、REM 睡眠時<b>最低</b>——它是逐漸調降,並非直接停止。"
        ),
    },
    "walk_2": {
        "en": (
            '<span class="step-tag">3 &middot; The circadian clock — when the switch may flip</span>'
            "⑧ Light reaches ⑨ the <b>suprachiasmatic nucleus (SCN)</b> directly via the <b>retinohypothalamic "
            "tract</b>; the SCN then <b>times the VLPO switch</b>, biasing it toward sleep in the evening and toward "
            "wake in the morning. Melatonin release from the pineal gland follows the SCN&rsquo;s rhythm but is "
            "<b>not drawn</b> on this page.<br />"
            "<b>REM/NREM.</b> In NREM the whole arousal system idles. In REM the cholinergic arm re-ignites while the "
            "monoaminergic arm (LC, raphe) falls nearly silent — a dreaming, paralysed brain: the two arms coming "
            "uncoupled IS the REM state."
        ),
        "zh": (
            '<span class="step-tag">3 &middot; 日夜時鐘—決定開關何時可以翻轉</span>'
            "⑧ 光線經<b>視網膜下視丘徑</b>直達 ⑨ <b>視交叉上核(SCN)</b>;SCN 再為 <b>VLPO 開關計時</b>——傍晚把天平推向睡眠,"
            "清晨推向清醒。松果腺依 SCN 節律釋放褪黑激素,但本頁<b>未畫出</b>該路徑。<br />"
            "<b>REM/NREM。</b>NREM 期間整個覺醒系統怠速;REM 期間膽鹼性臂重新點火,而單胺臂(藍斑核、縫核)近乎靜默——"
            "一個作夢卻癱瘓的腦:兩條臂脫鉤本身就是 REM 狀態。"
        ),
    },
    "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
    "structures_title": {"en": "Structures", "zh": "結構"},
    "pathways_title": {"en": "Pathways", "zh": "路徑"},
    "legend_note": {"en": 'Wireframe spheres = schematic nodes (VLPO, reticular formation, PPT/LDT, basal forebrain, retina and SCN have no free segmentation). Click &quot;Structures&quot; to collapse this panel.',
                    "zh": "線框球體＝示意節點(VLPO、網狀結構、PPT/LDT、基底前腦、視網膜與 SCN 皆無免費分割)。點擊「結構」可收合此面板。"},
    "aras_thal_name": {"en": "Thalamic arm (cholinergic)", "zh": "視丘臂(膽鹼性)"},
    "aras_thal_desc": {"en": "reticular formation &rarr; PPT/LDT &rarr; thalamic gate &rarr; cortex",
                       "zh": "網狀結構&rarr;PPT/LDT&rarr;視丘閘門&rarr;皮質"},
    "aras_mono_name": {"en": "Monoaminergic arm (noradrenaline)", "zh": "單胺臂(正腎上腺素)"},
    "aras_mono_desc": {"en": "locus coeruleus &rarr; basal forebrain &rarr; cortex (+raphe 5-HT, VTA DA in legend)",
                       "zh": "藍斑核&rarr;基底前腦&rarr;皮質(另見圖例:縫核血清素、VTA 多巴胺)"},
    "vlpo_name": {"en": "Sleep switch (VLPO)", "zh": "睡眠開關(VLPO)"},
    "vlpo_desc": {"en": "GABA/galanin inhibition of ALL the arousal nuclei",
                  "zh": "以 GABA／甘丙素抑制所有覺醒核團"},
    "clock_name": {"en": "Circadian clock (SCN)", "zh": "日夜時鐘(SCN)"},
    "clock_desc": {"en": "retina &rarr; SCN &rarr; times the VLPO switch",
                   "zh": "視網膜&rarr;視交叉上核&rarr;計時睡眠開關"},
    "signal_name": {"en": "Neural signal", "zh": "神經訊號"},
    "signal_desc": {"en": "animated pulse along the noradrenergic arm", "zh": "沿正腎上腺素臂的動畫脈衝"},
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


def resolve_aal_ids(aal):
    """Map the six neuromodulatory-nuclei names to their AAL3v2 voxel ids."""
    name_to_id = {str(n): int(str(i)) for n, i in zip(aal.labels, aal.indices)}
    ids = {}
    for acr in AAL_VERIFIED:
        if acr not in name_to_id:
            raise RuntimeError(f"AAL3v2 label '{acr}' not found in fetched atlas labels")
        ids[acr] = name_to_id[acr]
        if ids[acr] != AAL_VERIFIED[acr]:
            print(f"  note: {acr} id {ids[acr]} differs from verified {AAL_VERIFIED[acr]}")
    return ids


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

    print("Loading MNI152 brain mask + AAL3 + Harvard-Oxford subcortical ...")
    mni_img = datasets.load_mni152_brain_mask()
    aal = datasets.fetch_atlas_aal(version="3v2", data_dir=str(AAL_CACHE_DIR))
    aal_img = nib.load(aal.maps) if isinstance(aal.maps, str) else aal.maps
    aal_data = aal_img.get_fdata()
    aal_ids = resolve_aal_ids(aal)

    ho = datasets.fetch_atlas_harvard_oxford("sub-maxprob-thr25-1mm", data_dir=str(HO_CACHE_DIR))
    ho_img = nib.load(ho.maps) if isinstance(ho.maps, str) else ho.maps
    ho_data = ho_img.get_fdata()
    label_to_int = {name: i for i, name in enumerate(ho.labels)}
    for name, want in HO_THAL_VERIFIED.items():
        if name not in label_to_int:
            raise RuntimeError(f"'{name}' not found in Harvard-Oxford subcortical labels")
        if label_to_int[name] != want:
            print(f"  note: '{name}' is label {label_to_int[name]}, differs from verified {want}")
    thal_ids = [label_to_int["Left Thalamus"], label_to_int["Right Thalamus"]]

    structures = {
        "root": {
            "mask": mni_img.get_fdata().astype(bool), "affine": mni_img.affine,
            "downsample": ROOT_DOWNSAMPLE, "smooth": 5,
            "color": "CCCCCC", "name": "Whole-brain outline (MNI152)",
        },
        "THAL": {
            "mask": np.isin(ho_data, thal_ids), "affine": ho_img.affine,
            "downsample": 1.0, "smooth": 8,
            "color": "888888", "name": "Thalamus — the gate (Harvard-Oxford)",
        },
        "LC_R": {
            "mask": np.isin(aal_data, [aal_ids["LC_R"]]), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 3,
            "color": "e0a458", "name": "Locus coeruleus, right (AAL3)",
        },
        "LC_L": {
            "mask": np.isin(aal_data, [aal_ids["LC_L"]]), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 3,
            "color": "e0a458", "name": "Locus coeruleus, left (AAL3)",
        },
        "Raphe_D": {
            "mask": np.isin(aal_data, [aal_ids["Raphe_D"]]), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 3,
            "color": "7fc99a", "name": "Dorsal raphe, serotonin (AAL3)",
        },
        "Raphe_M": {
            "mask": np.isin(aal_data, [aal_ids["Raphe_M"]]), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 3,
            "color": "7fc99a", "name": "Median raphe, serotonin (AAL3)",
        },
        "VTA_L": {
            "mask": np.isin(aal_data, [aal_ids["VTA_L"]]), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 3,
            "color": "6fb0e0", "name": "Ventral tegmental area, left (AAL3)",
        },
        "VTA_R": {
            "mask": np.isin(aal_data, [aal_ids["VTA_R"]]), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 3,
            "color": "6fb0e0", "name": "Ventral tegmental area, right (AAL3)",
        },
    }

    # empty-mask check BEFORE any meshing: non-LC empties are fatal; an
    # empty LC falls back to a schematic-only marker (it is genuinely
    # minuscule in AAL3v2 - single-digit voxels today)
    counts = {acr: int(s["mask"].sum()) for acr, s in structures.items()}
    lc_missing = any(counts[k] == 0 for k in ("LC_R", "LC_L"))
    fatal = [acr for acr, n in counts.items() if n == 0 and acr not in ("LC_R", "LC_L")]
    if fatal:
        raise RuntimeError(f"{', '.join(fatal)} masks are empty - wrong label index or threshold")
    if lc_missing:
        print("  WARNING: AAL3 LC mask empty - falling back to schematic-only LC markers")
        for k in ("LC_R", "LC_L"):
            del structures[k]

    meta = {
        "root":    ("CCCCCC", "Whole-brain outline (MNI152)", "全腦輪廓(MNI152)", True, True),
        "THAL":    ("888888", "Thalamus — the gate (Harvard-Oxford)", "視丘—閘門(Harvard-Oxford)", False, True),
        "LC_R":    ("e0a458", "Locus coeruleus, right (AAL3)", "右藍斑核(AAL3)", False, True),
        "LC_L":    ("e0a458", "Locus coeruleus, left (AAL3)", "左藍斑核(AAL3)", False, False),
        "Raphe_D": ("7fc99a", "Dorsal raphe, serotonin (AAL3)", "背側縫核—血清素(AAL3)", False, False),
        "Raphe_M": ("7fc99a", "Median raphe, serotonin (AAL3)", "內側縫核—血清素(AAL3)", False, False),
        "VTA_L":   ("6fb0e0", "Ventral tegmental area, left (AAL3)", "左腹側被蓋區—多巴胺(AAL3)", False, False),
        "VTA_R":   ("6fb0e0", "Ventral tegmental area, right (AAL3)", "右腹側被蓋區—多巴胺(AAL3)", False, False),
    }

    regions_js_parts, manifest, tms = [], {}, {}
    for acr, s in structures.items():
        color = meta[acr][0]
        print(f"  meshing {acr} ({counts[acr]} voxels) ...")
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
    order = list(structures.keys())

    # extent over ALL meshes (brain-only page, ~180000 um)
    extent = max(float(np.ptp(tm.vertices, axis=0).max()) for tm in tms.values())

    # ---- waypoints: schematic + real-mesh anchors ----
    wp = {k: [v["pos"][0] * MM_TO_UM, v["pos"][1] * MM_TO_UM,
              v["pos"][2] * MM_TO_UM, v["r"] * MM_TO_UM]
          for k, v in SCHEMATIC.items()}
    if "LC_R" in tms:
        wp["LC_R"] = hemi_anchor(tms["LC_R"], "right") + [0]
        wp["LC_L"] = hemi_anchor(tms["LC_L"], "left") + [0]
    else:
        for k, v in LC_FALLBACK_SCHEMATIC.items():
            wp[k] = [v["pos"][0] * MM_TO_UM, v["pos"][1] * MM_TO_UM,
                     v["pos"][2] * MM_TO_UM, v["r"] * MM_TO_UM]
    # THAL is bilateral - full centroid lands midline between the lobes,
    # which is where the gate belongs in this story
    wp["THAL"] = tms["THAL"].vertices.mean(axis=0).tolist() + [0]
    real_keys = ["THAL"] + [k for k in ("LC_R", "LC_L") if k in tms]

    pathways = [
        {"id": "aras_thal", "name_key": "aras_thal_name", "desc_key": "aras_thal_desc",
         "color": "0x9a8fe8", "default_checked": True,
         "chains": [["RF", "PPT", "THAL", "CORTEX"]]},
        {"id": "aras_mono", "name_key": "aras_mono_name", "desc_key": "aras_mono_desc",
         "color": "0xe0a458", "default_checked": True,
         "chains": [["LC_R", "BF", "CORTEXm"]]},
        {"id": "vlpo", "name_key": "vlpo_name", "desc_key": "vlpo_desc",
         "color": "0x5a8fe0", "default_checked": False,
         "chains": [["VLPO", "VLPOx", "LC_L"]]},
        {"id": "clock", "name_key": "clock_name", "desc_key": "clock_desc",
         "color": "0x5ac0c0", "default_checked": False,
         "chains": [["Eye", "SCN", "SCNv"]]},
    ]

    legend_meta = [
        {"acr": a, "name_en": meta[a][1], "name_zh": meta[a][2],
         "color": meta[a][0], "outline": meta[a][3], "default_checked": meta[a][4]}
        for a in order
    ]

    html = render_viewer_html({
        "title": "睡眠與覺醒",
        "accent": "9a8fe8",
        "extent": extent,
        "regions_js": regions_js,
        "order": order,
        "strings": STRINGS,
        "legend_meta": legend_meta,
        "pathways": pathways,
        "labels": LABELS,
        "waypoints": wp,
        "real": real_keys,
        "signal": {"pathway": "aras_mono", "color": "0xffd48a", "duration": 2.8},
        "walk": [
            {"key": "walk_0", "color": "#9a8fe8"},
            {"key": "walk_1", "color": "#5a8fe0"},
            {"key": "walk_2", "color": "#5ac0c0"},
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
