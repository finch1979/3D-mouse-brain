"""
Build a self-contained 3D viewer for the human PAIN pathway, foot to
cortex - the first page in this series that leaves the skull, integrating
peripheral nerve -> spinal cord -> brain, plus the spinal withdrawal
reflex and the descending motor command.

Sibling to human_auditory.py / human_visual.py / human_olfactory.py; same
architecture (real atlas meshes + schematic waypoint tubes, hover
leader-line + slice plane, collapsible panels, EN/zh toggle, animated
signal), extended with a scale-compression toggle.

HEADLINE FACT - FOUR MIDLINE CROSSINGS, IN FOUR DIFFERENT PLACES. This is
what the page exists to teach, and why all five pathways belong together:

  pathway                 crosses at                      where
  ----------------------  ------------------------------  ----------------
  Spinothalamic (pain)    anterior white commissure       CORD, within 1-2
                                                          segments of entry
  Crossed extensor        commissural interneurons        CORD, same segment
  DCML (touch/proprio.)   internal arcuate fibers         MEDULLA
  Corticospinal (motor)   pyramidal decussation (~90%)    MEDULLA

Two sensory / two motor x two in the cord / two in the medulla. The
clinical payoff is Brown-Sequard: hemisection of the cord causes
IPSILATERAL loss of touch/proprioception (DCML hasn't crossed yet) but
CONTRALATERAL loss of pain/temperature (spinothalamic already crossed),
beginning ~2 levels below the lesion - and that 2-level offset IS the
1-2 segment decussation delay, so the caveat is the lesson.

Story side: the RIGHT foot steps on a tack. One side only, matching the
one-ear / one-eye / one-nostril convention of the sibling pages. Tracts
are meshed PER SIDE (not merged L+R) because the side is the content.

REAL DATA - unusually, even the spinal cord is real here:
  - Brain: AAL3 via nilearn.datasets.fetch_atlas_aal(version="3v2").
    Verified label indices: Precentral 1/2, Insula 33/34, Postcentral
    61/62, Paracentral_Lobule 73/74, Thal_VPL 129/130, Thal_IL 131/132,
    ACC_sup 155/156. Paracentral_Lobule is the foot/leg sensorimotor
    territory - it is both where the ascending pain terminates and where
    the descending leg motor command originates, which is why no
    Harvard-Oxford mixing is needed.
  - Spinal cord: PAM50 template (De Leener et al., NeuroImage 2018),
    downloaded standalone from the Spinal Cord Toolbox GitHub release -
    no SCT install required. Its NIfTI affine is ALREADY in MNI152
    coordinates (verified: 141x141x991 @ 0.5mm, srow_z offset -561.84,
    so z spans -561.84 to -66.84mm, butting against the MNI brain's
    underside at -72 with ~5mm overlap). So mask_to_mesh() works on it
    unchanged, exactly like every other atlas here. Tract labels used:
    0/1 fasciculus gracilis, 4/5 lateral corticospinal, 12/13 spinal
    lemniscus, 30/31 ventral horn, 34/35 dorsal horn.

SCHEMATIC (no free segmentation exists): skin nociceptor, tibial/sciatic
nerve, dorsal root ganglion, cauda equina, the brainstem relay points
(nucleus gracilis, internal arcuate, pyramidal decussation), the
interneuron pools, the limb muscles, and the body outline.

ACCURACY RULES - these were researched deliberately; do not "simplify"
them back:
  - Say "within 1-2 segments of entry", NEVER "at the level of entry".
    The offset is real, varies (up to 6 segments in thoracic cord), and
    is what produces the clinical 2-level sensory offset.
  - The dorsal horn projection neuron is in LAMINA I / LAMINA V, not the
    substantia gelatinosa (lamina II is predominantly interneurons).
  - The withdrawal reflex is "completed by the cord without the brain" -
    do NOT claim it outruns conscious pain. Human psychophysics does not
    support that. Frame it as PARALLEL circuits, not sequential ones.
  - PAM50 label 12/13 is the ANTEROLATERAL SYSTEM (spinothalamic AND
    spinoreticular), not a pure spinothalamic segmentation.
  - PAM50 is STRAIGHTENED and its brainstem is deformed. Butt-joint it at
    z ~ -70; do not blend it into the MNI brainstem, and do not claim the
    cord's straightness is anatomical.
  - VPM is the FACE nucleus - never a relay on the foot pathway.

Data licensing: AAL3 (Rolls et al. 2020) license unspecified; PAM50 ships
no license file. Free educational use with citation.

Usage:
    python -m human_atlas.build.human_pain
"""

import json
import zipfile

import nibabel as nib
import numpy as np
import requests
import trimesh
from nilearn import datasets
from scipy.ndimage import zoom
from skimage import measure
from trimesh import smoothing

from human_atlas.common.paths import DATA_CACHE_DIR, OUTPUTS_DIR, WEB_LIB_DIR
from human_atlas.render.bake_meshes import mesh_to_region_js

MM_TO_UM = 1000.0
CACHE_DIR = DATA_CACHE_DIR / "human_pain"
AAL_CACHE_DIR = DATA_CACHE_DIR / "human_olfactory"  # AAL3 already lives here
OUT_DIR = OUTPUTS_DIR / "pain_system"
MESH_DIR = OUT_DIR / "mesh"
OUT_FILE = "human_pain_system_3d.html"

PAM50_URL = (
    "https://github.com/spinalcordtoolbox/PAM50/releases/download/"
    "r20250730/PAM50-r20250730.zip"
)
PAM50_ZIP = CACHE_DIR / "PAM50-r20250730.zip"

ROOT_DOWNSAMPLE = 0.35
CORD_DOWNSAMPLE = 0.5
TRACT_THRESHOLD = 0.25  # PAM50 atlas volumes are probabilistic; the tracts are
                        # only 1-4mm wide, so a 0.5 threshold yields slivers

# AAL3 label indices (verified by inspecting the fetched atlas' .indices)
AAL = {
    "M1": [1, 2],                # Precentral
    "INS": [33, 34],             # Insula
    "S1": [61, 62],              # Postcentral
    "FOOT": [73, 74],            # Paracentral_Lobule - foot/leg sensorimotor
    "VPL": [129, 130],           # Thal_VPL
    "ILN": [131, 132],           # Thal_IL (intralaminar - medial pain system)
    "ACC": [155, 156],           # ACC_sup
}
# PAM50 atlas volume ids, per side (see module docstring)
PAM50_TRACTS = {
    "DH_R": 35,    # right dorsal horn - where the foot afferent synapses
    "VH_R": 31,    # right ventral horn - withdrawal motor output
    "VH_L": 30,    # left ventral horn - crossed extensor output
    "STT_L": 12,   # left anterolateral system - AFTER the cord decussation
    "DC_R": 1,     # right fasciculus gracilis - uncrossed touch, for contrast
    "CST_R": 5,    # right lateral corticospinal - AFTER the pyramidal decussation
}

# ---- vertical scale compression -------------------------------------------
# A true-scale figure is ~1700mm tall, of which the brain is ~150mm (9%) and
# the cord decussation is a ~15mm event (<1%). Compress along z ONLY - never
# the cord's transverse geometry, since the dorsal horn -> commissure ->
# contralateral quadrant cross-section is the whole point.
Z_BRAIN_FLOOR = -72.0      # below this, the cord; above, untouched brain
Z_CORD_FLOOR = -545.0      # below this, the leg
CORD_SCALE = 0.40
LEG_SCALE = 0.14


def zc(z):
    """True MNI z (mm) -> compressed-view z (mm). Piecewise-linear, continuous."""
    if z >= Z_BRAIN_FLOOR:
        return z
    if z >= Z_CORD_FLOOR:
        return Z_BRAIN_FLOOR + (z - Z_BRAIN_FLOOR) * CORD_SCALE
    cord_bottom = Z_BRAIN_FLOOR + (Z_CORD_FLOOR - Z_BRAIN_FLOOR) * CORD_SCALE
    return cord_bottom + (z - Z_CORD_FLOOR) * LEG_SCALE


# Schematic waypoints: (x, y, z) in true MNI mm + marker radius mm. Right
# side (x>0) except where the pathway has crossed. See docstring for what is
# real vs schematic.
# The sole sits at z = -1618 so that vertex-to-sole is exactly 1700mm - a
# 170cm adult - measured against the brain mesh's own top (z = +82). That
# figure is also anatomically consistent: it puts the L1 vertebra (z ~ -485)
# 1133mm above the sole, inside the 1130-1160mm reported for adults.
BODY_HEIGHT_MM = 1700
SOLE_Z = -1618.0

