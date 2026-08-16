"""
Build self-contained interactive HTML pages for Allen Brain Atlas reference
plates: hover/click any colored region for its full structure name, with the
raw Nissl photo underneath for anatomical context, a region search box, a
persisted "recently viewed" history, and cross-links between plates + the
3D structure viewer.

Data sources (Allen Institute Brain Map API, all public, no key required):
  - Structure ontology  : /api/v2/data/Structure/query.json   (id -> full name)
  - Region boundary SVG : /api/v2/svg/{image_id}               (vector paths)
  - Plate photo (Nissl) : /api/v2/atlas_image_download/{image_id}?annotation=false

Usage:
    python build_plate_atlas.py            # builds every plate in PLATES
    python build_plate_atlas.py p56_coronal_289
"""

import base64
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

import requests
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ATLAS_DIR = os.path.join(SCRIPT_DIR, "atlas")

API_BASE = "http://api.brain-map.org/api/v2"
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

# each page lives in its own age-group folder (atlas/P56, atlas/P14, ...) so
# photos/meshes for different ages never mix; nav links are computed relative
# to whichever folder is currently being built
NAV_PAGES = [
    {"key": "p56_coronal_289", "label": "P56 &middot; Coronal", "dir": "P56", "file": "coronal_section289_interactive.html"},
    {"key": "p14_sagittal_144", "label": "P14 &middot; Sagittal", "dir": "P14", "file": "sagittal_p14_section144_interactive.html"},
    {"key": "p15_coronal_demba", "label": "P15 &middot; Coronal (DeMBA)", "dir": "P15", "file": "coronal_p15_demba_interactive.html"},
    {"key": "3d", "label": "3D (P56 adult)", "dir": "P56", "file": "motor_cortex_3d.html"},
    {"key": "3d_p15", "label": "3D (P15)", "dir": "P15", "file": "motor_cortex_3d_p15.html"},
]

PLATES = {
    "p56_coronal_289": {
        "image_id": 100960232,
        "section_number": 289,
        "out_dir": "P56",
        "out_file": "coronal_section289_interactive.html",
        "eyebrow": "Allen Mouse Brain CCF &middot; P56 coronal reference &middot; section 289",
        "title_html": 'Interactive <span class="accent">Coronal Atlas</span>',
        "title_plain": "Coronal Atlas &middot; P56 Section 289",
        "subtitle": (
            "Left = raw Nissl photograph, right = colored structure diagram. Drag the divider to compare "
            "either side; hover or click any colored region for its full anatomical name."
        ),
        "source_note": "atlas_id=1 (Mouse, P56, Coronal) &middot; image_id=100960232 &middot; section_number=289",
        "history_key": "mouseAtlasHistory_p56_section289_v1",
        "resolution_um_per_px": 1.047,
        "series_index": 72,
        "series_total": 132,
        "position_axis_labels": ("Anterior", "Posterior"),
        "position_note": (
            "Plate 73 of 132 in the anterior&rarr;posterior coronal series (Allen's own ordering)."
        ),
        # slice position cross-referenced against this exact plate's own MOp/MOs/RSP content in the 3D
        # model (midpoint between where MOp/MOs end and RSP begins along the AP axis) - precise, not a guess
        "slice_axis": "x",
        "slice_pos": -358.7,
        "slice_approx": False,
        "slice_label": "Coronal section 289 (P56)",
    },
    "p14_sagittal_144": {
        "image_id": 100365849,
        "section_number": 144,
        "out_dir": "P14",
        "out_file": "sagittal_p14_section144_interactive.html",
        "eyebrow": "Allen Developing Mouse Brain Atlas &middot; P14 sagittal reference &middot; section 144",
        "title_html": 'Interactive <span class="accent">P14 Sagittal Atlas</span>',
        "title_plain": "Sagittal Atlas &middot; P14 Section 144",
        "subtitle": (
            "P14 has no coronal reference &mdash; only this sagittal series exists. Regions use the "
            "developmental (prosomeric) ontology, not the adult MOp/MOs-style names: cortex appears as "
            "DPall/MPall, brainstem as p1&ndash;p3 and rhombomeres r1&ndash;r11. Drag the divider to compare "
            "photo vs diagram; hover or click any region for its full name."
        ),
        "source_note": "atlas_id=181276164 (Developing Mouse, P14) &middot; image_id=100365849 &middot; section_number=144",
        "history_key": "mouseAtlasHistory_p14_section144_v1",
        "resolution_um_per_px": 1.047,
        "series_index": 29,
        "series_total": 39,
        "position_axis_labels": ("Medial (approx.)", "Lateral (approx.)"),
        "position_note": (
            "Plate 30 of 39 in the series; at ~93% of this series' widest plate's cross-section width, "
            "so a relatively medial parasagittal cut &mdash; but this is inferred from tissue width, "
            "not a stereotaxic ML coordinate (the API does not expose one for this atlas)."
        ),
        # no region-level 3D mesh exists for P14, so this is a coarse estimate: plate's ordinal position
        # in the 39-plate series, scaled onto the adult root mesh's half-width along the ML (Z) axis
        "slice_axis": "z",
        "slice_pos": 3970.6,
        "slice_approx": True,
        "slice_label": "Sagittal section 144 (P14, approximate)",
    },
}


