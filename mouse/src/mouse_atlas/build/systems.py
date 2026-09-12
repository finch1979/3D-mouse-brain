"""Adult mouse systems backed by docs/architecture/mouse-systems-evidence.md.

Region outlines and population markers are separate. A chain is an educational
relationship, never a measured axonal trajectory. No human package imports.
"""

def bi(zh, en):
    return {'zh': zh, 'en': en}


REGION_ZH = dict(zip(
    'CN SOC IC MGv AUDp CU GR VPL SSp-ul SSp-ll MOp NTS PB VPMpc GU MV SUV III VI FL CBX IP DN FN VAL RN IO CA1 CA3 DG SUB BLA ENTl PAG RM CEA LC LHA VLPO TMv PVH DMX'.split(),
    '耳蝸核群 上橄欖複合體 下丘 腹側內側膝狀體 初級聽覺區 楔狀核 薄束核 腹後外側丘腦核 初級體感上肢區 初級體感下肢區 初級運動區 孤束核 橋臂核 腹後內側丘腦核小細胞部 味覺區 內側前庭核 上前庭核 動眼神經核 外展神經核 絨球 小腦皮質 中間核 齒狀核 頂核 腹前外側丘腦複合體 紅核 下橄欖複合體 海馬CA1 海馬CA3 齒狀回 下托 基底外側杏仁核 外側內嗅區 導水管周圍灰質 中縫大核 中央杏仁核 藍斑 外側下視丘區 腹外側視前核 腹側結節乳頭核 室旁下視丘核 迷走神經背側運動核'.split()))


def branch(id, zh, en, nodes, refs):
    return dict(id=id, name=bi(zh,en), nodes=nodes.split(), refs=refs.split())