SCHEMATIC = {
    "Nocicept":  {"pos": (95, 45, SOLE_Z), "r": 7},
    "Nerve":     {"pos": (92, -5, -1170), "r": 4},
    "DRG":       {"pos": (20, -42, -680), "r": 5},
    "Cauda":     {"pos": (9, -46, -585), "r": 3},
    "Commiss":   {"pos": (0, -45, -458), "r": 2.5},
    "Interneur": {"pos": (5, -44, -466), "r": 2},
    "CommIN":    {"pos": (0, -45, -470), "r": 2},
    "Flexor":    {"pos": (92, -14, -1014), "r": 8},
    "Extensor":  {"pos": (-92, -14, -1014), "r": 8},
    "Brainstem": {"pos": (-5, -34, -34), "r": 3},
    "IntCaps":   {"pos": (-19, -8, 2), "r": 3},
    "Pyramids":  {"pos": (0, -32, -58), "r": 3},
    "NucGrac":   {"pos": (5, -41, -62), "r": 3},
    "IntArc":    {"pos": (0, -38, -50), "r": 2.5},
    "MedLem":    {"pos": (-7, -31, -26), "r": 2.5},
}

LABELS = {
    "Nocicept":  {"en": "① Nociceptor (right sole)", "zh": "① 傷害受器(右腳底)"},
    "Nerve":     {"en": "② Tibial → sciatic nerve", "zh": "② 脛神經→坐骨神經"},
    "DRG":       {"en": "③ S1 dorsal root ganglion (sacral canal)", "zh": "③ S1 背根神經節(薦管內)"},
    "Cauda":     {"en": "④ Cauda equina — ~200mm ascent", "zh": "④ 馬尾—向上約 200mm"},
    "DH_R":      {"en": "⑤ Right dorsal horn — lamina I/V", "zh": "⑤ 右背角—第 I/V 層"},
    "Commiss":   {"en": "⑥ Anterior white commissure — CROSSES (within 1–2 segments)", "zh": "⑥ 前白連合—交叉(1–2 節段內)"},
    "STT_L":     {"en": "⑦ Left anterolateral system", "zh": "⑦ 左前外側系統"},
    "Brainstem": {"en": "brainstem", "zh": "腦幹"},
    "VPL":       {"en": "⑧ Left VPL thalamus", "zh": "⑧ 左腹後外側核(視丘)"},
    "FOOT":      {"en": "⑨a Left paracentral lobule — foot S1", "zh": "⑨a 左中央旁小葉—腳部感覺區"},
    "ILN":       {"en": "⑨b Intralaminar thalamus", "zh": "⑨b 板內核(視丘)"},
    "ACC":       {"en": "⑨c Anterior cingulate — unpleasantness", "zh": "⑨c 前扣帶迴—不適感"},
    "INS":       {"en": "⑨d Insula", "zh": "⑨d 腦島"},
    "Interneur": {"en": "⑩a Interneuron pool (polysynaptic)", "zh": "⑩a 中間神經元(多突觸)"},
    "VH_R":      {"en": "⑪ a Right ventral horn", "zh": "⑪ a 右前角"},
    "Flexor":    {"en": "⑫ a Right flexor — withdraws", "zh": "⑫ a 右屈肌—縮腳"},
    "CommIN":    {"en": "⑩b Commissural interneuron — CROSSES", "zh": "⑩b 連合中間神經元—交叉"},
    "VH_L":      {"en": "⑪ b Left ventral horn", "zh": "⑪ b 左前角"},
    "Extensor":  {"en": "⑫ b Left extensor — supports weight", "zh": "⑫ b 左伸肌—支撐體重"},
    "M1":        {"en": "⑬ Left motor cortex (foot area)", "zh": "⑬ 左運動皮質(腳部區)"},
    "IntCaps":   {"en": "⑭ Internal capsule (posterior limb)", "zh": "⑭ 內囊(後肢)"},
    "Pyramids":  {"en": "⑮ Pyramidal decussation — CROSSES (medulla, ~90%)", "zh": "⑮ 錐體交叉—交叉(延髓,約 90%)"},
    "CST_R":     {"en": "⑯ Right lateral corticospinal tract", "zh": "⑯ 右外側皮質脊髓束"},
    "DC_R":      {"en": "⑰ Right fasciculus gracilis — UNCROSSED", "zh": "⑰ 右薄束—不交叉"},
    "NucGrac":   {"en": "⑱ Nucleus gracilis (medulla)", "zh": "⑱ 薄束核(延髓)"},
    "IntArc":    {"en": "⑲ Internal arcuate fibers — CROSSES (medulla)", "zh": "⑲ 內弓狀纖維—交叉(延髓)"},
    "MedLem":    {"en": "⑳ Medial lemniscus", "zh": "⑳ 內側蹄系"},
}

