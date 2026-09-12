"""Assemble the bilingual atlas homepages from built, species-specific outputs.

The interface is inlined so the generated homepage needs no CDN or asset server.
This module belongs to site assembly and never imports either atlas package.
"""
from html import escape, unescape
from pathlib import Path

from brain_art import render_brain

TEMPLATES = Path(__file__).resolve().parent / "templates"


def bi(zh: str, en: str, tag: str = "span", attrs: str = "") -> str:
    return (f'<{tag} data-zh="{escape(unescape(zh), quote=True)}" '
            f'data-en="{escape(unescape(en), quote=True)}" {attrs}>'
            f'{escape(unescape(zh))}</{tag}>')


PROMPTS = {
    "auditory": ("聲音如何從耳朵傳到大腦？", "How does sound travel from the ear to the brain?"),
    "visual": ("沿著視覺訊號，找到通往大腦的路。", "Follow a visual signal on its way to the brain."),
    "olfactory": ("從鼻腔出發，認識嗅覺的傳遞路徑。", "Trace the route of smell, starting at the nose."),
    "limbic": ("把記憶與情緒相關結構放回腦中。", "Locate the structures involved in memory and emotion."),
    "motor-hippocampus": ("比較皮質表面與深部結構的位置。", "Compare structures on the surface and deep inside."),
    "pain": ("追蹤感覺輸入、反射與運動的連結。", "Explore the connections between sensation, reflex and movement."),
    "somatosensory": ("一個指尖的觸碰，經過哪些中繼站？", "Which relays does a signal from the fingertip pass through?"),
    "gustatory": ("從舌頭到皮質，認識味覺中繼站。", "Explore taste relays from the tongue to the cortex."),
    "vestibular": ("一起探索平衡、眼球與姿勢的連結。", "Explore the links between balance, eyes and posture."),
    "cerebellum": ("沿著迴路，認識小腦與運動控制。", "Follow the loops connecting the cerebellum and movement."),
    "sleep": ("找到睡眠與覺醒相關的神經結構。", "Find the neural structures involved in sleep and arousal."),
    "autonomic": ("觀察大腦與內臟之間的神經連結。", "See the neural connections between the brain and organs."),
    "whisker": ("從一根鬍鬚開始，探索體感路徑。", "Start with a whisker and explore the sensory pathway."),
}


