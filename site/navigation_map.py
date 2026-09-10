"""Compact anatomical navigation from existing atlas geometry and topic routes.

The projected brain is a spatial reference. Numbered links are topic entrances,
not segmentation labels or invented anatomical attachment points.
"""

from html import escape, unescape
from pathlib import Path

from brain_art import render_map_brain


def _text(zh: str, en: str, tag: str = "span", attrs: str = "") -> str:
    return (f'<{tag} data-zh="{escape(unescape(zh), quote=True)}" '
            f'data-en="{escape(unescape(en), quote=True)}" {attrs}>'
            f'{escape(unescape(zh))}</{tag}>')


def render_navigation_map(species: str, systems: list, repo: Path) -> str:
    mouse = species == "mouse"
    groups = (
        ("structures" if mouse else "central", "腦內結構", "Within the brain"),
        ("pathways" if mouse else "input", "感覺入口", "Sensory entry points"),
        ("output", "身體連結", "Brain & body"),
    )
    sections = []
    for key, zh, en in groups:
        routes = []
        for index, system in enumerate(systems):
            if system["group"] != key or not system.get("hotspot"):
                continue
            src = Path(system["src"])
            href = f'./{src.as_posix()}' if mouse and not src.is_absolute() else f'./{system["slug"]}/'
            routes.append(
                f'<a class="hot map-route" href="{escape(href, quote=True)}" '
                f'data-slug="{system["slug"]}" style="--accent:{system["accent"]}">'
                f'<span class="map-number" aria-hidden="true">{index + 1:02d}</span>'
                + _text(system["short"]["zh"], system["short"]["en"], attrs='class="map-route-name"')
                + '<span class="map-route-arrow" aria-hidden="true">↗</span></a>'
            )
        if routes:
            sections.append('<section class="map-section">'
                            + _text(zh, en, "h4")
                            + '<div class="map-routes">' + "".join(routes) + '</div></section>')

    return (
        '<div id="map" class="anatomical-index">'
        '<figure class="map-plate">'
        '<div class="map-plate-heading"><span>'
        + ('MOUSE BRAIN' if mouse else 'HUMAN BRAIN')
        + '</span><span>OBLIQUE VIEW</span></div>'
        + render_map_brain(species, repo)
        + '<figcaption><span class="map-direction">A <i aria-hidden="true"></i> P</span>'
        + _text('圖譜表面投影', 'Atlas surface projection')
        + '</figcaption></figure><div class="map-directory">'
        + "".join(sections) + '</div></div>'
    )
