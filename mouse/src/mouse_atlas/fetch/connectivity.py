"""
Fetch REAL region-to-region projection strengths from the Allen Mouse Brain
Connectivity Atlas (product 5, adult C57BL/6J + Cre lines, CCFv3 space).

This is the Phase 2 replacement for the schematic teaching graph in
build/connectivity_data.py. It writes the SAME schema, so the viewer needs
no change: edges simply carry evidence_class EXPERIMENTAL instead of
SCHEMATIC, with a real n_experiments and download_date.

WHAT THE NUMBERS MEAN - normalized_projection_volume from the Allen
ProjectionStructureUnionize model: the volume of segmented axonal signal
found in a target structure, normalized by injection volume. It is a
MESOSCALE ANATOMICAL measure of how much axon an injection deposits in a
target. It is NOT synapse count, NOT connection probability, and NOT
functional strength.

METHOD
  1. Pull the graph-1 structure tree once, for descendant tests.
  2. Pull every product-5 experiment with its primary injection structure.
  3. An experiment counts as a source for region R when its primary
     injection structure is R or a descendant of R.
  4. Pull unionize rows (is_injection=false, hemisphere_id=3 i.e. both)
     for those experiments restricted to our target structures. Allen's
     unionize rows for a parent structure already aggregate descendants.
  5. Edge weight = MEAN normalized_projection_volume across the source's
     experiments. Self-edges are dropped.

CAVEATS worth keeping in the page, not just the code:
  - Injection counts are wildly uneven (VISp ~139 experiments, PSV ~4), so
    a mean from 4 experiments is far less stable than one from 139. The
    per-edge n_experiments is carried through for exactly this reason.
  - Product 5 mixes wild-type and Cre-line injections. A Cre line samples a
    genetically defined subpopulation, not the whole structure.
  - Absence of an edge here means "little or no bulk axonal signal in this
    atlas", not "no connection exists".

Usage:
    python -m mouse_atlas.fetch.connectivity
    python -m mouse_atlas.fetch.connectivity --refresh    # ignore the cache
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone

import requests

from mouse_atlas.common.paths import DATA_CACHE_DIR

BASE = "http://api.brain-map.org/api/v2/data/query.json"
PRODUCT_ID = 5
GRAPH_ID = 1
HEMISPHERE_BOTH = 3
PAGE = 500
CACHE_DIR = DATA_CACHE_DIR / "P56" / "connectivity"
OUT_PATH = CACHE_DIR / "allen_projection_p56.json"

# The regions this graph covers. Every one has a precomputed CCFv3 mesh in
# outputs/P56/mesh/ and at least one product-5 injection experiment.
# None is an ancestor of another, so sources never double-count.
# CA2 (423) is deliberately absent: zero injection experiments.
# HPF (1089) is absent because CA1/CA3/DG are its children.
REGIONS = [
    ("VISp", 385), ("LGd", 170), ("SCs", 302), ("LP", 218),
    ("SSp-bfd", 329), ("VPM", 733), ("PSV", 7), ("SPVC", 429),
    ("MOB", 507), ("AON", 159), ("PIR", 961),
    ("MOp", 985), ("MOs", 993), ("RSP", 254),
    ("CA1", 382), ("CA3", 463), ("DG", 726),
]

# Keep the graph readable: at most this many targets per source, and drop
# anything below this mean normalized projection volume. Both are recorded
# in the provenance so the filtering is never invisible.
TOP_TARGETS_PER_SOURCE = 8
MIN_MEAN_NPV = 0.002


def _cached_get(criteria: str, cache_name: str, refresh: bool,
                num_rows: int = PAGE, start_row: int = 0) -> dict:
    """Read-through file cache over one RMA query, mirroring the pattern in
    build/plate_atlas.py:api_get."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / cache_name
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    r = requests.get(
        BASE,
        params={"criteria": criteria, "num_rows": num_rows, "start_row": start_row},
        timeout=120,
    )
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success"):
        raise RuntimeError(f"Allen RMA error: {payload.get('msg')}")
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def _paged(criteria: str, stem: str, refresh: bool):
    """Yield every row of a query, caching one file per page."""
    start = 0
    while True:
        page = _cached_get(criteria, f"{stem}_{start:05d}.json", refresh, PAGE, start)
        rows = page["msg"]
        if not rows:
            return
        yield from rows
        start += len(rows)
        if start >= page["total_rows"]:
            return


def fetch_structure_paths(refresh: bool = False) -> dict[int, str]:
    """structure id -> structure_id_path, for descendant tests."""
    paths = {}
    for s in _paged(f"model::Structure,rma::criteria,[graph_id$eq{GRAPH_ID}]",
                    "structures", refresh):
        paths[s["id"]] = s.get("structure_id_path") or ""
    return paths


def fetch_experiments(refresh: bool = False) -> list[tuple[int, int]]:
    """(experiment id, primary injection structure id) for product 5."""
    out = []
    for row in _paged(
        f"model::SectionDataSet,rma::criteria,products[id$eq{PRODUCT_ID}],"
        "rma::include,specimen(injections)", "experiments", refresh
    ):
        injections = (row.get("specimen") or {}).get("injections") or []
        primary = next((i.get("primary_injection_structure_id") for i in injections
                        if i.get("primary_injection_structure_id")), None)
        if primary:
            out.append((row["id"], primary))
    return out


