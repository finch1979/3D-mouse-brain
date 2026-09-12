"""
Region-level connectivity graph + propagation model for the MOUSE
Connectivity Explorer (Allen CCFv3 adult / P56).

SCOPE - this is a MESOSCALE, REGION-LEVEL graph. The Allen Mouse Brain
Connectivity Atlas measures axonal projection density between structures;
it is NOT a synapse-level connectome and carries no spike timing. Nothing
in this module should ever be described as a "connectome simulation".

Two sources, same schema:
  "mock"  a hand-specified SCHEMATIC teaching graph (4 edges) - useful for
          demos and as the propagation model's test fixture.
  "allen" REAL Allen Mouse Brain Connectivity Atlas projection data (see
          fetch/connectivity.py), cached under data/cache/P56/connectivity/.
          Run `python -m mouse_atlas.fetch.connectivity` once before using
          this source; load_connectivity raises a clear error if the cache
          is missing rather than silently falling back to mock data.

EVIDENCE CLASSES - every node, edge and model carries exactly one:
    EXPERIMENTAL    measured (real tracer data; Phase 2 edges)
    ATLAS-DERIVED   from the CCFv3 atlas itself (region identity, geometry)
    COMPUTATIONAL   produced by the propagation model
    SCHEMATIC       hand-drawn for teaching (Phase 1 edges)

ACCURACY RULES - do not "simplify" these back:
  - Keep BOTH raw_weight and normalized_weight. Raw values are never
    discarded; normalization is a display concern.
  - LP is Allen CCF structure 218 (graph_id=1). fetch.atlas_plate
    .lookup_structure("LP") returns 3793 because it does not filter by
    ontology graph, and 3793 has no precomputed mesh. Same class of trap
    as SCs (302, not the current 5744) documented in build/mouse_visual.py.
  - SC does NOT project to VISp directly; its cortical route runs via LP.
    That is precisely why LP is in this graph and not in mouse_visual.py.
  - The propagation model is a normalized linear network diffusion. It is
    NOT Hodgkin-Huxley, NOT leaky-integrate-and-fire, and says nothing
    about firing rates, latency or conduction velocity.
  - No randomness anywhere in this module. Same input => same output.

Data licensing: Allen CCFv3, Allen Institute - free educational use with
citation.
"""

from __future__ import annotations

import heapq
import json
import math
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0.0"
BUILD_VERSION = "mouse_connectivity/0.1.0"

EVIDENCE_CLASSES = frozenset(
    {"EXPERIMENTAL", "ATLAS-DERIVED", "COMPUTATIONAL", "SCHEMATIC"}
)

PROVENANCE_KEYS = (
    "dataset", "version", "source", "download_date", "generated_utc",
    "atlas_space", "age", "normalization", "build_version", "license",
)

# Allen CCFv3 (graph_id=1) structure ids. Meshes live in outputs/P56/mesh/.
# Colour is grouped by system so the 3D scene reads as systems, not a
# rainbow. None of these is an ancestor of another, so an injection maps to
# exactly one source region (see fetch/connectivity.py).
# acronym, id, name_en, name_zh, colour, system
NODE_SPECS = [
    ("VISp", 385, "Primary visual area", "初級視覺區", "5A8FE0", "visual"),
    ("LGd", 170, "Dorsal part of the lateral geniculate complex", "背側外側膝狀體", "7FB2F0", "visual"),
    ("SCs", 302, "Superior colliculus, sensory related", "上丘感覺相關層", "5AC0C0", "visual"),
    ("LP", 218, "Lateral posterior nucleus of the thalamus", "丘腦後外側核", "89A7E8", "visual"),
    ("SSp-bfd", 329, "Primary somatosensory area, barrel field", "初級體感區桶狀區", "B08FD9", "somatosensory"),
    ("VPM", 733, "Ventral posteromedial nucleus of the thalamus", "丘腦腹後內側核", "C9A6E6", "somatosensory"),
    ("PSV", 7, "Principal sensory nucleus of the trigeminal", "三叉神經主感覺核", "9B7BC4", "somatosensory"),
    ("SPVC", 429, "Spinal nucleus of the trigeminal, caudal part", "三叉神經脊髓核尾側部", "8468B0", "somatosensory"),
    ("MOB", 507, "Main olfactory bulb", "主嗅球", "8FBF7F", "olfactory"),
    ("AON", 159, "Anterior olfactory nucleus", "前嗅核", "A9D19A", "olfactory"),
    ("PIR", 961, "Piriform area", "梨狀皮質", "6FA05F", "olfactory"),
    ("MOp", 985, "Primary motor area", "初級運動區", "E8C46A", "motor"),
    ("MOs", 993, "Secondary motor area", "次級運動區", "D9A94E", "motor"),
    ("RSP", 254, "Retrosplenial area", "壓後皮質區", "1AA698", "association"),
    ("CA1", 382, "Field CA1", "海馬 CA1 區", "E88B6A", "hippocampal"),
    ("CA3", 463, "Field CA3", "海馬 CA3 區", "D96F4E", "hippocampal"),
    ("DG", 726, "Dentate gyrus", "齒狀回", "F0A98C", "hippocampal"),
]

