"""
Build a self-contained interactive HTML page for a real coronal slice of the
DeMBA "Allen segmentation" P15 mouse brain atlas (BrainGlobe Atlas API).

Unlike the plain Allen Developing Mouse Brain Atlas (which only ships a fixed
sagittal 2D plate series with coarse prosomeric labels), DeMBA is a true 3D
volume where the *adult* Allen CCFv3 ontology (MOp / MOs / RSP / ... down to
cortical layers) has been non-linearly registered onto a P15-shaped brain.
That means we can cut our own coronal slice and get real MOp/MOs/RSP
boundaries - something neither the raw Allen API nor the plain P14 plate can
give us. The tradeoff (surfaced in the page itself): those boundaries are
computationally warped from the adult atlas, not independently re-annotated
at P15.

Usage:
    python -m mouse_atlas.build.demba_p15
"""

import base64
import io
import json
import os

import numpy as np
from PIL import Image
from scipy.ndimage import zoom
from skimage import measure

from brainglobe_atlasapi import BrainGlobeAtlas

from mouse_atlas.build import plate_atlas as bpa
from mouse_atlas.common.config import load_config
from mouse_atlas.common.paths import OUTPUTS_DIR

P15_CONFIG = load_config("p15")

OUT_DIR = str(OUTPUTS_DIR / "P15")
os.makedirs(OUT_DIR, exist_ok=True)

ATLAS_NAME = P15_CONFIG["brainglobe_atlas_name"]
SLICE_IDX = 222  # AP voxel index; chosen so MOp/MOs/RSP are all well represented
UPSAMPLE = 4
RESOLUTION_UM = P15_CONFIG["resolution_um"]

OUT_FILE = "coronal_p15_demba_interactive.html"

# adult mesh's root X (AP) half-extent, from the earlier motor_cortex_3d.html
# bounding-box probe: root X range [-6604.665, 6604.665]
ADULT_ROOT_X_MIN = -6604.665
ADULT_ROOT_X_MAX = 6604.665


def contour_paths_for_mask(mask):
    contours = measure.find_contours(mask.astype(np.uint8), level=0.5)
    parts = []
    for c in contours:
        if len(c) < 3:
            continue
        pts = [f"{pt[1]:.1f},{pt[0]:.1f}" for pt in c]
        parts.append("M " + " L ".join(pts) + " Z")
    return parts