def render_hub(species: str, systems: list, groups: list, planned: list,
               svg: str, repo: Path) -> str:
    mouse = species == "mouse"
    cards = []
    for key, title, sub in groups:
        rows = []
        for index, system in enumerate(systems):
            if system["group"] != key:
                continue
            slug = system["slug"]
            src = str(system["src"]).replace("\\", "/")
            legacy = mouse and not src.startswith(str(repo).replace("\\", "/"))
            href = f'./{src}' if legacy else f'./{slug}/'
            plate = "plate" in slug
            age = next((a for a in ("P14", "P15", "P56") if a in src), "P56")
            kind = "2D" if plate else "3D"
            question = ((system['question']['zh'], system['question']['en']) if 'question' in system else
                        PROMPTS.get(slug, (unescape(system["route"]["zh"]), unescape(system["route"]["en"]))))
            search = " ".join(unescape(str(v)) for d in (system["name"], system["route"], system["short"]) for v in d.values()) + " " + system["source"] + (" " + age if mouse else "")
            rows.append(f'''<a class="atlas-card" href="{escape(href)}" data-card="{slug}" data-search="{escape(search, quote=True)}" style="--card-accent:{system['accent']}">
                <div class="card-top"><span class="card-index">{index + 1:02d} <i></i></span><span class="card-format">{age + ' · ' if mouse else ''}{kind} <span aria-hidden="true">↗</span></span></div>
                {bi(system['name']['zh'], system['name']['en'], 'h3')}
                {bi(*question, 'p', 'class="card-question"')}
                {bi(system['route']['zh'], system['route']['en'], 'p', 'class="card-route"')}
                <div class="card-bottom"><span>{escape(system['source'])}</span>{bi('開啟圖譜 →', 'Explore →')}</div>
            </a>''')
        cards.append(f'<section class="system-group" data-group="{key}"><div class="group-heading">{bi(title["zh"], title["en"], "h3")}{bi(sub["zh"], sub["en"], "span")}</div><div class="cards">{"".join(rows)}</div></section>')
    filters = bi("全部", "All systems", "button", 'type="button" class="filter active" data-filter="all" aria-pressed="true"')
    for key, title, _ in groups:
        filters += bi(title["zh"], title["en"], "button", f'type="button" class="filter" data-filter="{key}" aria-pressed="false"')
    planned_html = ""
    if planned:
        planned_html = '<div class="planned">' + bi('接下來的探索', 'On the horizon', 'h3')
        for item in planned:
            planned_html += bi(item['name']['zh'], item['name']['en'], 'span', 'class="planned-item"')
        planned_html += '</div>'
    count = sum(s["group"] != "hidden" for s in systems)
    source_zh = ('Allen CCFv3 成鼠圖譜、DeMBA P15 與 Allen P14 發育圖譜。' if mouse else
                 'MNI152、Harvard-Oxford、AAL3、PAM50、Diedrichsen 小腦圖譜與 Allen Human Brain Atlas。')
    source_en = ('Allen CCFv3 adult atlas, DeMBA P15 and the Allen P14 developing atlas.' if mouse else
                 'MNI152, Harvard-Oxford, AAL3, PAM50, Diedrichsen cerebellar atlas and Allen Human Brain Atlas.')
    replacements = {
        'CSS': (TEMPLATES / 'atlas.css').read_text(encoding='utf-8'),
        'JS': (TEMPLATES / 'atlas.js').read_text(encoding='utf-8'),
        'SPECIES': species,
        'HOME': '../' if mouse else './',
        'HUMAN_LINK': '../' if mouse else './',
        'MOUSE_LINK': './' if mouse else './mouse/',
        'HUMAN_CURRENT': '' if mouse else 'aria-current="page"',
        'MOUSE_CURRENT': 'aria-current="page"' if mouse else '',
        'TITLE': '小鼠腦圖譜' if mouse else '人類神經圖譜',
        'EYEBROW': bi('小鼠腦圖譜 · MOUSE ATLAS' if mouse else '人類神經圖譜 · HUMAN ATLAS', 'MOUSE BRAIN ATLAS' if mouse else 'HUMAN NERVOUS SYSTEM'),
        'HERO_TITLE': (bi('從小鼠腦，', 'A small brain.', 'span') + bi('看見大世界。', 'A world to explore.', 'span', 'class="accent"')) if mouse else
                      (bi('看見訊號，', 'Follow the signal.', 'span') + bi('理解大腦。', 'Understand the brain.', 'span', 'class="accent"')),
        'HERO_INTRO': bi('從感覺路徑到發育中的腦，旋轉、觀察、逐步理解。讓平面的知識，成為立體的連結。' if mouse else '從一個感覺出發，走進神經系統。透過互動 3D 圖譜，看清每個結構的位置，串起訊號的旅程。',
                         'Explore sensory pathways and the developing brain. Rotate, observe and connect the structures in three dimensions.' if mouse else 'Start with a sensation. Explore interactive 3D atlases, find each structure and piece together the journey of a signal.', 'p', 'class="hero-intro"'),
        'START_LINK': './whisker/' if mouse else './visual/',
        'START_TEXT': bi('從鬍鬚體感開始', 'Start with whisker touch') if mouse else bi('從視覺系統開始', 'Start with vision'),
        'COUNT': str(count),
        'STAT_LABEL': bi('路徑與結構', 'pathways & structures') if mouse else bi('神經系統主題', 'systems to explore'),
        'STAT_TWO': '3' if mouse else '3D',
        'STAT_TWO_LABEL': bi('發育年齡', 'developmental ages') if mouse else bi('互動空間探索', 'interactive exploration'),
        'BRAIN': render_brain(species, repo),
        'BRAIN_SOURCE': 'ALLEN CCFv3 · P56' if mouse else 'ALLEN HUMAN BRAIN ATLAS',
        'BRAIN_LABEL': bi('成鼠腦表面', 'Adult mouse brain surface') if mouse else bi('人類腦表面', 'Human brain surface'),
        'FILTERS': filters,
        'CARDS': ''.join(cards),
        'MAP': svg,
        'PLANNED': planned_html,
        'SOURCE': bi(source_zh, source_en, 'p'),
    }
    html = (TEMPLATES / 'atlas.html').read_text(encoding='utf-8')
    for name, value in replacements.items():
        html = html.replace(f'__{name}__', value)
    return html