SYSTEM_NAMES = {
    "visual": {"en": "Visual", "zh": "視覺"},
    "somatosensory": {"en": "Somatosensory (whisker)", "zh": "體感(鬍鬚)"},
    "olfactory": {"en": "Olfactory", "zh": "嗅覺"},
    "motor": {"en": "Motor", "zh": "運動"},
    "association": {"en": "Association", "zh": "聯合區"},
    "hippocampal": {"en": "Hippocampal", "zh": "海馬"},
}

# Phase 1 SCHEMATIC edges. Values are on an arbitrary projection-density
# scale chosen to reflect the QUALITATIVE ordering reported for these
# projections; they are teaching values, not measurements, and Phase 2
# replaces every one of them with real Allen tracer data.
MOCK_EDGE_SPECS = [
    ("LGd", "VISp", 0.152,
     "The cortical road: LGd relay cells drive primary visual cortex.",
     "皮質之路:背側外側膝狀體的中繼細胞驅動初級視覺皮質。"),
    ("SCs", "LP", 0.061,
     "The collicular road reaches cortex only indirectly, via LP.",
     "上丘之路只能間接抵達皮質,需經丘腦後外側核(LP)。"),
    ("VISp", "RSP", 0.024,
     "Visual cortex to retrosplenial cortex, a visuospatial route.",
     "視覺皮質到壓後皮質,屬視覺空間路徑。"),
    ("VISp", "MOs", 0.009,
     "A weaker long-range projection to secondary motor cortex.",
     "較弱的長距離投射,前往次級運動皮質。"),
]

PROPAGATION = {
    "decay": 0.35,
    "gain": 0.65,
    "steps": 8,
    "clip": [0.0, 1.0],
    "seed_mode": "impulse",
    "model": "next = decay*current + gain*(W^T @ current), clipped to [0,1]",
    "evidence_class": "COMPUTATIONAL",
}


def normalize_weights(raws):
    """log1p(raw) / log1p(max_raw), clipped to [0, 1].

    Projection strengths are heavily right-skewed, so a linear scale hides
    every weak edge. Returns all zeros for an empty or all-zero input
    rather than dividing by zero.
    """
    positive = [r for r in raws if r > 0]
    if not positive:
        return [0.0] * len(raws)
    denom = math.log1p(max(positive))
    if denom <= 0:
        return [0.0] * len(raws)
    return [min(1.0, max(0.0, math.log1p(r) / denom)) if r > 0 else 0.0 for r in raws]


def _node_meta_by_acronym() -> dict:
    return {acr: (sid, name_en, name_zh, color, system)
            for acr, sid, name_en, name_zh, color, system in NODE_SPECS}


# fixed order: the mock demo only needs the six regions its edges touch,
# and this exact order is what tests/test_connectivity.py's golden
# propagation trace is indexed against.
MOCK_NODE_ORDER = ["LGd", "VISp", "SCs", "LP", "RSP", "MOs"]