STRINGS = {
    "eyebrow": {"en": "Human &middot; MNI152 + PAM50 &middot; foot&rarr;cord&rarr;cortex",
                "zh": "人體 &middot; MNI152 + PAM50 &middot; 腳&rarr;脊髓&rarr;皮質"},
    "title_suffix": {"en": '<span class="accent">Pain</span>, <span style="color:var(--accent2)">Reflex</span> &amp; <span style="color:var(--accent3)">Motor</span> Pathways',
                      "zh": '<span class="accent">痛覺</span>、<span style="color:var(--accent2)">反射</span>與<span style="color:var(--accent3)">運動</span>路徑'},
    "subtitle": {
        "en": "A <b>170 cm</b> adult's right foot steps on a tack. The walkthrough below follows what happens <b>one pathway at a time</b> &mdash; the ascending pain route first, in full, naming every nucleus it passes through, and only then the reflex and the descending motor command. Solid meshes are real anatomy (AAL3 brain, PAM50 spinal cord); wireframe spheres are schematic. Only the pain pathway is switched on at first &mdash; reflex, motor, touch and affective layers are checkboxes under <b>Structures</b>. The figure is <b>vertically compressed</b> by default so the crossings are visible; toggle <b>true scale</b> for the real 170 cm body, where the signal covers roughly <b>1.5 metres</b> from sole to cortex.",
        "zh": "一位<b>身高 170 公分</b>的成人,右腳踩到圖釘。下面的說明<b>一條路徑一條路徑地</b>追蹤接下來發生的事&mdash;先完整走完上行痛覺、逐一點出它經過的每一個神經核區,再談反射與下行運動指令。實心網格是真實解剖(AAL3 腦部、PAM50 脊髓);線框球體為示意。畫面一開始只開啟痛覺路徑,反射、運動、觸覺與情緒層都在<b>結構</b>面板裡自行勾選。垂直方向預設<b>壓縮</b>以便看清交叉點;切換<b>真實比例</b>可還原成真正 170 公分的身體,訊號從腳底到皮質實際要走約 <b>1.5 公尺</b>。",
    },
    # "1-4" is the only cue that the panel scrolls past step 1, so keep it.
    "walk_title": {"en": "Pathway walkthrough &nbsp;1&ndash;4", "zh": "路徑逐段說明 &nbsp;1&ndash;4"},
    "pain_walk": {
        "en": (
            '<span class="step-tag">1 &middot; Ascending pain &mdash; three neurons, one crossing, and the crossing is in the cord</span>'
            "<b>First-order neuron.</b> ① A nociceptor in the right sole fires &rarr; ② the tibial and then the sciatic nerve carries it up the leg &rarr; its cell body sits in the ③ <b>S1 dorsal root ganglion</b>, inside the sacral canal &mdash; a ganglion, not a relay, so <b>nothing synapses here</b> &rarr; ④ the axon climbs ~200&nbsp;mm of <b>cauda equina</b> to reach the L4&ndash;S1 cord segments, then runs 1&ndash;2 segments within <b>Lissauer&rsquo;s tract</b>.<br />"
            "<b>First synapse &rarr; second-order neuron.</b> ⑤ <b>Right dorsal horn</b> &mdash; specifically a <b>lamina I / lamina V projection neuron</b>. (Lamina II, the substantia gelatinosa, is mostly interneurons; it modulates, it does not project.)<br />"
            '<span class="cross">Crossing.</span> That axon crosses the ⑥ <b>anterior white commissure</b> <span class="cross">within 1&ndash;2 segments of where it entered</span> and joins the ⑦ <b>left anterolateral system</b> &mdash; spinothalamic together with spinoreticular fibres, which is exactly what the PAM50 label contains.<br />'
            "<b>The long climb.</b> It ascends the cord, medulla, pons and midbrain <b>without another synapse</b>. Collaterals peel off to the reticular formation and periaqueductal grey on the way (not drawn).<br />"
            "<b>Second synapse &rarr; third-order neuron.</b> ⑧ <b>Left VPL nucleus</b> of the thalamus. VPL is body and limb; VPM is face and is never a stop on this route.<br />"
            "<b>Destination.</b> ⑨a <b>Left paracentral lobule</b> &mdash; the foot&rsquo;s S1 territory, on the <b>medial</b> surface of the hemisphere. That is why the foot maps to the top of the brain tucked against the midline, not onto the lateral convexity.<br />"
            "<b>Parallel branch (medial pain system, opt-in).</b> ⑨b <b>intralaminar nuclei</b> &rarr; ⑨c <b>anterior cingulate</b> + ⑨d <b>insula</b> &mdash; how unpleasant it is, running alongside the VPL&rarr;S1 route that carries where and how much."
        ),
        "zh": (
            '<span class="step-tag">1 &middot; 上行痛覺 &mdash; 三個神經元、一個交叉,而交叉發生在脊髓內</span>'
            "<b>第一級神經元。</b>① 右腳底的傷害受器放電 &rarr; ② 訊號沿脛神經、再經坐骨神經上行 &rarr; 細胞本體位於薦管內的 ③ <b>S1 背根神經節</b>&mdash;它是神經節而不是中繼站,<b>這裡不換神經元</b> &rarr; ④ 軸突再沿<b>馬尾</b>上行約 200 公釐,進入 L4&ndash;S1 脊髓節段,並在<b>背外側束(Lissauer 束)</b>內走 1&ndash;2 個節段。<br />"
            "<b>第一個突觸 &rarr; 第二級神經元。</b>⑤ <b>右側背角</b>,確切地說是<b>第 I 層／第 V 層的投射神經元</b>。(第 II 層膠狀質主要是中間神經元,負責調節,並不上行。)<br />"
            '<span class="cross">交叉。</span>此軸突穿過 ⑥ <b>前白連合</b>,<span class="cross">就在進入後 1&ndash;2 個節段內</span>越過中線,加入 ⑦ <b>左側前外側系統</b>&mdash;內含脊髓視丘束與脊髓網狀束,這也正是 PAM50 該標籤實際涵蓋的範圍。<br />'
            "<b>漫長的上行。</b>接著<b>不再換神經元</b>,一路穿過脊髓、延髓、橋腦與中腦。沿途有側枝分出到網狀結構與中腦導水管周圍灰質(未繪出)。<br />"
            "<b>第二個突觸 &rarr; 第三級神經元。</b>⑧ 視丘<b>左側腹後外側核(VPL)</b>。VPL 負責軀幹與四肢,VPM 負責顏面,不會出現在這條路徑上。<br />"
            "<b>終點。</b>⑨a <b>左側中央旁小葉</b>&mdash;腳部的 S1 領域,位在大腦半球的<b>內側面</b>。這就是為什麼腳的感覺區在大腦頂端、貼著中線,而不在外側凸面。<br />"
            "<b>平行分支(內側痛覺系統,需自行開啟)。</b>⑨b <b>板內核</b> &rarr; ⑨c <b>前扣帶迴</b> + ⑨d <b>腦島</b>&mdash;負責「有多不舒服」,與 VPL&rarr;S1 負責的「在哪裡、有多強」平行運作。"
        ),
    },
    "reflex_walk": {
        "en": (
            '<span class="step-tag">2 &middot; Withdrawal reflex &mdash; the cord finishes this one without the brain</span>'
            "Same first-order afferent, a different branch. ⑤ right dorsal horn &rarr; ⑩a <b>interneuron pool</b> &mdash; <b>polysynaptic</b>, at least one interneuron in the middle, unlike the monosynaptic stretch reflex &rarr; ⑪a <b>right ventral horn</b> &alpha;-motor neurons &rarr; ⑫a the right <b>flexors</b> contract and the foot lifts.<br />"
            "At the same moment ⑩b <b>commissural interneurons cross the midline inside the cord</b> &rarr; ⑪b <b>left ventral horn</b> &rarr; ⑫b the left <b>extensors</b> contract to take the body weight, so lifting one foot does not become a fall.<br />"
            "This is a <b>parallel circuit, not a step on the way up</b>: the pain signal is still climbing the cord while this has already finished. The brain is informed, not consulted."
        ),
        "zh": (
            '<span class="step-tag">2 &middot; 縮腳反射 &mdash; 這一段由脊髓自己完成,不需要大腦</span>'
            "同一條第一級傳入纖維,走的是另一條分支。⑤ 右背角 &rarr; ⑩a <b>中間神經元群</b>&mdash;屬於<b>多突觸</b>,中間至少隔一個中間神經元,與單突觸的牽張反射不同 &rarr; ⑪a <b>右前角</b>&alpha;運動神經元 &rarr; ⑫a 右側<b>屈肌</b>收縮,腳抬起。<br />"
            "與此同時,⑩b <b>連合中間神經元在脊髓內越過中線</b> &rarr; ⑪b <b>左前角</b> &rarr; ⑫b 左側<b>伸肌</b>收縮撐住體重,才不會因為抬起一隻腳而跌倒。<br />"
            "這是一條<b>平行迴路,而不是上行途中的一站</b>:反射完成時,痛覺訊號還在脊髓裡往上爬。大腦是被告知,不是被徵詢。"
        ),
    },
    "motor_walk": {
        "en": (
            '<span class="step-tag">3 &middot; Descending motor &mdash; the deliberate move afterwards, crossing in the medulla</span>'
            "⑬ <b>Left motor cortex</b>, foot area on the paracentral lobule &rarr; corona radiata &rarr; ⑭ <b>posterior limb of the internal capsule</b> &rarr; cerebral peduncle &rarr; basis pontis &rarr; the <b>medullary pyramid</b> &rarr; ⑮ <span class=\"cross\">pyramidal decussation, where ~90% of the fibres cross</span> &rarr; ⑯ <b>right lateral corticospinal tract</b> &rarr; ⑪a <b>right ventral horn</b> &alpha;-motor neuron &rarr; muscle.<br />"
            "Note what is <b>missing</b> from that list: there is no relay between cortex and cord. A single corticospinal axon runs the whole way from the cortical cell body down to the ventral horn &mdash; among the longest axons in the body."
        ),
        "zh": (
            '<span class="step-tag">3 &middot; 下行運動 &mdash; 反射之後的自主動作,在延髓交叉</span>'
            "⑬ <b>左側運動皮質</b>(中央旁小葉的腳部區) &rarr; 放射冠 &rarr; ⑭ <b>內囊後肢</b> &rarr; 大腦腳 &rarr; 橋腦基底 &rarr; <b>延髓錐體</b> &rarr; ⑮ <span class=\"cross\">錐體交叉,約 90% 的纖維在此越過中線</span> &rarr; ⑯ <b>右外側皮質脊髓束</b> &rarr; ⑪a <b>右前角</b>&alpha;運動神經元 &rarr; 肌肉。<br />"
            "值得注意的是這串名單裡<b>少了什麼</b>:皮質到脊髓之間沒有中繼站。一條皮質脊髓軸突從皮質細胞本體一路走到前角,是人體最長的軸突之一。"
        ),
    },
    "touch_walk": {
        "en": (
            '<span class="step-tag">4 &middot; Contrast &mdash; touch reaches the same thalamus by a different route</span>'
            "Touch and proprioception from that same sole enter the cord and turn straight upward in ⑰ the <b>right fasciculus gracilis</b>, staying <b>uncrossed for the entire length of the cord</b>. Their first synapse does not come until ⑱ <b>nucleus gracilis</b> in the <b>medulla</b>; only there do ⑲ <b>internal arcuate fibres</b> cross the midline to form the ⑳ <b>medial lemniscus</b>, which ends in the same ⑧ <b>left VPL</b> and then left S1.<br />"
            "So this page&rsquo;s four midline crossings sit in <b>four different places</b>: pain (⑥) and the crossed extensor (⑩b) cross <b>in the cord</b>; touch (⑲) and the motor command (⑮) cross <b>in the medulla</b>. That is why hemisecting the cord (<b>Brown-S&eacute;quard</b>) takes touch and proprioception from <b>one</b> side and pain and temperature from the <b>other</b>, with the pain loss starting about two segments below the lesion &mdash; that offset is precisely the 1&ndash;2 segment delay at ⑥."
        ),
        "zh": (
            '<span class="step-tag">4 &middot; 對照 &mdash; 觸覺以另一條路線抵達同一個視丘核</span>'
            "來自同一隻腳底的觸覺與本體感覺進入脊髓後直接轉往上行,走 ⑰ <b>右側薄束</b>,<b>沿整條脊髓都不交叉</b>。它們的第一個突觸要到<b>延髓</b>的 ⑱ <b>薄束核</b>才發生;也只有在那裡,⑲ <b>內弓狀纖維</b>才越過中線,形成 ⑳ <b>內側蹄系</b>,最後同樣終止於 ⑧ <b>左側 VPL</b>,再到左側 S1。<br />"
            "所以這一頁的四個中線交叉分別落在<b>四個不同位置</b>:痛覺(⑥)與交叉伸肌(⑩b)在<b>脊髓內</b>交叉;觸覺(⑲)與運動指令(⑮)在<b>延髓</b>交叉。這正是脊髓半切(<b>Brown-S&eacute;quard 症候群</b>)會拿走<b>一側</b>的觸覺與本體感覺、<b>另一側</b>的痛溫覺的原因,而痛覺喪失是從病灶下方約兩個節段才開始&mdash;這個落差,正好就是 ⑥ 那 1&ndash;2 個節段的延遲。"
        ),
    },
    "height_note": {"en": "▎subject height 170 cm &middot; sole z = −1618 mm &middot; vertex z = +82 mm",
                     "zh": "▎模型身高 170 公分 &middot; 腳底 z = −1618 mm &middot; 頭頂 z = +82 mm"},
    "hover_title": {"en": "Hovered structure", "zh": "目前指向的結構"},
    "structures_title": {"en": "Structures", "zh": "結構"},
    "legend_note": {"en": "Dashed swatch / wireframe sphere = schematic node, not a real segmented structure. Click &quot;Structures&quot; to collapse this panel.",
                     "zh": "虛線色塊／線框球體＝示意節點,並非真實分割出的解剖構造。點擊「結構」可收合此面板。"},
    "pain_name": {"en": "Ascending pain", "zh": "上行痛覺"},
    "pain_desc": {"en": "foot &rarr; dorsal horn &rarr; CROSSES in cord &rarr; VPL &rarr; S1", "zh": "腳&rarr;背角&rarr;脊髓內交叉&rarr;VPL&rarr;S1"},
    "reflex_name": {"en": "Withdrawal reflex", "zh": "縮腳反射"},
    "reflex_desc": {"en": "cord-only arc, + crossed extensor for balance", "zh": "純脊髓迴路,+交叉伸肌維持平衡"},
    "motor_name": {"en": "Descending motor", "zh": "下行運動"},
    "motor_desc": {"en": "M1 &rarr; CROSSES at pyramids &rarr; ventral horn &rarr; muscle", "zh": "M1&rarr;錐體交叉&rarr;前角&rarr;肌肉"},
    "touch_name": {"en": "Touch contrast (DCML)", "zh": "觸覺對比(背柱)"},
    "touch_desc": {"en": "uncrossed in cord, CROSSES in medulla &mdash; same VPL", "zh": "脊髓內不交叉,延髓才交叉&mdash;同樣到 VPL"},
    "affect_name": {"en": "Medial pain system", "zh": "內側痛覺系統"},
    "affect_desc": {"en": "the unpleasantness: intralaminar &rarr; ACC + insula", "zh": "不適感:板內核&rarr;前扣帶迴+腦島"},
    "signal_name": {"en": "Neural signal", "zh": "神經訊號"},
    "signal_desc": {"en": "animated pain pulse, foot &rarr; cortex", "zh": "動畫痛覺訊號,腳&rarr;皮質"},
    "scale_name": {"en": "True scale", "zh": "真實比例"},
    "scale_desc": {"en": "un-compress to a real 170 cm body", "zh": "還原成真實 170 公分的身體"},
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
    """Download + extract the PAM50 release once. Returns (atlas_dir, template_dir)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not PAM50_ZIP.exists():
        print(f"Downloading PAM50 ({PAM50_URL}) ...")
        r = requests.get(PAM50_URL, timeout=900, stream=True)
        r.raise_for_status()
        with open(PAM50_ZIP, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    # the zip expands into a hash-suffixed dir, so glob rather than hardcode
    template = next(CACHE_DIR.glob("**/template/PAM50_cord.nii.gz"), None)
    if template is None:
        print("Extracting PAM50 ...")
        with zipfile.ZipFile(PAM50_ZIP) as z:
            z.extractall(CACHE_DIR)
        template = next(CACHE_DIR.glob("**/template/PAM50_cord.nii.gz"), None)
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
    """Mean vertex of one hemisphere's blob (um). Bilateral meshes otherwise
    collapse to a midline point floating between the two halves."""
    v = tm.vertices
    sel = v[v[:, 0] > 0] if side == "right" else v[v[:, 0] < 0]
    return (sel.mean(axis=0) if len(sel) else tm.centroid).tolist()


def tract_anchor(tm, z_mm, side, window=8.0):
    """A point ON a full-length cord tract at a given spinal height.

    The PAM50 tract masks run the entire cord, so a plain centroid lands at
    mid-cord rather than at the spinal level the pathway actually uses.
    Sample a z-slab instead so the drawn tube follows the real tract."""
    v = tm.vertices
    z = z_mm * MM_TO_UM
    w = window * MM_TO_UM
    sel = v[(np.abs(v[:, 2] - z) < w) & ((v[:, 0] > 0) if side == "right" else (v[:, 0] < 0))]
    if not len(sel):  # outside the tract's z coverage - fall back to nearest end
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
    }
    for acr, ids in AAL.items():
        structures[acr] = {
            "mask": np.isin(aal_data, ids), "affine": aal_img.affine,
            "downsample": 1.0, "smooth": 15, "color": "888888", "name": acr,
        }

    cord_img = nib.load(str(template_dir / "PAM50_cord.nii.gz"))
    structures["cord"] = {
        "mask": cord_img.get_fdata() > 0.5, "affine": cord_img.affine,
        "downsample": CORD_DOWNSAMPLE, "smooth": 5,
        "color": "BBBBBB", "name": "Spinal cord outline (PAM50)",
    }
    for acr, lid in PAM50_TRACTS.items():
        img = nib.load(str(atlas_dir / f"PAM50_atlas_{lid:02d}.nii.gz"))
        structures[acr] = {
            "mask": img.get_fdata() > TRACT_THRESHOLD, "affine": img.affine,
            "downsample": 1.0, "smooth": 8, "color": "888888", "name": acr,
        }

    # per-structure display metadata (colour + bilingual name + outline? + default on?)
    # Defaults deliberately show ONLY the ascending pain story - root, cord,
    # DH_R, STT_L, VPL, FOOT. Five pathways at once is unreadable; the reflex,
    # motor, touch and affective layers are opt-in. Don't switch them back on.
    meta = {
        "root":  ("CCCCCC", "Whole-brain outline (MNI152)", "全腦輪廓(MNI152)", True, True),
        "cord":  ("BBBBBB", "Spinal cord outline (PAM50)", "脊髓輪廓(PAM50)", True, True),
        "FOOT":  ("E0705A", "Paracentral lobule — foot sensorimotor", "中央旁小葉—腳部感覺運動區", False, True),
        "VPL":   ("E0A458", "VPL thalamus (AAL3)", "腹後外側核(AAL3)", False, True),
        "DH_R":  ("E0705A", "Right dorsal horn (PAM50)", "右背角(PAM50)", False, True),
        "STT_L": ("E0705A", "Left anterolateral system (PAM50)", "左前外側系統(PAM50)", False, True),
        "VH_R":  ("7FC99A", "Right ventral horn (PAM50)", "右前角(PAM50)", False, False),
        "VH_L":  ("7FC99A", "Left ventral horn (PAM50)", "左前角(PAM50)", False, False),
        "CST_R": ("6FB0E0", "Right lateral corticospinal tract (PAM50)", "右外側皮質脊髓束(PAM50)", False, False),
        "M1":    ("6FB0E0", "Precentral gyrus / M1 (AAL3)", "中央前迴／M1(AAL3)", False, False),
        "S1":    ("D0A0A0", "Postcentral gyrus / S1 (AAL3)", "中央後迴／S1(AAL3)", False, False),
        "DC_R":  ("C9A8FF", "Right fasciculus gracilis (PAM50)", "右薄束(PAM50)", False, False),
        "ILN":   ("D094D9", "Intralaminar thalamus (AAL3)", "板內核(AAL3)", False, False),
        "ACC":   ("D094D9", "Anterior cingulate, supracallosal (AAL3)", "前扣帶迴上部(AAL3)", False, False),
        "INS":   ("D094D9", "Insula (AAL3)", "腦島(AAL3)", False, False),
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

    # --- spatial-join check: the cord must abut the brain, not float away ---
    cord_top = float(tms["cord"].vertices[:, 2].max()) / MM_TO_UM
    brain_bot = float(tms["root"].vertices[:, 2].min()) / MM_TO_UM
    gap = brain_bot - cord_top
    print(f"\n  spatial join: cord z-max={cord_top:.2f}mm, brain z-min={brain_bot:.2f}mm, gap={gap:.2f}mm")
    if gap > 2.0:
        raise RuntimeError(f"cord and brain do not abut (gap {gap:.2f}mm) - affine mismatch")
    print("  join OK (abut/overlap)\n")

    (MESH_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    regions_js = "{" + ",".join(regions_js_parts) + "}"
    order = ["root", "cord"] + [a for a in meta if a not in ("root", "cord")]

    # ---- waypoints, in BOTH true and compressed z, so the toggle is a lerp ---
    S1_ENTRY_Z = -470.0   # S1 cord segment (behind the T12/L1 vertebra)
    wp_true = {}
    for k, v in SCHEMATIC.items():
        x, y, z = v["pos"]
        wp_true[k] = [x * MM_TO_UM, y * MM_TO_UM, z * MM_TO_UM, v["r"] * MM_TO_UM]

    # real-mesh endpoints. Cord tracts are sampled at the spinal level the
    # pathway actually uses; brain structures use a hemisphere mean.
    wp_true["DH_R"] = tract_anchor(tms["DH_R"], S1_ENTRY_Z, "right") + [0]
    wp_true["VH_R"] = tract_anchor(tms["VH_R"], S1_ENTRY_Z - 4, "right") + [0]
    wp_true["VH_L"] = tract_anchor(tms["VH_L"], S1_ENTRY_Z - 4, "left") + [0]
    wp_true["FOOT"] = hemi_anchor(tms["FOOT"], "left") + [0]
    wp_true["M1"] = hemi_anchor(tms["M1"], "left") + [0]
    wp_true["VPL"] = hemi_anchor(tms["VPL"], "left") + [0]
    wp_true["ILN"] = hemi_anchor(tms["ILN"], "left") + [0]
    wp_true["ACC"] = hemi_anchor(tms["ACC"], "left") + [0]
    wp_true["INS"] = hemi_anchor(tms["INS"], "left") + [0]
    # intermediate points ALONG each long cord tract, so the tube follows it
    stt_levels, dc_levels, cst_levels = [], [], []
    for i, z in enumerate([-450, -370, -290, -210, -130, -75]):
        k = f"STT_L{i}"
        wp_true[k] = tract_anchor(tms["STT_L"], z, "left") + [0]
        stt_levels.append(k)
        k = f"DC_R{i}"
        wp_true[k] = tract_anchor(tms["DC_R"], z, "right") + [0]
        dc_levels.append(k)
    for i, z in enumerate([-80, -160, -250, -340, -430]):
        k = f"CST_R{i}"
        wp_true[k] = tract_anchor(tms["CST_R"], z, "right") + [0]
        cst_levels.append(k)
    # the labelled tract nodes sit mid-tract
    wp_true["STT_L"] = tract_anchor(tms["STT_L"], -300, "left") + [0]
    wp_true["DC_R"] = tract_anchor(tms["DC_R"], -300, "right") + [0]
    wp_true["CST_R"] = tract_anchor(tms["CST_R"], -300, "right") + [0]

    wp_comp = {k: [v[0], v[1], zc(v[2] / MM_TO_UM) * MM_TO_UM, v[3]] for k, v in wp_true.items()}

    # ---- pathway definitions: (orderedKeys, labelKeys) --------------------
    pain_order = (["Nocicept", "Nerve", "DRG", "Cauda", "DH_R", "Commiss"]
                  + stt_levels + ["Brainstem", "VPL", "FOOT"])
    pain_labels = ["Nocicept", "Nerve", "DRG", "Cauda", "DH_R", "Commiss", "VPL", "FOOT"]
    affect_order = ["VPL", "ILN", "ACC", "INS"]
    reflex_ipsi = ["DH_R", "Interneur", "VH_R", "Flexor"]
    reflex_cross = ["DH_R", "CommIN", "VH_L", "Extensor"]
    motor_order = ["M1", "IntCaps", "Pyramids"] + cst_levels + ["VH_R", "Flexor"]
    motor_labels = ["M1", "IntCaps", "Pyramids", "CST_R"]
    touch_order = ["Nocicept", "Nerve", "DRG", "Cauda"] + dc_levels + ["NucGrac", "IntArc", "MedLem", "VPL"]
    touch_labels = ["DC_R", "NucGrac", "IntArc", "MedLem"]

    real_keys = ["DH_R", "VH_R", "VH_L", "STT_L", "DC_R", "CST_R",
                 "FOOT", "M1", "VPL", "ILN", "ACC", "INS"] + stt_levels + dc_levels + cst_levels

    legend_meta = [
        {"acr": a, "name_en": meta[a][1], "name_zh": meta[a][2],
         "color": meta[a][0], "outline": meta[a][3], "default_checked": meta[a][4]}
        for a in order
    ]

    three_js = (WEB_LIB_DIR / "three.min.js").read_text(encoding="utf-8")
    orbit_js = (WEB_LIB_DIR / "OrbitControls.js").read_text(encoding="utf-8")

    html = TEMPLATE.format(
        three_js=three_js,
        orbit_js=orbit_js,
        extent=float(np.ptp(tms["root"].vertices, axis=0).max()),
        regions_js=regions_js,
        order_js=json.dumps(order),
        strings_json=json.dumps(STRINGS, ensure_ascii=False),
        legend_meta_json=json.dumps(legend_meta, ensure_ascii=False),
        wp_true_json=json.dumps(wp_true),
        wp_comp_json=json.dumps(wp_comp),
        labels_json=json.dumps(LABELS, ensure_ascii=False),
        real_json=json.dumps(real_keys),
        pain_order_json=json.dumps(pain_order),
        pain_labels_json=json.dumps(pain_labels),
        affect_order_json=json.dumps(affect_order),
        reflex_ipsi_json=json.dumps(reflex_ipsi),
        reflex_cross_json=json.dumps(reflex_cross),
        motor_order_json=json.dumps(motor_order),
        motor_labels_json=json.dumps(motor_labels),
        touch_order_json=json.dumps(touch_order),
        touch_labels_json=json.dumps(touch_labels),
        cord_scale=CORD_SCALE,
        cord_offset=(Z_BRAIN_FLOOR * (1 - CORD_SCALE)) * MM_TO_UM,
        cord_floor=Z_CORD_FLOOR * MM_TO_UM,
        brain_floor=Z_BRAIN_FLOOR * MM_TO_UM,
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


TEMPLATE = """<title>痛覺系統</title>
<style>
  :root {{
    --bg: #12151a;
    --panel: rgba(27, 32, 40, 0.86);
    --panel-border: #2b323d;
    --text: #e9edf1;
    --text-dim: #8b96a3;
    --text-faint: #5c6672;
    --accent: #e0705a;
    --accent2: #7fc99a;
    --accent3: #6fb0e0;
    --mono: ui-monospace, "Cascadia Code", "SF Mono", "JetBrains Mono", Consolas, "Liberation Mono", monospace;
    --sans: -apple-system, "Segoe UI", system-ui, Roboto, sans-serif;
  }}

  * {{ box-sizing: border-box; }}

  html, body {{
    margin: 0; padding: 0; width: 100%; height: 100%;
    background: var(--bg); color: var(--text);
    font-family: var(--sans); overflow: hidden;
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
    font-family: var(--mono); font-size: 11px;
    letter-spacing: 0.14em; text-transform: uppercase; color: var(--text-faint);
  }}

  h1 {{
    margin: 0; font-family: var(--mono); font-weight: 600;
    font-size: clamp(20px, 2.6vw, 30px);
    letter-spacing: 0.01em; text-wrap: balance; color: var(--text);
  }}

  h1 .accent {{ color: var(--accent); }}

  .subtitle {{ font-size: 12.5px; color: var(--text-dim); max-width: 54ch; line-height: 1.55; }}

  .height-note {{
    font-family: var(--mono); font-size: 11px; color: var(--accent);
    letter-spacing: 0.06em; margin-top: 6px;
  }}

  /* The pathway walkthrough is long-form reading, so it gets a panel of its
     own rather than living in the subtitle: pointer-events on (it scrolls),
     and it auto-collapses when the legend is opened - both live left. */
  .walk {{
    align-self: flex-start; margin-top: 12px; padding: 9px 14px 11px;
    width: min(460px, 40vw); pointer-events: auto;
    display: flex; flex-direction: column;
  }}

  .walk-title {{
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
    font-family: var(--mono); font-size: 10px; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--text-faint);
    cursor: pointer; user-select: none;
  }}

  .walk-title .chevron {{ font-size: 12px; transition: transform 0.15s ease; }}
  .walk.collapsed .walk-body {{ display: none; }}
  .walk.collapsed .walk-title .chevron {{ transform: rotate(-90deg); }}

  .walk-body {{
    display: flex; flex-direction: column; gap: 14px;
    margin-top: 10px; padding-right: 4px;
    max-height: min(54vh, 470px); overflow-y: auto;
  }}

  .step {{
    border-left: 2px solid var(--panel-border); padding: 1px 0 1px 11px;
    font-size: 11.5px; line-height: 1.65; color: var(--text-dim);
  }}

  .step b {{ color: var(--text); font-weight: 600; }}
  .step .cross {{ color: var(--accent); font-weight: 600; }}

  .step-tag {{
    display: block; font-family: var(--mono); font-size: 11px;
    letter-spacing: 0.03em; line-height: 1.4; margin-bottom: 5px;
  }}

  .step--pain {{ border-left-color: #e0705a; }}
  .step--pain .step-tag {{ color: #e0705a; }}
  .step--reflex {{ border-left-color: #7fc99a; }}
  .step--reflex .step-tag {{ color: #7fc99a; }}
  .step--motor {{ border-left-color: #6fb0e0; }}
  .step--motor .step-tag {{ color: #6fb0e0; }}
  .step--touch {{ border-left-color: #c9a8ff; }}
  .step--touch .step-tag {{ color: #c9a8ff; }}

  .panel {{
    pointer-events: auto; background: var(--panel);
    border: 1px solid var(--panel-border);
    backdrop-filter: blur(10px); border-radius: 10px;
  }}

  .legend {{
    left: 24px; bottom: 24px; padding: 10px 14px;
    display: flex; flex-direction: column; gap: 2px;
    min-width: 230px; max-width: 280px; max-height: min(70vh, 620px);
  }}

  .legend-title {{
    font-family: var(--mono); font-size: 10px;
    letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--text-faint); padding: 4px 2px 8px;
  }}

  .legend-title--toggle {{
    display: flex; align-items: center; justify-content: space-between;
    cursor: pointer; user-select: none;
  }}

  .legend-title--toggle .chevron {{ font-size: 12px; transition: transform 0.15s ease; }}

  .legend-body {{ display: flex; flex-direction: column; gap: 2px; overflow-y: auto; }}

  .legend.collapsed .legend-body {{ display: none; }}
  .legend.collapsed .legend-title .chevron {{ transform: rotate(-90deg); }}
  .legend.collapsed {{ max-height: none; }}

  .legend-row {{
    display: flex; align-items: center; gap: 10px;
    padding: 7px 6px; border-radius: 6px; cursor: pointer;
    transition: background 0.15s ease;
  }}

  .legend-row:hover {{ background: rgba(255, 255, 255, 0.045); }}

  .legend-row input {{
    appearance: none; width: 13px; height: 13px;
    border: 1.5px solid var(--text-faint); border-radius: 3px;
    margin: 0; flex: none; position: relative; cursor: pointer;
  }}

  .legend-row input:checked {{ border-color: var(--accent); background: var(--accent); }}

  .legend-row input:checked::after {{
    content: ""; position: absolute; left: 3px; top: 0px;
    width: 3px; height: 7px; border: solid #12151a;
    border-width: 0 1.6px 1.6px 0; transform: rotate(40deg);
  }}

  .swatch {{
    width: 12px; height: 12px; border-radius: 3px;
    background: var(--swatch); flex: none;
    box-shadow: 0 0 8px color-mix(in srgb, var(--swatch) 65%, transparent);
  }}

  .swatch--outline {{ background: transparent; border: 1.5px solid var(--text-faint); box-shadow: none; }}

  .legend-text {{ display: flex; flex-direction: column; line-height: 1.25; }}
  .legend-acr {{ font-family: var(--mono); font-size: 12.5px; color: var(--text); }}
  .legend-name {{ font-size: 11px; color: var(--text-dim); }}

  .legend-row--outline {{ margin-top: 4px; border-top: 1px solid var(--panel-border); padding-top: 10px; }}

  .legend-note {{
    font-size: 10.5px; color: var(--text-faint);
    padding: 8px 6px 0; line-height: 1.5;
    border-top: 1px solid var(--panel-border); margin-top: 4px;
  }}

  .lang-toggle {{
    right: 24px; top: 20px; padding: 8px 16px;
    font-family: var(--mono); font-size: 12px; letter-spacing: 0.04em;
    color: var(--text); cursor: pointer; z-index: 11;
  }}

  .lang-toggle:hover {{ border-color: var(--accent); color: var(--accent); }}

  .hover-info {{ right: 24px; top: 132px; padding: 12px 14px; max-width: 250px; display: none; }}
  .hover-info.show {{ display: block; }}
  .hover-label {{ font-size: 13px; color: var(--text); line-height: 1.4; }}

  .hint {{
    right: 24px; bottom: 24px; padding: 10px 14px;
    font-family: var(--mono); font-size: 10.5px; color: var(--text-faint);
    text-align: right; line-height: 1.6; letter-spacing: 0.01em; max-width: 330px;
  }}

  .hint-title--toggle {{
    display: flex; align-items: center; justify-content: flex-end; gap: 8px;
    cursor: pointer; user-select: none; text-transform: uppercase;
    letter-spacing: 0.12em; font-size: 10px;
  }}

  .hint-title--toggle .chevron {{ font-size: 12px; transition: transform 0.15s ease; }}
  .hint-body {{ padding-top: 8px; }}
  .hint.collapsed .hint-body {{ display: none; }}
  .hint.collapsed .hint-title--toggle .chevron {{ transform: rotate(-90deg); }}
  .hint b {{ color: var(--text-dim); font-weight: 500; }}

  .loading {{
    position: fixed; inset: 0;
    display: flex; align-items: center; justify-content: center;
    font-family: var(--mono); font-size: 12px;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--text-faint); z-index: 20; background: var(--bg);
    transition: opacity 0.4s ease;
  }}

  .loading.hidden {{ opacity: 0; pointer-events: none; }}

  @media (prefers-reduced-motion: reduce) {{ .loading {{ transition: none; }} }}
</style>

<div id="scene"></div>
<div class="loading" id="loading">Loading meshes&hellip;</div>

<button class="panel lang-toggle ui" id="langToggle" type="button">中文</button>

<header class="ui">
  <span class="eyebrow" id="txtEyebrow">Human &middot; MNI152 + PAM50 &middot; foot&rarr;cord&rarr;cortex</span>
  <h1>痛覺系統 <span id="txtTitleSuffix"><span class="accent">Pain</span>, <span style="color:var(--accent2)">Reflex</span> &amp; <span style="color:var(--accent3)">Motor</span> Pathways</span></h1>
  <span class="subtitle" id="txtSubtitle"></span>
  <span class="height-note" id="txtHeightNote"></span>
  <div class="panel walk" id="walkPanel">
    <div class="walk-title" id="walkToggle">
      <span id="txtWalkTitle">Pathway walkthrough</span>
      <span class="chevron">&#9660;</span>
    </div>
    <div class="walk-body" id="walkBody">
      <div class="step step--pain" id="txtPainWalk"></div>
      <div class="step step--reflex" id="txtReflexWalk"></div>
      <div class="step step--motor" id="txtMotorWalk"></div>
      <div class="step step--touch" id="txtTouchWalk"></div>
    </div>
  </div>
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
    <label class="legend-row legend-row--outline" data-acr="pain">
      <input type="checkbox" id="painToggle" checked />
      <span class="swatch" style="--swatch:#e0705a"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtPainName">Ascending pain</span>
        <span class="legend-name" id="txtPainDesc"></span>
      </span>
    </label>
    <label class="legend-row" data-acr="reflex">
      <input type="checkbox" id="reflexToggle" />
      <span class="swatch" style="--swatch:#7fc99a"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtReflexName">Withdrawal reflex</span>
        <span class="legend-name" id="txtReflexDesc"></span>
      </span>
    </label>
    <label class="legend-row" data-acr="motor">
      <input type="checkbox" id="motorToggle" />
      <span class="swatch" style="--swatch:#6fb0e0"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtMotorName">Descending motor</span>
        <span class="legend-name" id="txtMotorDesc"></span>
      </span>
    </label>
    <label class="legend-row" data-acr="touch">
      <input type="checkbox" id="touchToggle" />
      <span class="swatch" style="--swatch:#c9a8ff"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtTouchName">Touch contrast (DCML)</span>
        <span class="legend-name" id="txtTouchDesc"></span>
      </span>
    </label>
    <label class="legend-row" data-acr="affect">
      <input type="checkbox" id="affectToggle" />
      <span class="swatch" style="--swatch:#d094d9"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtAffectName">Medial pain system</span>
        <span class="legend-name" id="txtAffectDesc"></span>
      </span>
    </label>
    <label class="legend-row legend-row--outline" data-acr="signal">
      <input type="checkbox" id="signalToggle" checked />
      <span class="swatch" style="--swatch:#ffd48a"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtSignalName">Neural signal</span>
        <span class="legend-name" id="txtSignalDesc"></span>
      </span>
    </label>
    <label class="legend-row" data-acr="scale">
      <input type="checkbox" id="scaleToggle" />
      <span class="swatch swatch--outline"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtScaleName">True scale</span>
        <span class="legend-name" id="txtScaleDesc"></span>
      </span>
    </label>
    <div class="legend-note" id="txtLegendNote"></div>
  </div>
</div>

<div class="panel hint ui collapsed" id="hintPanel">
  <div class="hint-title--toggle" id="hintToggle">
    <span id="txtControlsTitle">Controls</span>
    <span class="chevron">&#9660;</span>
  </div>
  <div class="hint-body" id="hintBody">
    <span id="txtHintControls"></span><br />
    <span id="txtHintUnits"></span>
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

  const CORD_SCALE = {cord_scale};
  const CORD_OFFSET = {cord_offset};
  const BRAIN_FLOOR = {brain_floor};

  const scene = new THREE.Scene();
  const FOV = 40;
  const camera = new THREE.PerspectiveCamera(FOV, window.innerWidth / window.innerHeight, 1, EXTENT * 60);
  // MNI152 RAS: x=Right+, y=Anterior+, z=Superior+. Unlike the sibling
  // brain-only pages, the subject here is a whole figure ~11x taller than
  // the brain, and it changes height when the scale toggles - so framing is
  // computed from the figure, not from EXTENT, and re-fits on toggle.
  camera.position.set(EXTENT * 1.4, EXTENT * 3.6, -EXTENT * 0.6);
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
  controls.minDistance = EXTENT * 0.1;
  // must clear the true-scale framing distance (~3150mm for a 1700mm figure
  // at this FOV) or controls.update() silently clamps the camera and the
  // figure gets cropped when the scale toggle expands it
  controls.maxDistance = EXTENT * 40;
  controls.autoRotate = !reduceMotion;
  controls.autoRotateSpeed = 0.5;
  controls.addEventListener("start", () => {{ controls.autoRotate = false; }});
  controls.target.set(0, 0, -EXTENT * 0.9); // refined by frameScene() below

  scene.add(new THREE.HemisphereLight(0xaebfd4, 0x14171c, 0.6));
  const key = new THREE.DirectionalLight(0xffffff, 0.85);
  key.position.set(EXTENT * 0.6, EXTENT * 0.9, EXTENT * 0.7);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0x8fb4ff, 0.3);
  fill.position.set(-EXTENT * 0.7, -EXTENT * 0.2, -EXTENT * 0.5);
  scene.add(fill);

  const STRINGS = {strings_json};
  let LANG = "en";

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
    const mat = new THREE.SpriteMaterial({{ map: tex, depthTest: false, depthWrite: false, transparent: true, opacity: 0.92 }});
    const sprite = new THREE.Sprite(mat);
    sprite.scale.set(scaleH * (canvas.width / canvas.height), scaleH, 1);
    sprite.renderOrder = renderOrder;
    sprite.userData = {{ fontPx, color, aspect: canvas.width / canvas.height }};
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
    sprite.userData.aspect = canvas.width / canvas.height;
    const scaleH = sprite.scale.y;
    sprite.scale.set(scaleH * sprite.userData.aspect, scaleH, 1);
  }}

  // This page spans a ~100x zoom range (a 1700mm figure down to a 15mm
  // decussation), so world-sized label sprites are either invisible or
  // enormous. Rescale them every frame to a roughly constant on-screen
  // size instead.
  function updateLabelScales() {{
    HOVER_NODES.forEach((n) => {{
      const s = n.labelSprite;
      const h = camera.position.distanceTo(s.position) * 0.017;
      s.scale.set(h * s.userData.aspect, h, 1);
    }});
    AXIS_SPRITES.forEach(({{ sprite }}) => {{
      const h = camera.position.distanceTo(sprite.position) * 0.028;
      sprite.scale.set(h * sprite.userData.aspect, h, 1);
    }});
  }}

  const LEGEND_META = {legend_meta_json};
  const legendDefaults = {{}};
  LEGEND_META.forEach((m) => {{ legendDefaults[m.acr] = m.default_checked; }});

  // Brain meshes stay put; cord meshes live in a group whose z is squashed
  // in the compressed view. Every PAM50 structure sits wholly inside the
  // cord's z range, so one uniform (scale, offset) is exact for all of them.
  const CORD_ACRS = new Set(["cord", "DH_R", "VH_R", "VH_L", "STT_L", "DC_R", "CST_R"]);
  const cordGroup = new THREE.Group();
  scene.add(cordGroup);

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
    if (acr === "root" || acr === "cord") {{
      mat = new THREE.MeshStandardMaterial({{
        color: acr === "root" ? 0x7c8b99 : 0x9aa6b2,
        transparent: true, opacity: acr === "root" ? 0.09 : 0.14,
        side: THREE.BackSide, depthWrite: false, roughness: 1,
      }});
      mesh = new THREE.Mesh(geom, mat);
      mesh.renderOrder = 10;
    }} else {{
      mat = new THREE.MeshStandardMaterial({{ color: parseInt(s.color, 16), roughness: 0.45, metalness: 0.05 }});
      mesh = new THREE.Mesh(geom, mat);
    }}
    mesh.visible = !!legendDefaults[acr];
    (CORD_ACRS.has(acr) ? cordGroup : scene).add(mesh);
    meshes[acr] = mesh;
  }});

  // Walkthrough and legend both occupy the left edge and are both tall, so
  // opening one collapses the other instead of letting them overlap.
  const walkPanel = document.getElementById("walkPanel");
  const legendPanel = document.getElementById("legendPanel");
  document.getElementById("legendToggle").addEventListener("click", () => {{
    legendPanel.classList.toggle("collapsed");
    if (!legendPanel.classList.contains("collapsed")) walkPanel.classList.add("collapsed");
  }});
  document.getElementById("walkToggle").addEventListener("click", () => {{
    walkPanel.classList.toggle("collapsed");
    if (!walkPanel.classList.contains("collapsed")) legendPanel.classList.add("collapsed");
  }});
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

  const AXIS_SPRITES = [];
  (function addAxisLabels() {{
    const A = EXTENT * 0.7, S = EXTENT * 0.55, R = EXTENT * 0.62;
    const specs = [
      {{ key: "anterior", pos: [0, A, 0] }},
      {{ key: "posterior", pos: [0, -A, 0] }},
      {{ key: "superior", pos: [0, 0, S] }},
      {{ key: "right_axis", pos: [R, 0, 0] }},
    ];
    specs.forEach(({{ key, pos }}) => {{
      const sprite = makeTextSprite(STRINGS[key][LANG], "#f2f4f7", 72, EXTENT * 0.08, 999);
      sprite.position.set(...pos);
      scene.add(sprite);
      AXIS_SPRITES.push({{ sprite, key }});
    }});
  }})();

  // ---- waypoints in both scales; SCALE_T lerps 0(compressed)..1(true) ----
  const WP_TRUE = {wp_true_json};
  const WP_COMP = {wp_comp_json};
  const LABELS = {labels_json};
  const REAL = {real_json};
  let SCALE_T = 0;

  function wpAt(key, t) {{
    const a = WP_COMP[key], b = WP_TRUE[key];
    return [a[0], a[1], a[2] + (b[2] - a[2]) * t, a[3]];
  }}

  const HOVER_NODES = [];
  let hoveredNode = null;
  const PATHS = [];

  // The figure spans from the sole up to the vertex, and that span changes
  // when the scale toggles - so label size, tube radius and camera distance
  // are all derived from it rather than from the brain's EXTENT.
  meshes.root.geometry.computeBoundingBox();
  const BRAIN_TOP = meshes.root.geometry.boundingBox.max.z;
  function figureHeight() {{ return BRAIN_TOP - wpAt("Nocicept", SCALE_T)[2]; }}
  function labelH() {{ return figureHeight() * 0.021; }}
  function tubeR() {{ return figureHeight() * 0.0035; }}

  // Re-fit the camera to the whole figure, keeping whatever direction the
  // user is currently orbiting from. Called at load and on every scale
  // toggle frame, so the figure stays framed as it grows/shrinks.
  function frameScene() {{
    const foot = wpAt("Nocicept", SCALE_T)[2];
    const h = BRAIN_TOP - foot;
    // generous margin: node labels stick out well past the pathway endpoints
    const dist = (h * 0.5) / Math.tan((FOV * Math.PI / 180) * 0.5) * 1.35;
    const dir = camera.position.clone().sub(controls.target);
    if (dir.lengthSq() === 0) dir.set(0.35, 0.9, 0.12);
    dir.normalize();
    controls.target.set(0, 0, (BRAIN_TOP + foot) * 0.5);
    camera.position.copy(controls.target).add(dir.multiplyScalar(dist));
    controls.update();
  }}

  // labelKeys: which nodes get a label/marker/hit-sphere. Branches share long
  // trunks, so each curve is drawn full-length (the signal must sweep it all)
  // but only one branch labels the shared part.
  function buildPathway(orderedKeys, labelKeys, color, tubeR) {{
    const group = new THREE.Group();
    const realSet = new Set(REAL);
    const labelSet = new Set(labelKeys);
    const colorHex = "#" + color.toString(16).padStart(6, "0");

    const tubeMat = new THREE.MeshStandardMaterial({{
      color, emissive: color, emissiveIntensity: 0.4, roughness: 0.4, metalness: 0.1,
    }});
    const tube = new THREE.Mesh(new THREE.BufferGeometry(), tubeMat);
    group.add(tube);

    const nodes = [];
    orderedKeys.forEach((key, i) => {{
      if (!labelSet.has(key)) return;
      const p = wpAt(key, SCALE_T);
      const isReal = realSet.has(key);
      let marker = null;
      if (!isReal) {{
        marker = new THREE.Mesh(
          new THREE.SphereGeometry(p[3] || EXTENT * 0.01, 14, 14),
          new THREE.MeshBasicMaterial({{ color, wireframe: true, transparent: true, opacity: 0.85 }})
        );
        group.add(marker);
      }}
      const label = makeTextSprite(LABELS[key][LANG], colorHex, 52, labelH(), 998);
      group.add(label);
      const hit = new THREE.Mesh(
        new THREE.SphereGeometry(Math.max(p[3] || 0, figureHeight() * 0.012), 8, 8),
        new THREE.MeshBasicMaterial({{ visible: false }})
      );
      group.add(hit);
      const node = {{ key, i, marker, labelSprite: label, mesh: hit,
                     pos: new THREE.Vector3(), labelPos: new THREE.Vector3(),
                     text: LABELS[key], color }};
      nodes.push(node);
      HOVER_NODES.push(node);
    }});

    scene.add(group);
    const path = {{ group, tube, nodes, orderedKeys, curve: null }};
    PATHS.push(path);
    refreshPath(path);
    return path;
  }}

  // Rebuild a pathway's tube + reposition its nodes for the current SCALE_T.
  function refreshPath(path, segments) {{
    const pts = path.orderedKeys.map((k) => {{
      const p = wpAt(k, SCALE_T);
      return new THREE.Vector3(p[0], p[1], p[2]);
    }});
    const curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.3);
    path.curve = curve;
    const old = path.tube.geometry;
    path.tube.geometry = new THREE.TubeGeometry(curve, segments || 220, tubeR(), 8, false);
    if (old) old.dispose();

    // labels stagger along Y (anterior/posterior) only - never Z, so each
    // label keeps its node's true height and the on-screen vertical order
    // always matches real anatomy. The cord nodes crowd into ~15mm of a
    // ~500mm figure, so the stagger has to be generous here; the hover
    // leader line is what ties a label back to its node.
    const step = figureHeight() * 0.075;
    path.nodes.forEach((n) => {{
      const p = wpAt(n.key, SCALE_T);
      n.pos.set(p[0], p[1], p[2]);
      if (n.marker) n.marker.position.copy(n.pos);
      n.mesh.position.copy(n.pos);
      const yOff = (n.i % 2 === 0 ? -1 : 1) * step * (1 + Math.floor(n.i / 2) * 0.4);
      n.labelPos.set(p[0], p[1] + yOff, p[2]);
      n.labelSprite.position.copy(n.labelPos);
      // sprite size is handled per-frame by updateLabelScales()
    }});
  }}

  const painPath = buildPathway({pain_order_json}, {pain_labels_json}, 0xe0705a);
  const affectPath = buildPathway({affect_order_json}, ["ILN", "ACC", "INS"], 0xd094d9);
  const reflexIpsi = buildPathway({reflex_ipsi_json}, ["Interneur", "VH_R", "Flexor"], 0x7fc99a);
  const reflexCross = buildPathway({reflex_cross_json}, ["CommIN", "VH_L", "Extensor"], 0x7fc99a);
  const motorPath = buildPathway({motor_order_json}, {motor_labels_json}, 0x6fb0e0);
  const touchPath = buildPathway({touch_order_json}, {touch_labels_json}, 0xc9a8ff);

  const reflexGroup = [reflexIpsi, reflexCross];
  const GROUPS = {{
    pain: [painPath], affect: [affectPath], reflex: reflexGroup,
    motor: [motorPath], touch: [touchPath],
  }};
  function setGroupVisible(name, on) {{ GROUPS[name].forEach((p) => {{ p.group.visible = on; }}); }}
  ["pain", "reflex", "motor", "touch", "affect"].forEach((name) => {{
    const el = document.getElementById(name + "Toggle");
    setGroupVisible(name, el.checked);
    el.addEventListener("change", (e) => setGroupVisible(name, e.target.checked));
  }});

  // ---- true-scale toggle: lerp SCALE_T, squash the cord group, rebuild tubes ----
  let scaleAnim = null;
  function applyScale() {{
    const s = 1 + (1 / CORD_SCALE - 1) * SCALE_T; // 1 -> 1/CORD_SCALE
    cordGroup.scale.z = CORD_SCALE * s;
    cordGroup.position.z = CORD_OFFSET * (1 - SCALE_T);
    PATHS.forEach((p) => refreshPath(p, scaleAnim ? 80 : 220));
    frameScene();
  }}
  applyScale();
  document.getElementById("scaleToggle").addEventListener("change", (e) => {{
    const from = SCALE_T, to = e.target.checked ? 1 : 0, t0 = performance.now();
    scaleAnim = true;
    (function step() {{
      const k = Math.min(1, (performance.now() - t0) / 700);
      SCALE_T = from + (to - from) * (k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2);
      applyScale();
      if (k < 1) requestAnimationFrame(step);
      else {{ scaleAnim = null; applyScale(); }}
    }})();
  }});

  // ---- animated pain signal along the ascending pathway ----
  const SIGNAL_COLOR = 0xffd48a;
  const SIGNAL_COUNT = 30;
  const SIGNAL_DURATION = 3.2;
  const SIGNAL_TRAIL = 0.14;
  const SIGNAL_JITTER = EXTENT * 0.008;

  const signalGeom = new THREE.BufferGeometry();
  signalGeom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(SIGNAL_COUNT * 3), 3));
  const signalPoints = new THREE.Points(signalGeom, new THREE.PointsMaterial({{
    color: SIGNAL_COLOR, size: figureHeight() * 0.006, sizeAttenuation: true,
    transparent: true, opacity: 0.95, depthWrite: false, blending: THREE.AdditiveBlending,
  }}));
  signalPoints.renderOrder = 1001;
  scene.add(signalPoints);

  let signalEnabled = true;
  document.getElementById("signalToggle").addEventListener("change", (e) => {{ signalEnabled = e.target.checked; }});

  const clock = new THREE.Clock();
  const posArr = signalGeom.attributes.position.array;

  function updateSignal() {{
    const show = signalEnabled && painPath.group.visible;
    signalPoints.visible = show;
    if (!show) return;
    const cycle = (clock.getElapsedTime() % SIGNAL_DURATION) / SIGNAL_DURATION;
    for (let i = 0; i < SIGNAL_COUNT; i++) {{
      const t = Math.min(0.999, Math.max(0, cycle - (i / SIGNAL_COUNT) * SIGNAL_TRAIL));
      const p = painPath.curve.getPointAt(t);
      posArr[i * 3 + 0] = p.x + (Math.random() - 0.5) * SIGNAL_JITTER;
      posArr[i * 3 + 1] = p.y + (Math.random() - 0.5) * SIGNAL_JITTER;
      posArr[i * 3 + 2] = p.z + (Math.random() - 0.5) * SIGNAL_JITTER;
    }}
    signalGeom.attributes.position.needsUpdate = true;
  }}

  // ---- hover: leader line + coronal slice plane through the hovered node ----
  (function setupHover() {{
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const leaderLine = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineBasicMaterial({{ color: 0xffffff, transparent: true, opacity: 0.95, depthTest: false }})
    );
    leaderLine.visible = false;
    leaderLine.renderOrder = 1000;
    scene.add(leaderLine);

    const SPAN = EXTENT * 1.4;
    const planeGeom = new THREE.PlaneGeometry(SPAN, SPAN);
    const slicePlane = new THREE.Mesh(planeGeom, new THREE.MeshBasicMaterial({{
      color: 0xffffff, transparent: true, opacity: 0.13,
      side: THREE.DoubleSide, depthWrite: false,
    }}));
    slicePlane.add(new THREE.LineSegments(
      new THREE.EdgesGeometry(planeGeom),
      new THREE.LineBasicMaterial({{ color: 0xffffff, transparent: true, opacity: 0.55 }})
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
        sliceLabel.textContent = node.text[LANG].replace(/^[\\u2460-\\u2473]+\\s*[a-d]?\\s*/, "");
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
      const live = HOVER_NODES.filter((n) => n.mesh.parent && n.mesh.parent.visible);
      const hits = raycaster.intersectObjects(live.map((n) => n.mesh), false);
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

  // ---- EN / 中文 toggle ----
  function applyLang() {{
    document.querySelectorAll("[id^='txt']").forEach((el) => {{
      const key = {{
        txtEyebrow: "eyebrow", txtTitleSuffix: "title_suffix", txtSubtitle: "subtitle",
        txtHoverTitle: "hover_title", txtStructuresTitle: "structures_title",
        txtHeightNote: "height_note", txtWalkTitle: "walk_title",
        txtPainWalk: "pain_walk", txtReflexWalk: "reflex_walk",
        txtMotorWalk: "motor_walk", txtTouchWalk: "touch_walk",
        txtPainName: "pain_name", txtPainDesc: "pain_desc",
        txtReflexName: "reflex_name", txtReflexDesc: "reflex_desc",
        txtMotorName: "motor_name", txtMotorDesc: "motor_desc",
        txtTouchName: "touch_name", txtTouchDesc: "touch_desc",
        txtAffectName: "affect_name", txtAffectDesc: "affect_desc",
        txtSignalName: "signal_name", txtSignalDesc: "signal_desc",
        txtScaleName: "scale_name", txtScaleDesc: "scale_desc",
        txtLegendNote: "legend_note", txtHintControls: "hint_controls",
        txtHintUnits: "hint_units", txtControlsTitle: "controls_title",
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
        hoveredNode.text[LANG].replace(/^[\\u2460-\\u2473]+\\s*[a-d]?\\s*/, "");
    }}
  }}

  const langToggleBtn = document.getElementById("langToggle");
  langToggleBtn.addEventListener("click", () => {{
    LANG = LANG === "en" ? "zh" : "en";
    applyLang();
  }});
  applyLang();

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
    updateLabelScales();
    renderer.render(scene, camera);
  }}
  animate();

  document.getElementById("loading").classList.add("hidden");
}})();
</script>
"""


if __name__ == "__main__":
    main()