def fetch_unionizes(exp_ids: list[int], structure_ids: list[int],
                    refresh: bool = False) -> list[dict]:
    """Projection unionize rows for these experiments and target structures."""
    rows = []
    targets = ",".join(str(s) for s in structure_ids)
    batch = 40
    for i in range(0, len(exp_ids), batch):
        chunk = exp_ids[i:i + batch]
        criteria = (
            "model::ProjectionStructureUnionize,rma::criteria,"
            f"[section_data_set_id$in{','.join(str(e) for e in chunk)}],"
            f"[is_injection$eqfalse],[hemisphere_id$eq{HEMISPHERE_BOTH}],"
            f"[structure_id$in{targets}]"
        )
        # one page is plenty: len(chunk) * len(structure_ids) rows at most
        page = _cached_get(criteria, f"unionize_{i:05d}.json", refresh,
                           num_rows=batch * len(structure_ids) + 50)
        rows.extend(page["msg"])
    return rows


def build_graph(refresh: bool = False) -> dict:
    from mouse_atlas.build.connectivity_data import (
        BUILD_VERSION, SCHEMA_VERSION, normalize_weights,
    )

    paths = fetch_structure_paths(refresh)
    experiments = fetch_experiments(refresh)
    region_ids = dict(REGIONS)

    def owning_region(structure_id: int):
        for acr, rid in REGIONS:
            if structure_id == rid or f"/{rid}/" in paths.get(structure_id, ""):
                return acr
        return None

    source_of = {}
    for exp_id, primary in experiments:
        acr = owning_region(primary)
        if acr:
            source_of[exp_id] = acr
    print(f"  {len(source_of)} experiments map onto {len(REGIONS)} regions")

    rows = fetch_unionizes(sorted(source_of), [rid for _a, rid in REGIONS], refresh)
    print(f"  {len(rows)} unionize rows")

    id_to_acr = {rid: acr for acr, rid in REGIONS}
    # (source, target) -> list of normalized projection volumes
    buckets: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        src = source_of.get(row["section_data_set_id"])
        tgt = id_to_acr.get(row["structure_id"])
        if not src or not tgt or src == tgt:
            continue
        npv = row.get("normalized_projection_volume")
        if npv is None or not math.isfinite(npv) or npv < 0:
            continue
        buckets.setdefault((src, tgt), []).append(npv)

    candidates = []
    for (src, tgt), vals in buckets.items():
        mean = sum(vals) / len(vals)
        if mean >= MIN_MEAN_NPV:
            candidates.append({"source": src, "target": tgt,
                               "raw_weight": mean, "n_experiments": len(vals)})

    # keep the strongest few per source so the 3D view stays readable
    kept = []
    for acr, _rid in REGIONS:
        outgoing = sorted((c for c in candidates if c["source"] == acr),
                          key=lambda c: -c["raw_weight"])[:TOP_TARGETS_PER_SOURCE]
        kept.extend(outgoing)
    kept.sort(key=lambda c: -c["raw_weight"])
    print(f"  {len(candidates)} candidate edges -> {len(kept)} kept")

    norms = normalize_weights([c["raw_weight"] for c in kept])
    edges = [
        {
            "source": c["source"], "target": c["target"],
            "raw_weight": c["raw_weight"], "normalized_weight": n,
            "units": "mean normalized projection volume",
            "n_experiments": c["n_experiments"],
            "evidence_class": "EXPERIMENTAL",
            "note_en": f"Mean over {c['n_experiments']} injection experiment(s).",
            "note_zh": f"{c['n_experiments']} 次注射實驗的平均值。",
        }
        for c, n in zip(kept, norms)
    ]

    nodes = [
        {"acronym": acr, "structure_id": rid, "name_en": None, "name_zh": None,
         "color": None, "pos_um": None, "evidence_class": "ATLAS-DERIVED"}
        for acr, rid in REGIONS
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "dataset": "Allen Mouse Brain Connectivity Atlas - region projection graph",
            "version": f"product-{PRODUCT_ID}-ccfv3",
            "source": BASE + f" (model::ProjectionStructureUnionize, products[id$eq{PRODUCT_ID}])",
            "download_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "atlas_space": "Allen Mouse CCFv3 (2017)",
            "age": "P56 adult",
            "normalization": "log1p(raw)/log1p(max_raw), clipped [0,1]; "
                             "raw = mean normalized projection volume, "
                             f"hemisphere=both, edges below {MIN_MEAN_NPV} dropped, "
                             f"top {TOP_TARGETS_PER_SOURCE} targets per source",
            "build_version": BUILD_VERSION,
            "license": "Allen Institute - free educational use with citation",
        },
        "nodes": nodes,
        "edges": edges,
        "propagation": None,  # filled in by connectivity_data.load_connectivity
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true", help="ignore the local cache")
    args = ap.parse_args()

    print("Fetching Allen Mouse Connectivity projection data ...")
    doc = build_graph(args.refresh)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT_PATH}  ({len(doc['nodes'])} nodes, {len(doc['edges'])} edges)")
    top = sorted(doc["edges"], key=lambda e: -e["normalized_weight"])[:12]
    for e in top:
        print(f"    {e['source']:>8} -> {e['target']:<8} "
              f"raw={e['raw_weight']:.4f}  norm={e['normalized_weight']:.3f}  "
              f"n={e['n_experiments']}")


if __name__ == "__main__":
    main()
