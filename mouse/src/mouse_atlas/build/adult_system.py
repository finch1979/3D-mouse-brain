"""Build one or all nine adult mouse systems, strictly from fetched local meshes.

Run: python -m mouse_atlas.build.adult_system [all|auditory|...]
"""
import argparse
import json
import re
from html import escape
import numpy as np
from mouse_atlas.common.paths import OUTPUTS_DIR, REPO_ROOT
from mouse_atlas.render.bake_meshes import mesh_to_region_js
from mouse_atlas.render.viewer_template import render_viewer_html
from mouse_atlas.build.system_meshes import load_regions, anchor
from mouse_atlas.build.systems import SYSTEMS, REGION_ZH, bi

OUT = OUTPUTS_DIR / 'P56' / 'pathway_meshes'
PALETTE = ['79b8ca','d9af72','91bc8b','c594c6','d98b7d','a4aee0','70b9a8']


def evidence():
    text = (REPO_ROOT/'docs/architecture/mouse-systems-evidence.md').read_text(encoding='utf-8')
    return {key:dict(title=title,url=url) for key,title,url in re.findall(
        r'^\| ([A-Z]\d+) [^|]+\| \[([^\]]+)\]\((https://[^)]+)\)', text, re.M)}


def sources_html(refs, language):
    rows = evidence()
    heading = '來源與範圍' if language == 'zh' else 'Sources and scope'
    links = '<br>'.join(f'<a href="{escape(rows[r]["url"],quote=True)}" target="_blank" rel="noopener">[{r}] {escape(rows[r]["title"])}</a>' for r in refs)
    return f'<br><br><b>{heading}</b><br>{links}'