def main():
    print(f"Loading {ATLAS_NAME} ...")
    atlas = BrainGlobeAtlas(ATLAS_NAME)

    ref = atlas.reference[SLICE_IDX, :, :].astype(np.float32)
    ann = atlas.annotation[SLICE_IDX, :, :].astype(np.int64)
    orig_h, orig_w = ann.shape

    print("Upsampling...")
    ref_up = zoom(ref, UPSAMPLE, order=1)
    ann_up = zoom(ann, UPSAMPLE, order=0)
    height, width = ann_up.shape

    refn = ref_up - ref_up.min()
    refn = refn / (refn.max() + 1e-9) * 255
    img = Image.fromarray(refn.astype(np.uint8)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    photo_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    print(f"photo: {width}x{height}, {len(photo_b64)/1024:.0f} KB base64")

    ids_present = [int(i) for i in np.unique(ann_up) if i != 0]
    print(f"{len(ids_present)} structures present in this slice")

    paths = []
    names = {}
    for sid in ids_present:
        try:
            info = atlas.structures[sid]
        except KeyError:
            continue
        mask = ann_up == sid
        if mask.sum() < 8:
            continue
        d_list = contour_paths_for_mask(mask)
        if not d_list:
            continue
        r, g, b = info["rgb_triplet"]
        fill = f"#{r:02x}{g:02x}{b:02x}"
        for d in d_list:
            paths.append((str(sid), fill, d))
        names[str(sid)] = {
            "acronym": info["acronym"],
            "name": info["name"],
            "color": f"{r:02x}{g:02x}{b:02x}",
        }

    print(f"{len(paths)} contour paths, {len(names)} named structures")

    structures_groups = [("", paths)]
    tracts_groups = []

    size_w_mm = orig_w * RESOLUTION_UM / 1000
    size_h_mm = orig_h * RESOLUTION_UM / 1000
    series_total = atlas.shape[0]
    position_frac = SLICE_IDX / (series_total - 1) * 100

    # the P15 3D model (motor_cortex_3d_p15.html) is built from this exact same
    # DeMBA volume, so if it's already been built we get a precise plane
    # position (voxel_row * resolution - mesh center), not a guess
    meta_path = os.path.join(OUT_DIR, "mesh_meta.json")
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path, encoding="utf-8"))
        p15_x = SLICE_IDX * RESOLUTION_UM - meta["center"][0]
        slice_query = "?" + "&".join([
            "axis=x",
            f"pos={p15_x:.1f}",
            "label=" + "Coronal%20slice%20~P15%20(DeMBA)",
            "approx=0",
        ])
        slice_href = f"motor_cortex_3d_p15.html{slice_query}"
    else:
        adult_x = ADULT_ROOT_X_MIN + (SLICE_IDX / (series_total - 1)) * (ADULT_ROOT_X_MAX - ADULT_ROOT_X_MIN)
        slice_query = "?" + "&".join([
            "axis=x",
            f"pos={adult_x:.1f}",
            "label=" + "Coronal%20slice%20~P15%20(DeMBA%2C%20position%20mapped%20by%20fraction)",
            "approx=1",
        ])
        slice_href = f"../P56/motor_cortex_3d.html{slice_query}"

    # the nav bar's plain "3D (P56 adult)" pill should stay an unparametrized
    # link regardless - only the dedicated CTA button (slice_href) above
    # carries this plate's own locator query
    nav_html = bpa.render_nav("p15_coronal_demba", "P15")

    html = bpa.TEMPLATE.format(
        width=width,
        height=height,
        half_width=float(width) / 2,
        photo_b64=photo_b64,
        structures_svg=bpa.groups_to_svg_markup(structures_groups),
        tracts_svg=bpa.groups_to_svg_markup(tracts_groups),
        names_json=json.dumps(names, ensure_ascii=False),
        eyebrow="DeMBA (Kim Lab) &middot; Allen CCFv3 segmentation warped to P15 &middot; coronal, voxel row 222/564",
        title_html='Interactive <span class="accent">P15 Coronal Atlas</span> <span class="accent">(DeMBA)</span>',
        subtitle=(
            "A real coronal slice through the DeMBA P15 volume, with the adult Allen CCFv3 ontology "
            "(MOp, MOs, RSP, down to cortical layers) non-linearly registered onto this age's brain shape. "
            "<b>These boundaries are computationally warped from the adult atlas, not independently "
            "re-annotated at P15</b> &mdash; treat them as a well-informed estimate, not ground truth. "
            "Drag the divider to compare STPT template vs diagram; hover or click any region for its full name."
        ),
        source_note=(
            "BrainGlobe Atlas API &middot; demba_allen_seg_dev_mouse_p15_25um &middot; "
            "DOI: 10.25493/V3AH-HK7 &middot; AP voxel row 222 of 564 (25&micro;m/voxel)"
        ),
        history_key="mouseAtlasHistory_p15_demba_coronal_v1",
        nav_html=nav_html,
        struct_count=len(names),
        title_plain="Coronal Atlas &middot; P15 (DeMBA)",
        size_w_mm=f"{size_w_mm:.2f}",
        size_h_mm=f"{size_h_mm:.2f}",
        series_index=SLICE_IDX + 1,
        series_total=series_total,
        position_frac=f"{position_frac:.1f}",
        position_label_left="Anterior",
        position_label_right="Posterior",
        position_note=(
            "Voxel row 222 of 564 along the AP axis of the real DeMBA P15 volume (25&micro;m/voxel) &mdash; "
            "this is an exact index into the actual 3D data, not an estimate."
        ),
        slice_href=slice_href,
    )

    out_path = os.path.join(OUT_DIR, OUT_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out_path} ({os.path.getsize(out_path) / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