def _mock_document() -> dict:
    meta = _node_meta_by_acronym()
    nodes = [
        {
            "acronym": acr, "structure_id": meta[acr][0], "name_en": meta[acr][1],
            "name_zh": meta[acr][2], "color": meta[acr][3], "system": meta[acr][4],
            "pos_um": None, "evidence_class": "ATLAS-DERIVED",
        }
        for acr in MOCK_NODE_ORDER
    ]

    raws = [spec[2] for spec in MOCK_EDGE_SPECS]
    norms = normalize_weights(raws)
    edges = [
        {
            "source": src, "target": dst, "raw_weight": raw, "normalized_weight": norm,
            "units": "projection density (a.u.)", "n_experiments": 0,
            "evidence_class": "SCHEMATIC", "note_en": note_en, "note_zh": note_zh,
        }
        for (src, dst, raw, note_en, note_zh), norm in zip(MOCK_EDGE_SPECS, norms)
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "dataset": "Mouse Brain Connectivity Explorer - schematic teaching graph",
            "version": "mock-0.1.0",
            "source": "Hand-specified teaching graph - NOT an Allen download",
            "download_date": None,
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "atlas_space": "Allen Mouse CCFv3 (2017)",
            "age": "P56 adult",
            "normalization": "log1p(raw)/log1p(max_raw), clipped [0,1]",
            "build_version": BUILD_VERSION,
            "license": "Allen Institute CCFv3 - educational use with citation",
        },
        "nodes": nodes,
        "edges": edges,
        "propagation": dict(PROPAGATION),
    }


def _allen_document() -> dict:
    from mouse_atlas.fetch.connectivity import OUT_PATH

    if not OUT_PATH.exists():
        raise FileNotFoundError(
            f"no cached Allen connectivity data at {OUT_PATH}\n"
            "fetch it first:  py -3.13 -m mouse_atlas.fetch.connectivity"
        )
    doc = json.loads(OUT_PATH.read_text(encoding="utf-8"))

    meta = _node_meta_by_acronym()
    for node in doc["nodes"]:
        sid, name_en, name_zh, color, system = meta[node["acronym"]]
        node.update(structure_id=sid, name_en=name_en, name_zh=name_zh,
                   color=color, system=system)

    doc["propagation"] = dict(PROPAGATION)
    return doc


def load_connectivity(source: str = "mock") -> dict:
    """Build the connectivity document. `pos_um` is None until the build
    script calls attach_positions() with mesh-derived centroids.

    source="mock"  hand-specified 6-node teaching graph, always available.
    source="allen" real Allen projection data; requires the cache written
                   by `python -m mouse_atlas.fetch.connectivity`.
    """
    if source == "mock":
        return _mock_document()
    if source == "allen":
        return _allen_document()
    raise ValueError(f"unknown connectivity source {source!r}; use 'mock' or 'allen'")


def attach_positions(doc: dict, positions: dict) -> dict:
    """Fill each node's pos_um from mesh centroids (centred RAS micrometres)."""
    for node in doc["nodes"]:
        pos = positions.get(node["acronym"])
        if pos is None:
            raise KeyError(f"no centroid supplied for node {node['acronym']!r}")
        node["pos_um"] = [float(v) for v in pos]
    return doc


def propagate(doc: dict, seed: str) -> list[list[float]]:
    """Region-level linear diffusion. Mirrors the JS in the viewer exactly.

    Returns steps+1 frames, frame 0 being the impulse at `seed`. The clip
    is load-bearing, not decorative: decay + gain*sum(incoming weights) can
    exceed 1 for a node with several strong inputs.
    """
    keys = [n["acronym"] for n in doc["nodes"]]
    if seed not in keys:
        raise KeyError(f"seed {seed!r} is not a node in this graph")
    idx = {k: i for i, k in enumerate(keys)}
    p = doc["propagation"]
    decay, gain = p["decay"], p["gain"]
    lo, hi = p["clip"]

    cur = [0.0] * len(keys)
    cur[idx[seed]] = 1.0
    frames = [list(cur)]
    for _ in range(p["steps"]):
        nxt = [decay * v for v in cur]
        for e in doc["edges"]:
            nxt[idx[e["target"]]] += gain * e["normalized_weight"] * cur[idx[e["source"]]]
        nxt = [min(hi, max(lo, v)) for v in nxt]
        frames.append(nxt)
        cur = nxt
    return frames


