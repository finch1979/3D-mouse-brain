"""Render the self-contained 3D pathway viewer HTML shared by the six new
human system pages (somatosensory / gustatory / vestibular / autonomic /
cerebellum / sleep).

Sibling to the templates embedded in build/human_auditory.py (two-pathway
trunk+branch chains, canvas-texture label sprites, hover leader-line +
coronal slice plane, animated signal swarm) and build/human_pain.py
(collapsible walkthrough panel, collapsible legend + controls, EN/zh
toggle). This module extracts the machinery they share so the six new
pages don't fork six private copies, and swaps `.format()` (which forces
every CSS/JS brace to be doubled) for __TOKEN__ substitution.

A page build script assembles a config dict and calls render_viewer_html();
see build/human_somatosensory.py for the reference usage.

Config keys (all required unless noted):
    title          page <title>
    accent         hex without '#', drives the CSS --accent variable
    extent         scene scale in um (max bbox dimension over ALL meshes,
                   cord included - the camera frames from this)
    regions_js     REGIONS object literal (baked meshes, bake_meshes.py)
    order          mesh acronyms in draw order
    strings        {key: {en, zh}} for every DOM text node
    legend_meta    [{acr, name_en, name_zh, color, outline, default_checked}]
    pathways       [{id, name_key, desc_key, color ('0x..'), default_checked,
                     chains: [[waypoint keys...], ...]}]  - one tube per chain
    labels         {waypoint key: {en, zh}} node label sprites
    waypoints      {key: [x, y, z, r_um]} in micrometres
    real           waypoint keys anchored to a real mesh (no wireframe ball)
    signal         optional {pathway, color ('0x..'), duration} animated pulse
    walk           optional [{key, color}] walkthrough steps (strings[key])
    frame          optional camera-distance multiplier (default 2.1)

The output is a body fragment exactly like every other viewer in this repo:
starts at <title>, ends at </script>, no doctype/head/body - the hub
injector (site/build_hub.py) relies on that.
"""

from __future__ import annotations

from pathlib import Path

from human_atlas.common.paths import WEB_LIB_DIR

_TEMPLATE_PATH = Path(__file__).resolve().parent / "viewer_template.html"


def render_viewer_html(cfg: dict) -> str:
    """Fill the shared template with one page's data + baked meshes."""
    three_js = (WEB_LIB_DIR / "three.min.js").read_text(encoding="utf-8")
    orbit_js = (WEB_LIB_DIR / "OrbitControls.js").read_text(encoding="utf-8")

    import json

    def js(obj) -> str:
        return json.dumps(obj, ensure_ascii=False)

    # pathway rows in the legend + the JS pathway registry share one shape
    pw_js = [
        {
            "id": p["id"], "color": p["color"],
            "name_key": p["name_key"], "desc_key": p["desc_key"],
            "chains": p["chains"], "default_checked": p["default_checked"],
        }
        for p in cfg["pathways"]
    ]
    pw_rows = []
    for p in cfg["pathways"]:
        pw_rows.append(f"""
    <label class="legend-row" data-acr="{p['id']}">
      <input type="checkbox" id="pw_{p['id']}" {'checked' if p['default_checked'] else ''} />
      <span class="swatch" style="--swatch:#{p.get('row_color', p['color'].replace('0x', ''))}"></span>
      <span class="legend-text">
        <span class="legend-acr" id="txtPw_{p['id']}Name"></span>
        <span class="legend-name" id="txtPw_{p['id']}Desc"></span>
      </span>
    </label>""")

    walk_rows = []
    for i, w in enumerate(cfg.get("walk", [])):
        walk_rows.append(
            f'    <div class="step" id="txtWalk{i}" '
            f'style="border-left-color:{w["color"]}"></div>')
    walk_ids_js = js([f"txtWalk{i}" for i in range(len(cfg.get("walk", [])))])

    html = _TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "__TITLE__": cfg["title"],
        "__ACCENT__": cfg["accent"],
        "__EXTENT__": repr(float(cfg["extent"])),
        "__FRAME__": repr(float(cfg.get("frame", 2.1))),
        "__THREE__": three_js,
        "__ORBIT__": orbit_js,
        "__REGIONS__": cfg["regions_js"],
        "__ORDER__": js(cfg["order"]),
        "__STRINGS__": js(cfg["strings"]),
        "__LEGEND__": js(cfg["legend_meta"]),
        "__PATHWAYS__": js(pw_js),
        "__PW_ROWS__": "".join(pw_rows),
        "__LABELS__": js(cfg["labels"]),
        "__WAYPOINTS__": js(cfg["waypoints"]),
        "__REAL__": js(cfg["real"]),
        "__SIGNAL__": js(cfg.get("signal")),
        "__WALK_ROWS__": "\n".join(walk_rows),
        "__WALK_IDS__": walk_ids_js,
        "__CUSTOM__": cfg.get("custom_js", ""),
    }
    for token, value in replacements.items():
        if token not in html:
            raise RuntimeError(f"template token {token} missing from viewer_template.html")
        html = html.replace(token, value)
    # three.min.js itself contains the literal "__THREE__" (multi-instance
    # guard), so the library tokens are exempt from the leftover scan
    leftover = [t for t in replacements if t not in ("__THREE__", "__ORBIT__") and t in html]
    if leftover:
        raise RuntimeError(f"unreplaced tokens in rendered HTML: {leftover}")
    return html