def api_get(path, params=None, cache_dir=None, cache_name=None, binary=False):
    cache_path = os.path.join(cache_dir, cache_name) if (cache_dir and cache_name) else None
    if cache_path and os.path.exists(cache_path):
        mode = "rb" if binary else "r"
        with open(cache_path, mode, **({} if binary else {"encoding": "utf-8"})) as f:
            return f.read()
    r = requests.get(f"{API_BASE}{path}", params=params, timeout=120)
    r.raise_for_status()
    content = r.content if binary else r.text
    if cache_path:
        mode = "wb" if binary else "w"
        with open(cache_path, mode, **({} if binary else {"encoding": "utf-8"})) as f:
            f.write(content)
    return content


def qn(tag):
    return f"{{{SVG_NS}}}{tag}"


def fetch_svg_groups(image_id, cache_dir):
    svg_text = api_get(f"/svg/{image_id}", cache_dir=cache_dir, cache_name=f"{image_id}.svg")
    root = ET.fromstring(svg_text)
    width = root.get("width")
    height = root.get("height")

    top_groups = root.findall(f"./{qn('g')}/{qn('g')}")
    # each inner <g> can carry its own transform="scale(...)" (varies per image -
    # P56's happened to be 1.0, but others like P14's are not, e.g. 8.33333) so
    # paths must stay wrapped in their originating group, not flattened out
    structures_groups = []
    tracts_groups = []
    fill_re = re.compile(r"fill:\s*(#[0-9a-fA-F]{6})")

    for g in top_groups:
        label = g.get("graphic_group_label", "")
        transform = g.get("transform", "")
        paths = []
        for p in g.findall(f".//{qn('path')}"):
            sid = p.get("structure_id")
            d = p.get("d")
            style = p.get("style", "")
            if not sid or not d:
                continue
            m = fill_re.search(style)
            fill = m.group(1) if m else "#cccccc"
            paths.append((sid, fill, d))
        if not paths:
            continue
        bucket = structures_groups if "Fiber Tracts" not in label else tracts_groups
        bucket.append((transform, paths))

    return width, height, structures_groups, tracts_groups


def fetch_names(sids, cache_dir):
    id_str = ",".join(sorted(set(sids)))
    text = api_get(
        "/data/Structure/query.json",
        params={"criteria": f"[id$in{id_str}]", "num_rows": "all"},
        cache_dir=cache_dir,
        cache_name=f"names_{hashlib.md5(id_str.encode()).hexdigest()[:10]}.json",
    )
    rows = json.loads(text)["msg"]
    return {
        str(row["id"]): {"acronym": row["acronym"], "name": row["name"], "color": row["color_hex_triplet"]}
        for row in rows
    }