SYSTEMS = {
    'auditory': dict(name=bi('聽覺系統','Auditory system'), short=bi('聽覺','Hearing'),
        group='pathways', accent='d5ad65', regions='CN SOC IC MGv AUDp'.split(),
        summary=bi('從中腦到聽皮質，觀察聲音訊息的主要中繼。','Follow a regional auditory relay from midbrain to cortex.'),
        limits=bi('耳蝸核與上橄欖複合體作為腦幹背景；未畫出全部雙側分支與耳蝸。','Cochlear nuclei and superior olive provide brainstem context; cochlea and the full bilateral network are omitted.'),
        branches=[branch('ascending','下丘 → 聽覺丘腦 → 皮質','Colliculus → auditory thalamus → cortex','IC_R MGv_R AUDp_R','A1 A2')]),
    'somatosensory': dict(name=bi('一般體感系統','Somatosensory system'),short=bi('體感','Touch'),
        group='pathways',accent='b28ad2',regions='CU GR VPL SSp-ul SSp-ll MOp'.split(),
        summary=bi('以前肢觸覺為例，從楔狀核連到丘腦與感覺運動皮質。','Explore a forelimb touch example through cuneate, thalamic and sensorimotor regions.'),
        limits=bi('薄束核與下肢皮質僅供位置對照；未重建周邊神經、脊髓或所有體感路徑。','Gracile nucleus and hindlimb cortex are context only; peripheral nerves, spinal cord and other modalities are not reconstructed.'),
        related=('/mouse/whisker/','鬍鬚體感專題','Whisker pathway'),
        branches=[branch('ascending','楔狀核交叉上行 → 前肢皮質','Crossed cuneate input → forelimb cortex','CU_L VPL_R SSp-ul_R','T1'),
                  branch('cortical','體感 → 運動皮質','Somatosensory → motor cortex','SSp-ul_R MOp_R','T1')]),
    'gustatory':dict(name=bi('味覺系統','Gustatory system'),short=bi('味覺','Taste'),
        group='pathways',accent='d88d69',regions='NTS PB VPMpc GU'.split(),
        summary=bi('保留小鼠的橋臂核中繼，探索味覺通往丘腦與皮質的代表性路線。','Explore the mouse taste route with its parabrachial relay.'),
        limits=bi('完整核群不等於其中的味覺細胞群；舌部與顱神經未建模。','Whole nuclei do not delineate taste-specific populations; tongue and cranial nerves are not modeled.'),
        branches=[branch('brainstem','孤束核 → 橋臂核','Solitary nucleus → parabrachial nucleus','NTS_R PB_R','G1'),
                  branch('cortical','橋臂核 → 味覺丘腦 → 皮質','Parabrachial → gustatory thalamus → cortex','PB_R VPMpc_R GU_R','G2')]),
    'vestibular':dict(name=bi('前庭與平衡系統','Vestibular system'),short=bi('平衡','Balance'),
        group='pathways',accent='62bab7',regions='MV SUV III VI FL'.split(),
        summary=bi('以小腦絨球、前庭核與動眼中繼，觀察穩定視線的部分迴路。','Explore selected cerebellar, vestibular and oculomotor connections for gaze stabilization.'),
        limits=bi('絨球到前庭核代表抑制性 Purkinje 細胞投射；未細分眼肌、半規管或完整前庭脊髓路。','Floccular output represents inhibitory Purkinje projections; eye muscles, semicircular canals and vestibulospinal routes are omitted.'),
        branches=[branch('cerebellar','絨球 → 內側前庭核（抑制）','Flocculus → medial vestibular nucleus (inhibitory)','FL_R MV_R','V1'),
                  branch('ocular','前庭核 → 對側動眼核','Vestibular → contralateral oculomotor nucleus','MV_R III_L','V2')]),
    'cerebellum':dict(name=bi('小腦系統','Cerebellar system'),short=bi('小腦','Cerebellum'),
        group='structures',accent='7dbd92',regions='CBX IP DN FN VAL RN IO'.split(),
        summary=bi('比較小腦皮質與深部核，觀察橄欖輸入和中間核輸出的代表性連結。','Compare cerebellar cortex and deep nuclei with selected olivary input and interposed output.'),
        limits=bi('圖示連到區域，不代表全部微區或 Purkinje 細胞；其他深部核的輸出未完整展開。','Regional links do not resolve microzones or Purkinje populations; other deep-nucleus outputs are not exhaustively shown.'),
        branches=[branch('input','下橄欖 → 對側小腦皮質','Inferior olive → contralateral cerebellar cortex','IO_L CBX_R','C2'),
                  branch('red','中間核 → 對側紅核','Interposed → contralateral red nucleus','IP_R RN_L','C1 C3'),
                  branch('thalamic','中間核 → 對側運動丘腦','Interposed → contralateral motor thalamus','IP_R VAL_L','C1 C3')]),
    'limbic':dict(name=bi('邊緣系統','Limbic system'),short=bi('邊緣','Limbic'),
        group='structures',accent='cd9c7c',regions='CA1 CA3 DG SUB BLA ENTl'.split(),
        summary=bi('在海馬與杏仁核之間，探索一條與情緒相關的代表性連結。','Explore a selected amygdala–hippocampal connection in its anatomical context.'),
        limits=bi('vCA1 是腹側 CA1 的近似標記；全 CA1 網格不是腹側亞區分割。不同細胞群可能產生不同情緒效應。','vCA1 is an approximate ventral CA1 marker, not a segmented subregion. Different cell populations can have different behavioral effects.'),
        related=('/mouse/P56/hippocampus_3d.html','海馬結構專題','Hippocampal anatomy'),
        populations={'vCA1':('CA1','ventral',bi('腹側 CA1（近似定位）','Ventral CA1 (approximate)'))},
        branches=[branch('affective','杏仁核 → 腹側海馬鄰域','Amygdala → ventral hippocampal neighborhood','BLA_R vCA1','L1 L2')]),
    'pain':dict(name=bi('疼痛與調節系統','Pain and modulation'),short=bi('疼痛','Pain'),
        group='output',accent='d47c76',regions='PB CEA PAG RM'.split(),
        summary=bi('分開看上行情緒成分與下行調節，不把疼痛縮成單一路線。','Separate an ascending affective component from descending modulation.'),
        limits=bi('RVM 以中縫大核附近的示意標記呈現，兩者不等同；脊髓與周邊傳入未繪製。下行調節不一定是抑制。','RVM is approximated near raphe magnus and is not identical to it. Spinal/peripheral stages are omitted; descending modulation is not uniformly inhibitory.'),
        populations={'RVM':('RM','center',bi('RVM 鄰域（近似定位）','RVM neighborhood (approximate)'))},
        branches=[branch('ascending','橋臂核 → 中央杏仁核','Parabrachial → central amygdala','PB_R CEA_R','P1'),
                  branch('descending','PAG → RVM 鄰域','PAG → RVM neighborhood','PAG_R RVM','P2')]),
    'sleep':dict(name=bi('睡眠與覺醒系統','Sleep and wakefulness'),short=bi('睡眠','Sleep'),
        group='structures',accent='8f9fd2',regions='LC LHA VLPO TMv'.split(),
        summary=bi('比較兩組研究支持的調節連結：食慾素與藍斑，以及視前區與結節乳頭核。','Compare two studied links: orexin–locus coeruleus and preoptic–tuberomammillary signaling.'),
        limits=bi('POA 與食慾素細胞群只作近似定位；整個 VLPO 或外側下視丘不等於這些細胞群。未涵蓋全部 REM／NREM 控制。','POA and orexin populations are approximate markers, not entire VLPO or LHA regions. This is not the complete REM/NREM control network.'),
        populations={'Orexin':('LHA','center',bi('食慾素細胞群（近似）','Orexin population (approximate)')),
                     'POA':('VLPO','center',bi('視前睡眠細胞群（近似）','Preoptic sleep population (approximate)'))},
        branches=[branch('wake','食慾素鄰域 → 藍斑','Orexin neighborhood → locus coeruleus','Orexin LC_R','S1'),
                  branch('sleep','視前區 → 結節乳頭核（抑制）','Preoptic → tuberomammillary (inhibitory)','POA TMv_R','S2')]),
    'autonomic':dict(name=bi('自律神經系統','Autonomic system'),short=bi('自律','Autonomic'),
        group='output',accent='c6ab68',regions='PVH NTS DMX'.split(),
        summary=bi('觀察下視丘與背側延髓之間，和內臟調節相關的代表性連結。','Explore selected hypothalamic and dorsal medullary connections related to visceral regulation.'),
        limits=bi('背側迷走複合體以鄰域標記呈現；不宣稱所有投射單獨終止在 DMX。周邊器官、交感鏈與反射細節未建模。','The dorsal vagal complex is a neighborhood marker, not proof of isolated DMX targeting. Peripheral organs, sympathetic chain and reflex details are not modeled.'),
        populations={'DVC':('DMX','center',bi('背側迷走複合體（近似）','Dorsal vagal complex (approximate)'))},
        branches=[branch('down','PVH → 孤束核','PVH → solitary nucleus','PVH_R NTS_R','U1'),
                  branch('up','孤束核 → PVH','Solitary nucleus → PVH','NTS_R PVH_R','U2'),
                  branch('vagal','PVH → 背側迷走鄰域','PVH → dorsal vagal neighborhood','PVH_R DVC','U3')]),
}