def build(slug):
    spec = SYSTEMS[slug]
    meshes, provenance = load_regions(spec['regions'])
    extent = float(np.ptp(meshes['root'].vertices,axis=0).max())
    colors = {'root':'CCCCCC', **{acr:PALETTE[i%len(PALETTE)] for i,acr in enumerate(spec['regions'])}}
    order = list(meshes)
    waypoints, labels, real, node_meta = {}, {}, [], {}
    nodes = list(dict.fromkeys(n for branch in spec['branches'] for n in branch['nodes']))
    for node in nodes:
        if node in spec.get('populations',{}):
            region, mode, label = spec['populations'][node]
            point = anchor(meshes[region], ventral=mode=='ventral')
            # Small wireframe sphere distinguishes approximate cell populations.
            waypoints[node] = point + [extent*.012]
            labels[node] = label
            node_meta[node] = dict(region=region, side='R', kind='approximate-population', position=point)
        else:
            region, side = node.rsplit('_',1)
            point = anchor(meshes[region],side)
            waypoints[node] = point + [0]
            suffix = bi('右' if side=='R' else '左', 'right' if side=='R' else 'left')
            labels[node] = bi(f'{REGION_ZH[region]} {region}（{suffix["zh"]}）',f'{provenance[region]["name"]} ({suffix["en"]})')
            real.append(node)
            node_meta[node] = dict(region=region, side=side,kind='atlas-region',position=point)
    refs = list(dict.fromkeys(r for branch in spec['branches'] for r in branch['refs']))
    assert set(refs) <= evidence().keys()
    strings = {
        'eyebrow':bi('成鼠 · Allen CCFv3 · 區域解剖與路徑示意','Adult mouse · Allen CCFv3 · regional anatomy and schematic routes'),
        'title_main':bi(spec['name']['zh']+'（小鼠）', spec['name']['en']+' (mouse)'),
        'title_suffix':bi('',''), 'walk_title':bi('代表性連結','Selected connections'),
        'hover_title':bi('目前指向的結構','Hovered structure'),
        'structures_title':bi('腦區','Regions'), 'pathways_title':bi('路徑示意','Schematic routes'),
        'legend_note':bi('線框節點為近似定位；曲線為文獻關係示意，並非實測纖維軌跡。','Wireframe nodes are approximate; curves illustrate literature relationships, not measured axon trajectories.'),
        'signal_name':bi('路徑','Route'),'signal_desc':bi('未表示傳導時間','No conduction timing encoded'),
        'controls_title':bi('操作','Controls'),
        'hint_controls':bi('拖曳旋轉 · 雙指或滾輪縮放 · 圖層切換腦區與路徑','Drag to rotate · Pinch or scroll to zoom · Toggle regions and routes in Layers'),
        'hint_units':bi('CCFv3 空間（微米）','CCFv3 space (micrometres)'),
        'lang_button':bi('EN','中文'),'anterior':bi('前','Anterior'),'posterior':bi('後','Posterior'),
        'superior':bi('上','Superior'),'right_axis':bi('右','Right')}
    strings['subtitle'] = {}
    for lang in ('zh','en'):
        copy = escape(spec['summary'][lang]) + '<br><br>' + escape(spec['limits'][lang])
        copy += '<br><br>' + ( '雙側網格呈現解剖背景；曲線僅示意選定的區域連結，不代表完整走向、連線強度或傳導時間。' if lang=='zh' else 'Bilateral meshes supply anatomical context. Curves show selected regional connections, not full trajectories, connection strengths or transmission times.')
        if spec.get('related'):
            href, zh, en = spec['related']
            copy += f'<br><br><a href="{href}">{escape(zh if lang=="zh" else en)} →</a>'
        copy += sources_html(refs,lang)
        copy += '<br><br><a href="https://brain-map.org/support/documentation/api-for-mouse-brain-atlas" target="_blank" rel="noopener">Allen Institute · Mouse CCFv3 2017</a> · <a href="https://alleninstitute.org/legal/terms-of-use" target="_blank" rel="noopener">'+('資料使用條款' if lang=='zh' else 'Data terms')+'</a>'
        copy += '<br><br>' + ('本頁為根據引用研究製作的小鼠教育性圖譜，內容經 AI 輔助整理與編修。連線為 Finch (芬奇) Science 自行繪製的示意，並非論文原圖或原作者／機構背書。僅供教育與研究交流，不構成醫療建議。' if lang=='zh' else 'An educational mouse atlas based on cited research, prepared and edited with AI assistance. Connections are original Finch Science schematics, not paper figures or endorsements by authors or institutions. For education and research discussion; not medical advice.')
        copy += '<br>© 2026 Finch (芬奇) Science. ' + ('保留所有權利；圖譜資料權利屬其來源。' if lang=='zh' else 'All rights reserved; atlas data retain their source rights.')
        strings['subtitle'][lang] = copy
    pathways, walks = [], []
    for i, branch in enumerate(spec['branches']):
        key = branch['id']
        strings[key+'_name'] = branch['name']
        strings[key+'_desc'] = bi('文獻關係示意 · '+', '.join(branch['refs']), 'Literature schematic · '+', '.join(branch['refs']))
        strings['walk_'+str(i)] = {lang: escape(branch['name'][lang]) + '<br>' + ' → '.join(escape(labels[n][lang]) for n in branch['nodes']) + sources_html(branch['refs'],lang) for lang in ('zh','en')}
        color=PALETTE[i%len(PALETTE)]
        pathways.append(dict(id=key,name_key=key+'_name',desc_key=key+'_desc',color='0x'+color,default_checked=True,chains=[branch['nodes']]))
        walks.append(dict(key='walk_'+str(i),color='#'+color))
    config=dict(title=strings['title_main']['zh'],accent=spec['accent'],extent=extent,
        regions_js='{'+','.join(mesh_to_region_js(a,meshes[a],colors[a]) for a in order)+'}',
        order=order,strings=strings,legend_meta=[dict(acr=a,name_en=provenance[a]['name'],name_zh=REGION_ZH.get(a,'全腦輪廓'),color=colors[a],outline=a=='root',default_checked=True) for a in order],
        pathways=pathways,labels=labels,waypoints=waypoints,real=real,walk=walks,signal=None)
    html=render_viewer_html(config)
    original = 'HOVER_NODES.push({ mesh: hitMesh, pos, labelPos, labelSprite: label, text: LABELS[key], color });'
    if original not in html:
        raise ValueError('Viewer hover-node interface changed')
    html=html.replace(original, "HOVER_NODES.push({ regionKey: REAL.has(key) ? key.replace(/_[LR]$/, '') : null, mesh: hitMesh, pos, labelPos, labelSprite: label, text: LABELS[key], color });")
    # This scope applies only to newly generated pages; original renderers stay intact.
    html=html.replace('<title>', '<style>header a{color:#a9d7cd;overflow-wrap:anywhere}header .subtitle{line-height:1.7}</style>\n<title>',1)
    folder=OUT/slug
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'mouse_{slug}_pathway_3d.html'
    path.write_text(html,encoding='utf-8')
    (folder/'manifest.json').write_text(json.dumps(dict(slug=slug,atlas='Allen CCFv3 2017',species='Mus musculus',regions=provenance,nodes=node_meta,branches=spec['branches'],sources={r:evidence()[r] for r in refs},signal_timing=False),ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{slug}: {len(meshes)-1} atlas regions; {len(pathways)} routes; {path.stat().st_size/1e6:.2f} MB',flush=True)


def write_catalog():
    catalog=[]
    for slug,spec in SYSTEMS.items():
        route=bi(' / '.join(b['name']['zh'] for b in spec['branches']), ' / '.join(b['name']['en'] for b in spec['branches']))
        catalog.append(dict(slug=slug,src=f'P56/pathway_meshes/{slug}/mouse_{slug}_pathway_3d.html',accent='#'+spec['accent'],group=spec['group'],hotspot=slug,name=spec['name'],short=spec['short'],question=spec['summary'],route=route,fact=spec['limits'],source='Allen CCFv3 · mouse studies'))
    (OUT/'systems.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')


def main(slug=None):
    if slug is None:
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('system',nargs='?',default='all',choices=['all',*SYSTEMS])
        slug=parser.parse_args().system
    for key in SYSTEMS if slug=='all' else [slug]:
        build(key)
    write_catalog()


if __name__=='__main__':
    main()