def fetch_photo_b64(image_id, cache_dir, target_w=2400):
    cache_path = os.path.join(cache_dir, f"{image_id}_photo_web.jpg")
    if not os.path.exists(cache_path):
        raw = api_get(
            f"/atlas_image_download/{image_id}",
            params={"downsample": 1, "annotation": "false"},
            cache_dir=cache_dir,
            cache_name=f"{image_id}_photo_full.jpg",
            binary=True,
        )
        full_path = os.path.join(cache_dir, f"{image_id}_photo_full.jpg")
        im = Image.open(full_path)
        w, h = im.size
        target_h = round(h * target_w / w)
        im = im.resize((target_w, target_h), Image.LANCZOS)
        im.save(cache_path, quality=86, optimize=True)
    with open(cache_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def groups_to_svg_markup(groups):
    parts = []
    for transform, paths in groups:
        inner = "".join(f'<path data-sid="{sid}" style="fill:{fill}" d="{d}"/>' for sid, fill, d in paths)
        if transform.strip():
            parts.append(f'<g transform="{transform}">{inner}</g>')
        else:
            parts.append(inner)
    return "".join(parts)


def render_nav(current_key, current_dir, slice_query=""):
    items = []
    for p in NAV_PAGES:
        cls = "nav-link active" if p["key"] == current_key else "nav-link"
        href = p["file"] if p["dir"] == current_dir else f'../{p["dir"]}/{p["file"]}'
        if p["key"] == "3d" and slice_query:
            href += slice_query
        items.append(f'<a class="{cls}" href="{href}">{p["label"]}</a>')
    return "".join(items)


def build_slice_query(cfg):
    from urllib.parse import urlencode

    return "?" + urlencode({
        "axis": cfg["slice_axis"],
        "pos": cfg["slice_pos"],
        "label": cfg["slice_label"],
        "approx": "1" if cfg["slice_approx"] else "0",
    })


def build(plate_key):
    cfg = PLATES[plate_key]
    image_id = cfg["image_id"]
    out_dir_path = os.path.join(ATLAS_DIR, cfg["out_dir"])
    cache_dir = os.path.join(out_dir_path, "api_cache")
    os.makedirs(cache_dir, exist_ok=True)
    print(f"--- building {plate_key} (image_id={image_id}) ---")

    width, height, structures_groups, tracts_groups = fetch_svg_groups(image_id, cache_dir)
    n_struct_paths = sum(len(paths) for _, paths in structures_groups)
    n_tract_paths = sum(len(paths) for _, paths in tracts_groups)
    print(f"structures paths: {n_struct_paths}, fiber tract paths: {n_tract_paths}")

    used_sids = {sid for _, paths in structures_groups for sid, _, _ in paths} | {
        sid for _, paths in tracts_groups for sid, _, _ in paths
    }
    names = fetch_names(used_sids, cache_dir)
    missing = used_sids - set(names)
    if missing:
        print("WARNING missing names for:", missing)

    photo_b64 = fetch_photo_b64(image_id, cache_dir)

    size_w_mm = float(width) * cfg["resolution_um_per_px"] / 1000
    size_h_mm = float(height) * cfg["resolution_um_per_px"] / 1000
    position_frac = cfg["series_index"] / (cfg["series_total"] - 1) * 100
    slice_query = build_slice_query(cfg)

    html = TEMPLATE.format(
        width=width,
        height=height,
        half_width=float(width) / 2,
        photo_b64=photo_b64,
        structures_svg=groups_to_svg_markup(structures_groups),
        tracts_svg=groups_to_svg_markup(tracts_groups),
        names_json=json.dumps(names, ensure_ascii=False),
        eyebrow=cfg["eyebrow"],
        title_html=cfg["title_html"],
        subtitle=cfg["subtitle"],
        source_note=cfg["source_note"],
        history_key=cfg["history_key"],
        nav_html=render_nav(plate_key, cfg["out_dir"], slice_query),
        struct_count=len(used_sids),
        title_plain=cfg["title_plain"],
        size_w_mm=f"{size_w_mm:.2f}",
        size_h_mm=f"{size_h_mm:.2f}",
        series_index=cfg["series_index"] + 1,
        series_total=cfg["series_total"],
        position_frac=f"{position_frac:.1f}",
        position_label_left=cfg["position_axis_labels"][0],
        position_label_right=cfg["position_axis_labels"][1],
        position_note=cfg["position_note"],
        slice_href=f'../P56/motor_cortex_3d.html{slice_query}' if cfg["out_dir"] != "P56" else f'motor_cortex_3d.html{slice_query}',
    )

    out_path = os.path.join(out_dir_path, cfg["out_file"])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out_path} ({os.path.getsize(out_path) / 1024 / 1024:.2f} MB)")


