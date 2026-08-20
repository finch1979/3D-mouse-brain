"""
Fetch a coronal reference-atlas plate from the Allen Mouse Brain Atlas API
that shows one or more target brain regions (by acronym).

API docs: https://brain-map.org/support/documentation/api-for-mouse-brain-atlas

Usage:
    python -m mouse_atlas.fetch.atlas_plate
    python -m mouse_atlas.fetch.atlas_plate --acronyms MOp MOs RSP
    python -m mouse_atlas.fetch.atlas_plate --acronyms VISp --plate-frac 0.6

Workflow:
    1. Look up each target structure's id / color via the Structure API.
    2. List every plate (AtlasImage) in the P56 mouse coronal reference
       atlas (atlas_id=1), ordered anterior -> posterior.
    3. Download a handful of low-res preview images spread across the
       series (atlas/preview/) so a human can eyeball which plate best
       shows the target region(s) together.
    4. Download the chosen plate at full resolution into atlas/.

There is no reliable "structure -> atlas image" endpoint in this API, so
step 3's preview-and-pick step is a deliberate manual checkpoint rather
than something fully automated.
"""

import argparse
import json
import os

import requests

from mouse_atlas.common.config import load_config
from mouse_atlas.common.paths import OUTPUTS_DIR

P56_CONFIG = load_config("p56")

BASE = "http://api.brain-map.org/api/v2"
ATLAS_ID = P56_CONFIG["atlas_id"]  # Mouse, P56, Coronal reference atlas
DEFAULT_ACRONYMS = P56_CONFIG["default_acronyms"]
OUT_DIR = str(OUTPUTS_DIR / "P56")
PREVIEW_DIR = os.path.join(OUT_DIR, "preview")


def lookup_structure(acronym):
    url = f"{BASE}/data/Structure/query.json"
    params = {"criteria": f"[acronym$eq'{acronym}']"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    rows = [row for row in r.json()["msg"] if row["acronym"] == acronym]
    if not rows:
        raise ValueError(f"No structure found for acronym {acronym!r}")
    row = rows[0]
    return {
        "id": row["id"],
        "name": row["name"],
        "acronym": row["acronym"],
        "color": row["color_hex_triplet"],
    }


def list_atlas_images(atlas_id=ATLAS_ID):
    url = f"{BASE}/data/query.json"
    criteria = (
        "model::AtlasImage,rma::criteria,[annotated$eqtrue],"
        f"atlas_data_set(atlases[id$eq{atlas_id}]),"
        "rma::options[order$eq'section_number'][num_rows$eqall]"
    )
    r = requests.get(url, params={"criteria": criteria}, timeout=60)
    r.raise_for_status()
    images = r.json()["msg"]
    images.sort(key=lambda im: im["section_number"])
    return images


def download_image(image_id, out_path, downsample=4, annotation=True):
    url = f"{BASE}/atlas_image_download/{image_id}"
    params = {"downsample": downsample, "annotation": str(annotation).lower()}
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(r.content)
    return out_path


def pick_preview_fractions(n=5, lo=0.30, hi=0.55):
    if n == 1:
        return [(lo + hi) / 2]
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--acronyms", nargs="+", default=DEFAULT_ACRONYMS,
        help="Structure acronyms to look up (Allen ontology naming, e.g. MOp MOs RSP)",
    )
    parser.add_argument(
        "--atlas-id", type=int, default=ATLAS_ID,
        help="Reference atlas id (default 1 = Mouse, P56, Coronal)",
    )
    parser.add_argument(
        "--n-previews", type=int, default=5,
        help="How many spread-out low-res preview plates to download for manual inspection",
    )
    parser.add_argument(
        "--plate-frac", type=float, default=None,
        help="If set, skip previews and directly download the plate at this fraction "
             "(0.0=most anterior, 1.0=most posterior) of the series at full resolution.",
    )
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Looking up structures: {args.acronyms}")
    structures = {a: lookup_structure(a) for a in args.acronyms}
    for a, s in structures.items():
        print(f"  {a}: id={s['id']} name={s['name']!r} color=#{s['color']}")

    regions_path = os.path.join(OUT_DIR, "regions.json")
    with open(regions_path, "w", encoding="utf-8") as f:
        json.dump(structures, f, indent=2, ensure_ascii=False)
    print(f"Wrote {regions_path}")

    print(f"Listing atlas plates for atlas_id={args.atlas_id} ...")
    images = list_atlas_images(args.atlas_id)
    total = len(images)
    print(f"Found {total} plates (section_number range "
          f"{images[0]['section_number']} .. {images[-1]['section_number']})")

    if args.plate_frac is not None:
        idx = min(total - 1, max(0, round(args.plate_frac * (total - 1))))
        im = images[idx]
        out_path = os.path.join(
            OUT_DIR, f"plate_idx{idx}_section{im['section_number']}.jpg"
        )
        download_image(im["id"], out_path, downsample=1, annotation=True)
        print(f"Downloaded full-res plate -> {out_path}")
        return

    fracs = pick_preview_fractions(args.n_previews)
    print(f"Downloading {len(fracs)} preview plates spread across the series "
          f"for manual inspection...")
    for frac in fracs:
        idx = min(total - 1, max(0, round(frac * (total - 1))))
        im = images[idx]
        out_path = os.path.join(
            PREVIEW_DIR, f"idx{idx}_section{im['section_number']}_frac{frac:.2f}.jpg"
        )
        download_image(im["id"], out_path, downsample=6, annotation=True)
        print(f"  frac={frac:.2f} idx={idx} section={im['section_number']} -> {out_path}")

    print(
        "\nPreviews saved. Inspect them, then re-run with "
        "--plate-frac <fraction of the winning preview> to fetch it full-resolution."
    )


if __name__ == "__main__":
    main()
