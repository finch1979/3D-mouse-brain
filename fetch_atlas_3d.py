"""
Download 3D structure mesh files (.obj) for Allen Mouse Brain CCF regions.

These meshes are pre-computed isosurfaces of the CCFv3 2017 annotation
volume, served as static files (not through the RMA query API):

    http://download.alleninstitute.org/informatics-archive/current-release/
        mouse_ccf/annotation/ccf_2017/structure_meshes/{structure_id}.obj

Usage:
    python fetch_atlas_3d.py --acronyms MOp MOs RSP
    python fetch_atlas_3d.py --acronyms VISp --no-root

By default also fetches structure_id=997 ("root", the whole-brain outline)
for spatial context, unless --no-root is passed.
"""

import argparse
import json
import os

import requests

from fetch_atlas_plate import lookup_structure, OUT_DIR

MESH_BASE = (
    "http://download.alleninstitute.org/informatics-archive/current-release/"
    "mouse_ccf/annotation/ccf_2017/structure_meshes/{}.obj"
)
MESH_DIR = os.path.join(OUT_DIR, "mesh")
ROOT_STRUCTURE = {"id": 997, "name": "Whole brain outline", "acronym": "root", "color": "CCCCCC"}


def download_mesh(structure_id):
    out_path = os.path.join(MESH_DIR, f"{structure_id}.obj")
    if os.path.exists(out_path):
        return out_path
    url = MESH_BASE.format(structure_id)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    os.makedirs(MESH_DIR, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(r.content)
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acronyms", nargs="+", default=["MOp", "MOs", "RSP"])
    parser.add_argument("--no-root", action="store_true", help="Skip the whole-brain context mesh")
    args = parser.parse_args()

    structures = {a: lookup_structure(a) for a in args.acronyms}
    if not args.no_root:
        structures["root"] = ROOT_STRUCTURE

    manifest = {}
    for acronym, s in structures.items():
        path = download_mesh(s["id"])
        size_kb = os.path.getsize(path) / 1024
        print(f"{acronym}: id={s['id']} name={s['name']!r} -> {path} ({size_kb:.0f} KB)")
        manifest[acronym] = {**s, "mesh_path": os.path.relpath(path, OUT_DIR)}

    manifest_path = os.path.join(MESH_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