TEMPLATE = """<title>{title_plain}</title>
<style>
  :root {{
    --bg: #12151a;
    --panel: rgba(27, 32, 40, 0.92);
    --panel-border: #2b323d;
    --text: #e9edf1;
    --text-dim: #8b96a3;
    --text-faint: #5c6672;
    --accent: #e0a458;
    --mono: ui-monospace, "Cascadia Code", "SF Mono", "JetBrains Mono", Consolas, "Liberation Mono", monospace;
    --sans: -apple-system, "Segoe UI", system-ui, Roboto, sans-serif;
  }}

  * {{ box-sizing: border-box; }}

  html, body {{
    margin: 0;
    padding: 0;
    width: 100%;
    min-height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
  }}

  nav.crossnav {{
    display: flex;
    gap: 6px;
    padding: 14px 32px 0;
    flex-wrap: wrap;
  }}

  .nav-link {{
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    color: var(--text-dim);
    text-decoration: none;
    padding: 6px 12px;
    border-radius: 999px;
    border: 1px solid var(--panel-border);
    background: rgba(255, 255, 255, 0.02);
  }}

  .nav-link:hover {{ color: var(--text); border-color: var(--text-faint); }}

  .nav-link.active {{
    color: #12151a;
    background: var(--accent);
    border-color: var(--accent);
    font-weight: 600;
  }}

  header.ui {{
    padding: 14px 32px 14px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}

  .eyebrow {{
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-faint);
  }}

  h1 {{
    margin: 0;
    font-family: var(--mono);
    font-weight: 600;
    font-size: clamp(20px, 2.6vw, 28px);
    letter-spacing: 0.01em;
    color: var(--text);
  }}

  h1 .accent {{ color: var(--accent); }}

  .subtitle {{
    font-size: 13px;
    color: var(--text-dim);
    max-width: 78ch;
    line-height: 1.55;
  }}

  .header-top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 20px;
    flex-wrap: wrap;
  }}

  .header-text {{
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}

  .btn-3d {{
    flex: none;
    font-family: var(--mono);
    font-size: 12px;
    letter-spacing: 0.03em;
    color: #12151a;
    background: var(--accent);
    padding: 10px 16px;
    border-radius: 8px;
    text-decoration: none;
    font-weight: 600;
    white-space: nowrap;
    filter: brightness(1);
    transition: filter 0.1s ease;
  }}

  .btn-3d:hover {{ filter: brightness(1.12); }}

  .section-info {{
    margin: 4px 32px 4px;
    padding: 14px 18px;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    border-radius: 10px;
    backdrop-filter: blur(10px);
  }}

  .section-info-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    font-size: 12.5px;
    color: var(--text-dim);
    margin-bottom: 10px;
  }}

  .section-info-row b {{ color: var(--text); }}

  .section-info-sep {{ color: var(--text-faint); }}

  .btn-3d-sm {{
    padding: 6px 12px;
    font-size: 11px;
    margin-left: auto;
  }}

  .position-bar {{
    display: flex;
    align-items: center;
    gap: 10px;
  }}

  .position-bar-label {{
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-faint);
    flex: none;
  }}

  .position-bar-track {{
    flex: 1;
    height: 5px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.08);
    position: relative;
  }}

  .position-bar-dot {{
    position: absolute;
    top: 50%;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--accent);
    transform: translate(-50%, -50%);
    box-shadow: 0 0 0 3px rgba(224, 164, 88, 0.25);
  }}

  .position-note {{
    font-size: 11px;
    color: var(--text-faint);
    margin-top: 8px;
    line-height: 1.5;
  }}

  .layout {{
    display: flex;
    gap: 18px;
    padding: 8px 32px 32px;
    align-items: flex-start;
    flex-wrap: wrap;
  }}

  .stage-wrap {{
    position: relative;
    flex: 1 1 700px;
    min-width: 320px;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid var(--panel-border);
    background: #05070a;
    line-height: 0;
    user-select: none;
  }}

  .stage-wrap img {{
    display: block;
    width: 100%;
    height: auto;
  }}

  .stage-wrap svg {{
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }}

  #diagramClip rect {{ transition: none; }}

  path[data-sid] {{
    stroke: rgba(10, 12, 15, 0.55);
    stroke-width: 1.4;
    vector-effect: non-scaling-stroke;
    cursor: pointer;
    transition: filter 0.08s ease, stroke-width 0.08s ease;
  }}

  path[data-sid]:hover,
  path[data-sid].pinned,
  path[data-sid].hover-glow {{
    filter: brightness(1.35) saturate(1.15);
    stroke: #fff;
    stroke-width: 2.6;
  }}

  #tractsLayer path[data-sid] {{
    stroke: rgba(10, 12, 15, 0.35);
    stroke-width: 0.8;
  }}

  .divider {{
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--accent);
    box-shadow: 0 0 8px rgba(224, 164, 88, 0.7);
    pointer-events: none;
  }}

  .divider::before {{
    content: "";
    position: absolute;
    top: 50%;
    left: 50%;
    width: 22px;
    height: 22px;
    transform: translate(-50%, -50%);
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 0 4px rgba(18, 21, 26, 0.85);
  }}

  .side-label {{
    position: absolute;
    top: 10px;
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: rgba(233, 237, 241, 0.75);
    background: rgba(5, 7, 10, 0.55);
    padding: 4px 8px;
    border-radius: 5px;
    pointer-events: none;
  }}

  .side-label.left {{ left: 10px; }}
  .side-label.right {{ right: 10px; }}

  .tooltip {{
    position: fixed;
    pointer-events: none;
    z-index: 50;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    backdrop-filter: blur(10px);
    border-radius: 8px;
    padding: 8px 11px;
    font-size: 12.5px;
    max-width: 320px;
    opacity: 0;
    transform: translate(14px, 14px);
    transition: opacity 0.08s ease;
  }}

  .tooltip.show {{ opacity: 1; }}

  .tooltip .acr {{
    font-family: var(--mono);
    color: var(--accent);
    font-weight: 600;
    font-size: 13px;
  }}

  .tooltip .full {{
    color: var(--text);
    margin-top: 2px;
  }}

  .tooltip .swatch {{
    display: inline-block;
    width: 9px;
    height: 9px;
    border-radius: 2px;
    margin-right: 6px;
    vertical-align: middle;
  }}

  .panel {{
    background: var(--panel);
    border: 1px solid var(--panel-border);
    backdrop-filter: blur(10px);
    border-radius: 10px;
    padding: 16px 18px;
    flex: 0 0 260px;
    min-width: 230px;
  }}

  .panel h2 {{
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-faint);
    margin: 0 0 12px;
  }}

  .search-wrap {{
    position: relative;
    margin-bottom: 18px;
  }}

  .search-wrap input {{
    width: 100%;
    background: #0d1015;
    border: 1px solid var(--panel-border);
    border-radius: 7px;
    color: var(--text);
    font-size: 12.5px;
    padding: 9px 10px;
    font-family: var(--sans);
    outline: none;
  }}

  .search-wrap input:focus {{ border-color: var(--accent); }}

  .search-results {{
    position: absolute;
    left: 0;
    right: 0;
    top: calc(100% + 4px);
    background: rgba(18, 21, 26, 0.98);
    border: 1px solid var(--panel-border);
    border-radius: 7px;
    max-height: 240px;
    overflow-y: auto;
    z-index: 30;
    display: none;
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.4);
  }}

  .search-results.show {{ display: block; }}

  .search-result-row, .history-row {{
    padding: 7px 10px;
    font-size: 12px;
    cursor: pointer;
    display: flex;
    gap: 8px;
    align-items: baseline;
  }}

  .search-result-row:hover, .history-row:hover {{
    background: rgba(255, 255, 255, 0.06);
  }}

  .search-result-row .acr, .history-row .acr {{
    font-family: var(--mono);
    color: var(--accent);
    font-weight: 600;
    flex: none;
    min-width: 58px;
  }}

  .search-result-row .full, .history-row .full {{
    color: var(--text-dim);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}

  .search-empty {{
    padding: 10px;
    font-size: 12px;
    color: var(--text-faint);
  }}

  .history-head {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
  }}

  .text-btn {{
    background: none;
    border: none;
    color: var(--text-faint);
    font-family: var(--sans);
    font-size: 11px;
    cursor: pointer;
    padding: 0 0 12px;
    text-decoration: underline;
  }}

  .text-btn:hover {{ color: var(--text-dim); }}

  .history-list {{
    max-height: 190px;
    overflow-y: auto;
    border: 1px solid var(--panel-border);
    border-radius: 7px;
    margin-bottom: 4px;
  }}

  .history-list .hint {{
    font-size: 11.5px;
    color: var(--text-faint);
    padding: 10px;
  }}

  .history-row + .history-row {{ border-top: 1px solid var(--panel-border); }}

  .pinned-card {{
    min-height: 64px;
    border-bottom: 1px solid var(--panel-border);
    padding-bottom: 12px;
    margin-bottom: 14px;
  }}

  .pinned-card .acr {{
    font-family: var(--mono);
    color: var(--accent);
    font-size: 15px;
    font-weight: 600;
  }}

  .pinned-card .full {{
    font-size: 13px;
    color: var(--text);
    margin-top: 3px;
    line-height: 1.4;
  }}

  .pinned-card .hint {{
    font-size: 12px;
    color: var(--text-faint);
  }}

  .control-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 7px 0;
    font-size: 12.5px;
    color: var(--text-dim);
  }}

  .control-row input[type="range"] {{
    width: 110px;
  }}

  .control-row label {{
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
  }}

  .help {{
    font-size: 11.5px;
    color: var(--text-faint);
    line-height: 1.6;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--panel-border);
  }}

  .source {{
    font-size: 10.5px;
    color: var(--text-faint);
    padding: 0 32px 24px;
    font-family: var(--mono);
  }}
</style>

<nav class="crossnav">{nav_html}</nav>

<header class="ui">
  <div class="header-top">
    <div class="header-text">
      <div class="eyebrow">{eyebrow}</div>
      <h1>{title_html}</h1>
      <div class="subtitle">{subtitle}</div>
    </div>
  </div>
</header>

<div class="section-info">
  <div class="section-info-row">
    <span><b>{size_w_mm} &times; {size_h_mm} mm</b> plate size</span>
    <span class="section-info-sep">&middot;</span>
    <span>plate <b>{series_index}</b> of <b>{series_total}</b> in this series</span>
    <a class="btn-3d btn-3d-sm" href="{slice_href}">Locate this slice in 3D &#8599;</a>
  </div>
  <div class="position-bar">
    <span class="position-bar-label">{position_label_left}</span>
    <div class="position-bar-track"><div class="position-bar-dot" style="left:{position_frac}%"></div></div>
    <span class="position-bar-label">{position_label_right}</span>
  </div>
  <div class="position-note">{position_note}</div>
</div>

<div class="layout">
  <div class="stage-wrap" id="stage">
    <img id="photo" src="data:image/jpeg;base64,{photo_b64}" alt="Nissl photo" draggable="false" />
    <svg id="overlay" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet">
      <defs>
        <clipPath id="diagramClip">
          <rect id="clipRect" x="{half_width}" y="0" width="{half_width}" height="{height}" />
        </clipPath>
      </defs>
      <g id="structuresLayer" clip-path="url(#diagramClip)" style="opacity:0.92">
        {structures_svg}
      </g>
      <g id="tractsLayer" clip-path="url(#diagramClip)" style="opacity:0; pointer-events:none">
        {tracts_svg}
      </g>
    </svg>
    <div class="divider" id="divider"></div>
    <div class="side-label left">Nissl photo</div>
    <div class="side-label right">Region diagram</div>
  </div>

  <div class="panel">
    <h2>Find a Region</h2>
    <div class="search-wrap">
      <input type="text" id="searchInput" placeholder="type acronym or name&hellip;" autocomplete="off" />
      <div class="search-results" id="searchResults"></div>
    </div>

    <h2>Selected Region</h2>
    <div class="pinned-card" id="pinnedCard">
      <div class="hint">Hover a region on the diagram side&hellip;</div>
    </div>

    <div class="history-head">
      <h2>Recently Viewed</h2>
      <button type="button" class="text-btn" id="clearHistory">clear</button>
    </div>
    <div class="history-list" id="historyList">
      <div class="hint">Regions you click or search for will show up here for quick recall.</div>
    </div>

    <h2>Display</h2>
    <div class="control-row">
      <label><input type="checkbox" id="tractsToggle" /> Show fiber tracts</label>
    </div>
    <div class="control-row">
      <span>Diagram opacity</span>
      <input type="range" id="opacitySlider" min="20" max="100" value="92" />
    </div>
    <div class="control-row">
      <span>Split position</span>
      <input type="range" id="splitSlider" min="0" max="100" value="50" />
    </div>

    <div class="help">
      Data: Allen Institute Brain Atlas API &mdash; Structure ontology (full names), per-plate region SVG
      (boundaries), and the reference photo. {struct_count} structures resolvable on this plate; drag the
      divider on the image itself too.
    </div>
  </div>
</div>

<div class="tooltip" id="tooltip">
  <div class="acr"></div>
  <div class="full"></div>
</div>

<div class="source">
  source: brain-map.org (Allen Institute) &middot; {source_note}
</div>

<script>
  const NAMES = {names_json};

  const stage = document.getElementById("stage");
  const svg = document.getElementById("overlay");
  const clipRect = document.getElementById("clipRect");
  const divider = document.getElementById("divider");
  const structuresLayer = document.getElementById("structuresLayer");
  const tractsLayer = document.getElementById("tractsLayer");
  const tooltip = document.getElementById("tooltip");
  const tooltipAcr = tooltip.querySelector(".acr");
  const tooltipFull = tooltip.querySelector(".full");
  const pinnedCard = document.getElementById("pinnedCard");
  const tractsToggle = document.getElementById("tractsToggle");
  const opacitySlider = document.getElementById("opacitySlider");
  const splitSlider = document.getElementById("splitSlider");
  const searchInput = document.getElementById("searchInput");
  const searchResults = document.getElementById("searchResults");
  const historyList = document.getElementById("historyList");
  const clearHistoryBtn = document.getElementById("clearHistory");

  const VIEW_W = {width};
  const VIEW_H = {height};
  const HISTORY_KEY = "{history_key}";
  const HISTORY_MAX = 40;

  let pinnedSid = null;

  function infoFor(sid) {{
    const info = NAMES[sid];
    if (!info) return null;
    return info;
  }}

  function renderCard(el, sid, showHint) {{
    const info = infoFor(sid);
    if (!info) {{ el.innerHTML = '<div class="hint">Unknown region</div>'; return; }}
    el.innerHTML =
      '<span class="swatch" style="background:#' + info.color + '"></span>' +
      '<span class="acr">' + info.acronym + '</span>' +
      '<div class="full">' + info.name + '</div>' +
      (showHint ? '<div class="hint" style="margin-top:6px">click elsewhere to unpin</div>' : '');
  }}

  function setSplit(pct) {{
    pct = Math.max(0, Math.min(100, pct));
    const x = (pct / 100) * VIEW_W;
    clipRect.setAttribute("x", x);
    clipRect.setAttribute("width", VIEW_W - x);
    divider.style.left = pct + "%";
    splitSlider.value = pct;
  }}

  // pointer highlighting via delegation
  function allPathsWithSid(sid) {{
    return svg.querySelectorAll('path[data-sid="' + sid + '"]');
  }}

  svg.addEventListener("pointerover", (e) => {{
    const p = e.target.closest("path[data-sid]");
    if (!p) return;
    const sid = p.getAttribute("data-sid");
    allPathsWithSid(sid).forEach((el) => el.classList.add("hover-glow"));
    if (!pinnedSid) renderCard(pinnedCard, sid, false);
    tooltipAcr.textContent = (infoFor(sid) || {{}}).acronym || sid;
    tooltipFull.textContent = (infoFor(sid) || {{}}).name || "";
    tooltip.classList.add("show");
  }});

  svg.addEventListener("pointerout", (e) => {{
    const p = e.target.closest("path[data-sid]");
    if (!p) return;
    const sid = p.getAttribute("data-sid");
    allPathsWithSid(sid).forEach((el) => el.classList.remove("hover-glow"));
    tooltip.classList.remove("show");
    if (!pinnedSid) pinnedCard.innerHTML = '<div class="hint">Hover a region on the diagram side&hellip;</div>';
  }});

  svg.addEventListener("pointermove", (e) => {{
    tooltip.style.left = "0px";
    tooltip.style.top = "0px";
    tooltip.style.transform = "translate(" + (e.clientX + 14) + "px," + (e.clientY + 14) + "px)";
  }});

  function unpinRegion() {{
    pinnedSid = null;
    document.querySelectorAll("path.pinned").forEach((el) => el.classList.remove("pinned"));
    pinnedCard.innerHTML = '<div class="hint">Hover a region on the diagram side&hellip;</div>';
  }}

  function pinRegion(sid) {{
    document.querySelectorAll("path.pinned").forEach((el) => el.classList.remove("pinned"));
    pinnedSid = sid;
    allPathsWithSid(sid).forEach((el) => el.classList.add("pinned"));
    renderCard(pinnedCard, sid, true);
    recordHistory(sid);
  }}

  // if the target region is currently hidden under the photo half, slide the
  // divider left just enough to reveal it before pinning
  function revealAndPin(sid) {{
    const el = svg.querySelector('path[data-sid="' + sid + '"]');
    if (el) {{
      const bbox = el.getBBox();
      const dividerX = (Number(splitSlider.value) / 100) * VIEW_W;
      if (bbox.x + bbox.width < dividerX + 4) {{
        setSplit(Math.max(0, (bbox.x / VIEW_W) * 100 - 3));
      }}
    }}
    pinRegion(sid);
    pinnedCard.scrollIntoView({{ behavior: "smooth", block: "nearest" }});
  }}

  svg.addEventListener("click", (e) => {{
    const p = e.target.closest("path[data-sid]");
    if (!p) {{ unpinRegion(); return; }}
    const sid = p.getAttribute("data-sid");
    if (pinnedSid === sid) {{
      unpinRegion();
    }} else {{
      pinRegion(sid);
    }}
  }});

  // ---- recently-viewed history (persisted in localStorage) ----
  function loadHistory() {{
    try {{
      return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    }} catch (e) {{
      return [];
    }}
  }}

  function saveHistory(list) {{
    try {{ localStorage.setItem(HISTORY_KEY, JSON.stringify(list)); }} catch (e) {{}}
  }}

  function renderHistory() {{
    const list = loadHistory();
    if (!list.length) {{
      historyList.innerHTML = '<div class="hint">Regions you click or search for will show up here for quick recall.</div>';
      return;
    }}
    historyList.innerHTML = list.map((h) => {{
      const info = infoFor(h.sid) || {{ acronym: h.sid, name: "" }};
      return '<div class="history-row" data-sid="' + h.sid + '">' +
        '<span class="acr">' + info.acronym + '</span>' +
        '<span class="full">' + info.name + '</span>' +
      '</div>';
    }}).join("");
  }}

  function recordHistory(sid) {{
    let list = loadHistory().filter((h) => h.sid !== sid);
    list.unshift({{ sid: sid, ts: Date.now() }});
    if (list.length > HISTORY_MAX) list = list.slice(0, HISTORY_MAX);
    saveHistory(list);
    renderHistory();
  }}

  historyList.addEventListener("click", (e) => {{
    const row = e.target.closest(".history-row[data-sid]");
    if (!row) return;
    revealAndPin(row.getAttribute("data-sid"));
  }});

  clearHistoryBtn.addEventListener("click", () => {{
    saveHistory([]);
    renderHistory();
  }});

  // ---- search ----
  const searchEntries = Object.entries(NAMES);

  function runSearch(q) {{
    q = q.trim().toLowerCase();
    if (!q) {{
      searchResults.classList.remove("show");
      searchResults.innerHTML = "";
      return;
    }}
    const matches = searchEntries
      .filter(([sid, info]) => info.acronym.toLowerCase().includes(q) || info.name.toLowerCase().includes(q))
      .slice(0, 30);
    searchResults.innerHTML = matches.length
      ? matches.map(([sid, info]) =>
          '<div class="search-result-row" data-sid="' + sid + '">' +
            '<span class="acr">' + info.acronym + '</span>' +
            '<span class="full">' + info.name + '</span>' +
          '</div>'
        ).join("")
      : '<div class="search-empty">No match</div>';
    searchResults.classList.add("show");
  }}

  searchInput.addEventListener("input", () => runSearch(searchInput.value));
  searchInput.addEventListener("focus", () => {{ if (searchInput.value) runSearch(searchInput.value); }});
  searchInput.addEventListener("keydown", (e) => {{
    if (e.key === "Enter") {{
      const first = searchResults.querySelector(".search-result-row[data-sid]");
      if (first) {{
        revealAndPin(first.getAttribute("data-sid"));
        searchResults.classList.remove("show");
        searchInput.value = "";
      }}
    }} else if (e.key === "Escape") {{
      searchResults.classList.remove("show");
      searchInput.blur();
    }}
  }});

  searchResults.addEventListener("click", (e) => {{
    const row = e.target.closest(".search-result-row[data-sid]");
    if (!row) return;
    revealAndPin(row.getAttribute("data-sid"));
    searchResults.classList.remove("show");
    searchInput.value = "";
  }});

  document.addEventListener("click", (e) => {{
    if (!e.target.closest(".search-wrap")) searchResults.classList.remove("show");
  }});

  // draggable split divider (only starts when grabbing the handle itself,
  // so clicking a region elsewhere on the image can't also yank the divider)
  let dragging = false;
  function pctFromEvent(e) {{
    const rect = stage.getBoundingClientRect();
    return ((e.clientX - rect.left) / rect.width) * 100;
  }}
  divider.style.pointerEvents = "auto";
  divider.style.cursor = "ew-resize";
  divider.addEventListener("pointerdown", (e) => {{
    dragging = true;
    e.stopPropagation();
  }});
  window.addEventListener("pointermove", (e) => {{
    if (!dragging) return;
    setSplit(pctFromEvent(e));
  }});
  window.addEventListener("pointerup", () => {{ dragging = false; }});

  splitSlider.addEventListener("input", () => setSplit(Number(splitSlider.value)));

  tractsToggle.addEventListener("change", () => {{
    tractsLayer.style.opacity = tractsToggle.checked ? String(Number(opacitySlider.value) / 100) : "0";
    tractsLayer.style.pointerEvents = tractsToggle.checked ? "auto" : "none";
  }});

  opacitySlider.addEventListener("input", () => {{
    const v = Number(opacitySlider.value) / 100;
    structuresLayer.style.opacity = String(v);
    if (tractsToggle.checked) tractsLayer.style.opacity = String(v);
  }});

  setSplit(50);
  renderHistory();
</script>
"""


def main():
    keys = sys.argv[1:] or list(PLATES.keys())
    for k in keys:
        build(k)


if __name__ == "__main__":
    main()