def strongest_path(doc: dict, source: str, target: str) -> list[str] | None:
    """Strongest weighted path source -> target; None if disconnected.

    "Strongest" = the path maximizing the PRODUCT of normalized edge
    weights, computed as shortest path with cost -log(weight). This is a
    display aid: it surfaces the most prominent multi-hop route in the
    measured projection graph (e.g. DG -> CA3 -> CA1, SCs -> LP -> VISp),
    not a claim about signal routing. Ties break by graph order, so the
    result is deterministic. The viewer's JS mirrors this exactly.
    """
    keys = [n["acronym"] for n in doc["nodes"]]
    if source not in keys or target not in keys:
        raise KeyError(f"{source!r} or {target!r} is not a node in this graph")
    order = {k: i for i, k in enumerate(keys)}

    adjacency: dict[str, list[tuple[str, float]]] = {k: [] for k in keys}
    for e in doc["edges"]:
        w = e["normalized_weight"]
        if w > 0:
            adjacency[e["source"]].append((e["target"], w))

    dist = {k: math.inf for k in keys}
    prev: dict[str, str | None] = {k: None for k in keys}
    dist[source] = 0.0
    queue = [(0.0, order[source], source)]
    while queue:
        d, _oi, u = heapq.heappop(queue)
        if d > dist[u]:
            continue
        if u == target:
            break
        for v, w in adjacency[u]:
            nd = d - math.log(w)
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(queue, (nd, order[v], v))

    if math.isinf(dist[target]):
        return None
    path = []
    cur: str | None = target
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path


def step_activity(doc: dict, activity, input_activity=None,
                  steps: int = 1) -> list[float]:
    """Advance the network diffusion by `steps` and return a new activity list.

    Same recurrence as propagate() (decay / gain / clip from the document),
    but with an optional per-node additive `input_activity` applied before the
    clip, so an engineered drive (e.g. a run cue at MOp/MOs) can be injected
    into the existing model instead of simulating an impulse. `propagate()`
    remains the deterministic impulse-response helper used by the page's
    Stimulate button; this is the continuous-stepping entry point the running
    simulation uses. Neither the input activity nor the document is mutated.
    """
    p = doc["propagation"]
    decay, gain = p["decay"], p["gain"]
    lo, hi = p["clip"]
    idx = {n["acronym"]: i for i, n in enumerate(doc["nodes"])}
    cur = [float(v) for v in activity]
    for _ in range(steps):
        nxt = [decay * v for v in cur]
        for e in doc["edges"]:
            nxt[idx[e["target"]]] += gain * e["normalized_weight"] * cur[idx[e["source"]]]
        if input_activity:
            for acr, amount in input_activity.items():
                if acr in idx:
                    nxt[idx[acr]] += amount
        nxt = [min(hi, max(lo, v)) for v in nxt]
        cur = nxt
    return cur


def validate(doc: dict) -> None:
    """Raise ValueError on anything that would publish a misleading page."""
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")

    prov = doc.get("provenance") or {}
    missing = [k for k in PROVENANCE_KEYS if k not in prov]
    if missing:
        raise ValueError(f"provenance is missing required keys: {missing}")

    keys = set()
    for node in doc["nodes"]:
        if node["evidence_class"] not in EVIDENCE_CLASSES:
            raise ValueError(
                f"node {node['acronym']!r} has unknown evidence class "
                f"{node['evidence_class']!r}"
            )
        pos = node["pos_um"]
        if pos is None or len(pos) != 3 or not all(math.isfinite(v) for v in pos):
            raise ValueError(f"node {node['acronym']!r} has no finite pos_um")
        keys.add(node["acronym"])

    for e in doc["edges"]:
        if e["source"] not in keys or e["target"] not in keys:
            raise ValueError(f"edge {e['source']}->{e['target']} references an unknown node")
        if e["evidence_class"] not in EVIDENCE_CLASSES:
            raise ValueError(
                f"edge {e['source']}->{e['target']} has unknown evidence class "
                f"{e['evidence_class']!r}"
            )
        if e.get("raw_weight") is None:
            raise ValueError(f"edge {e['source']}->{e['target']} lost its raw_weight")
        w = e["normalized_weight"]
        if not math.isfinite(w) or not 0.0 <= w <= 1.0:
            raise ValueError(
                f"edge {e['source']}->{e['target']} normalized_weight {w!r} outside [0,1]"
            )

    if doc["propagation"]["evidence_class"] != "COMPUTATIONAL":
        raise ValueError("the propagation model must be labelled COMPUTATIONAL")
