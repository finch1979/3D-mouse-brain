"""Tests for the mouse region-connectivity graph and its propagation model.

These cover the four properties the project's methodology requires of any
simulation layer: graph integrity, weights that stay in range without
discarding raw values, activity that stays finite and bounded, and strict
determinism (same input => same output).

The last test is a different kind of guard: it asserts the generated
JavaScript cannot collide with the string anchors site/viewer_upgrade.py
patches the viewer with. That collision would only show up as a silently
broken deployed page, so it is checked here rather than left to review.

Run:
    py -3.13 -m pytest tests/test_connectivity.py -q
"""

import math

import pytest

from mouse_atlas.build.connectivity_data import (
    EVIDENCE_CLASSES,
    NODE_SPECS,
    SYSTEM_NAMES,
    attach_positions,
    load_connectivity,
    normalize_weights,
    propagate,
    step_activity,
    strongest_path,
    validate,
)

NODE_ORDER = ["LGd", "VISp", "SCs", "LP", "RSP", "MOs"]

# Golden trace, seed LGd, derived from the implementation and checked by
# hand for step 0-2. Node order as above. Freezing it means any change to
# decay/gain/weights/clip has to be deliberate.
GOLDEN_LGD = [
    [1.0000, 0.0000, 0.0, 0.0, 0.0000, 0.0000],
    [0.3500, 0.6500, 0.0, 0.0, 0.0000, 0.0000],
    [0.1225, 0.4550, 0.0, 0.0, 0.0708, 0.0268],
    [0.0429, 0.2389, 0.0, 0.0, 0.0744, 0.0281],
    [0.0150, 0.1115, 0.0, 0.0, 0.0520, 0.0197],
    [0.0053, 0.0488, 0.0, 0.0, 0.0304, 0.0115],
    [0.0018, 0.0205, 0.0, 0.0, 0.0159, 0.0060],
    [0.0006, 0.0084, 0.0, 0.0, 0.0078, 0.0030],
    [0.0002, 0.0033, 0.0, 0.0, 0.0036, 0.0014],
]

FAKE_POSITIONS = {k: [float(i), 1.0, 2.0] for i, k in enumerate(NODE_ORDER)}


@pytest.fixture
def doc():
    return attach_positions(load_connectivity("mock"), dict(FAKE_POSITIONS))


# --- normalization ---------------------------------------------------------

def test_normalize_maps_max_to_exactly_one():
    assert normalize_weights([0.152, 0.061, 0.024, 0.009])[0] == 1.0


def test_normalize_stays_in_unit_range_and_is_monotone():
    out = normalize_weights([0.009, 0.152, 0.061, 0.024])
    assert all(0.0 <= w <= 1.0 for w in out)
    raws = [0.009, 0.152, 0.061, 0.024]
    ranked_by_raw = [w for _, w in sorted(zip(raws, out))]
    assert ranked_by_raw == sorted(ranked_by_raw)


def test_normalize_survives_empty_and_all_zero():
    assert normalize_weights([]) == []
    assert normalize_weights([0.0, 0.0]) == [0.0, 0.0]


def test_normalize_matches_log1p_formula():
    raws = [0.152, 0.061]
    expected = math.log1p(0.061) / math.log1p(0.152)
    assert normalize_weights(raws)[1] == pytest.approx(expected)


# --- graph integrity -------------------------------------------------------

def test_every_edge_keeps_its_raw_weight(doc):
    for e in doc["edges"]:
        assert e["raw_weight"] is not None
        assert e["raw_weight"] > 0
        assert e["normalized_weight"] is not None


def test_node_order_and_edges_reference_known_nodes(doc):
    keys = [n["acronym"] for n in doc["nodes"]]
    assert keys == NODE_ORDER
    for e in doc["edges"]:
        assert e["source"] in keys and e["target"] in keys


def test_every_element_carries_a_known_evidence_class(doc):
    for n in doc["nodes"]:
        assert n["evidence_class"] in EVIDENCE_CLASSES
    for e in doc["edges"]:
        assert e["evidence_class"] in EVIDENCE_CLASSES
    assert doc["propagation"]["evidence_class"] == "COMPUTATIONAL"


def test_sc_does_not_project_directly_to_visp(doc):
    """The collicular road reaches cortex via LP. Asserting the absence
    keeps a future edit from quietly adding the shortcut."""
    pairs = {(e["source"], e["target"]) for e in doc["edges"]}
    assert ("SCs", "VISp") not in pairs
    assert ("SCs", "LP") in pairs


# --- propagation -----------------------------------------------------------

def test_propagation_matches_golden_trace(doc):
    frames = propagate(doc, "LGd")
    assert len(frames) == doc["propagation"]["steps"] + 1
    for i, (got, want) in enumerate(zip(frames, GOLDEN_LGD)):
        assert got == pytest.approx(want, abs=5e-5), f"frame {i} drifted"


def test_activity_is_always_finite_and_bounded(doc):
    for seed in [n["acronym"] for n in doc["nodes"]]:
        for frame in propagate(doc, seed):
            for v in frame:
                assert math.isfinite(v)
                assert 0.0 <= v <= 1.0


def test_propagation_is_deterministic(doc):
    assert propagate(doc, "LGd") == propagate(doc, "LGd")


def test_step_activity_matches_propagate_frames(doc):
    """propagate() is exactly the impulse-response specialization of
    step_activity(): stepping the same recurrence by hand must reproduce it."""
    frames = propagate(doc, "LGd")
    keys = [n["acronym"] for n in doc["nodes"]]
    activity = [0.0] * len(keys)
    activity[keys.index("LGd")] = 1.0
    got = [list(activity)]
    for _ in range(doc["propagation"]["steps"]):
        activity = step_activity(doc, activity, steps=1)
        got.append(list(activity))
    assert len(got) == len(frames)
    for frame, stepped in zip(frames, got):
        assert list(frame) == pytest.approx(stepped, abs=1e-12)


def test_model_module_imports_no_randomness():
    import mouse_atlas.build.connectivity_data as mod
    src = open(mod.__file__, encoding="utf-8").read()
    assert "import random" not in src
    assert "random." not in src


def test_seed_starts_as_a_clean_impulse(doc):
    first = propagate(doc, "SCs")[0]
    assert first[NODE_ORDER.index("SCs")] == 1.0
    assert sum(first) == 1.0


def test_unknown_seed_is_rejected(doc):
    with pytest.raises(KeyError):
        propagate(doc, "NOPE")


# --- strongest path (the tracing reference the viewer mirrors) --------------

def test_strongest_path_follows_the_trisynaptic_loop():
    doc = load_connectivity("allen")
    # DG -> CA1 direct exists (0.316) but DG -> CA3 -> CA1 is stronger
    assert strongest_path(doc, "DG", "CA1") == ["DG", "CA3", "CA1"]


def test_strongest_path_routes_sc_to_cortex_via_lp():
    doc = load_connectivity("allen")
    # SCs -> LP -> VISp beats the weak direct SCs -> VISp edge
    assert strongest_path(doc, "SCs", "VISp") == ["SCs", "LP", "VISp"]


def test_strongest_path_same_node_is_trivial():
    doc = load_connectivity("allen")
    assert strongest_path(doc, "DG", "DG") == ["DG"]


def test_strongest_path_returns_none_when_disconnected():
    doc = load_connectivity("mock")
    assert strongest_path(doc, "MOs", "LGd") is None


def test_strongest_path_is_deterministic():
    doc = load_connectivity("allen")
    assert strongest_path(doc, "DG", "CA1") == strongest_path(doc, "DG", "CA1")


def test_strongest_path_rejects_unknown_node():
    doc = load_connectivity("allen")
    with pytest.raises(KeyError):
        strongest_path(doc, "DG", "NOPE")


# --- validation ------------------------------------------------------------

def test_validate_accepts_the_real_document(doc):
    validate(doc)


def test_validate_rejects_unknown_evidence_class(doc):
    doc["edges"][0]["evidence_class"] = "VIBES"
    with pytest.raises(ValueError, match="evidence class"):
        validate(doc)


def test_validate_rejects_missing_provenance_field(doc):
    del doc["provenance"]["atlas_space"]
    with pytest.raises(ValueError, match="provenance"):
        validate(doc)


def test_validate_rejects_dropped_raw_weight(doc):
    doc["edges"][0]["raw_weight"] = None
    with pytest.raises(ValueError, match="raw_weight"):
        validate(doc)


def test_validate_rejects_out_of_range_weight(doc):
    doc["edges"][0]["normalized_weight"] = 1.4
    with pytest.raises(ValueError, match="outside"):
        validate(doc)


def test_validate_rejects_node_without_position():
    bad = load_connectivity("mock")
    with pytest.raises(ValueError, match="pos_um"):
        validate(bad)


def test_unknown_source_is_rejected():
    with pytest.raises(ValueError, match="mock.*allen"):
        load_connectivity("something-else")


def test_allen_source_loads_the_cached_real_graph():
    """Requires the cache from `python -m mouse_atlas.fetch.connectivity`.
    If this fails with FileNotFoundError, fetch the cache first -- it is
    gitignored (mouse/data/ is not committed)."""
    doc = load_connectivity("allen")
    assert len(doc["nodes"]) == 17
    assert all(e["evidence_class"] == "EXPERIMENTAL" for e in doc["edges"])
    assert all(e["n_experiments"] > 0 for e in doc["edges"])
    pairs = {(e["source"], e["target"]) for e in doc["edges"]}
    # the trisynaptic loop should fall out of real data unprompted
    assert ("DG", "CA3") in pairs
    assert ("CA3", "CA1") in pairs


def test_allen_document_merges_system_and_display_metadata():
    """load_connectivity("allen") must fill every node's system + bilingual
    names from NODE_SPECS, because the viewer groups the picker by system."""
    doc = load_connectivity("allen")
    by_acr = {n["acronym"]: n for n in doc["nodes"]}
    for acr, sid, name_en, name_zh, color, system in NODE_SPECS:
        node = by_acr[acr]
        assert node["structure_id"] == sid
        assert node["name_en"] == name_en
        assert node["name_zh"] == name_zh
        assert node["color"] == color
        assert node["system"] == system
        assert system in SYSTEM_NAMES


def test_node_specs_cover_exactly_the_six_systems():
    assert {spec[5] for spec in NODE_SPECS} == set(SYSTEM_NAMES)


def test_build_region_specs_match_node_specs():
    """The page bake script must draw exactly the graph's node set, or a
    region in the data would have no mesh (and vice versa)."""
    from mouse_atlas.build.mouse_connectivity import REGION_SPECS
    got = [(s["acr"], s["sid"], s["name_en"], s["name_zh"], s["color"], s["system"])
           for s in REGION_SPECS]
    assert got == list(NODE_SPECS)


# --- the generated JS must not collide with the site layer ------------------

# site/viewer_upgrade.py:prepare_viewer patches the viewer's last <script>
# by literal str.replace against these. If custom_js emitted one, the patch
# would land in the wrong place and the deployed page would break silently.
FORBIDDEN_ANCHORS = [
    "  function animate() {",
    "    renderer.render(scene, camera);",
    "  const camera = new THREE.PerspectiveCamera(",
    "  const renderer = new THREE.WebGLRenderer(",
    '  window.addEventListener("resize", resize);',
    "  const HOVER_NODES = [];",
    "    camera.updateProjectionMatrix();",
    "window.innerWidth / window.innerHeight",
]

# these make the site layer bail out entirely
FORBIDDEN_IDS = ["neuroNav", "naViewport", "naRail"]


def test_custom_js_avoids_site_layer_anchors():
    from mouse_atlas.build.mouse_connectivity import CUSTOM_JS
    for anchor in FORBIDDEN_ANCHORS:
        assert anchor not in CUSTOM_JS, f"custom_js would collide with {anchor!r}"


def test_custom_js_avoids_site_layer_sentinels():
    from mouse_atlas.build.mouse_connectivity import CUSTOM_JS
    for name in FORBIDDEN_IDS:
        assert name not in CUSTOM_JS, f"custom_js contains the sentinel {name!r}"


def test_custom_js_has_no_randomness_in_the_model_path():
    from mouse_atlas.build.mouse_connectivity import CUSTOM_JS
    assert "Math.random" not in CUSTOM_JS


def test_custom_js_leaves_no_template_token_behind():
    """render_viewer_html hard-fails on leftover __TOKEN__ patterns, and the
    only one custom_js carries is substituted before rendering."""
    from mouse_atlas.build.mouse_connectivity import CUSTOM_JS
    filled = CUSTOM_JS.replace("__CONN_JSON__", "{}")
    assert "__" not in filled


def test_custom_js_has_no_global_edge_cap():
    """Phase 2 viewer ranks edges per selected region; the old global
    `.slice(0, 50)` would let a weak region show nothing."""
    from mouse_atlas.build.mouse_connectivity import CUSTOM_JS
    assert ".slice(0, 50)" not in CUSTOM_JS
    assert "OUT_BY" in CUSTOM_JS and "IN_BY" in CUSTOM_JS


def test_custom_js_groups_the_picker_by_system():
    from mouse_atlas.build.mouse_connectivity import CUSTOM_JS
    assert "conn-sys" in CUSTOM_JS
    assert "SYSTEMS" in CUSTOM_JS


def test_custom_js_has_edge_inspection_and_tracing():
    """Phase 3 surface: an edge detail card, a path tracer that mirrors the
    Python reference, a focus toggle, and the scene-layer evidence override."""
    from mouse_atlas.build.mouse_connectivity import CUSTOM_JS
    for needle in ("connDetail", "connTraceTo", "connTraceBtn", "connFocus",
                   "strongestPath", "NEURO_CONNECTIONS_LABEL", "conn-row--link"):
        assert needle in CUSTOM_JS, f"missing Phase 3 hook {needle!r}"


def test_scene_js_evidence_label_override_is_backward_compatible():
    """scene.js is shared by every viewer; it must only use the override when
    it is actually defined, and keep the original schematic text otherwise."""
    from pathlib import Path
    scene = (Path(__file__).resolve().parents[1] / "site" / "templates" / "scene.js").read_text(
        encoding="utf-8")
    assert "window.NEURO_CONNECTIONS_LABEL" in scene
    assert "ATLAS PROPORTIONS · SCHEMATIC CONNECTIONS" in scene


def test_custom_js_uses_a_fixed_activity_display_scale():
    """Raw frames stay untouched; the glow uses ONE fixed scale
    (activity ** 0.45, floor 0.005, cap 0.6) for the whole run, never a
    per-step max normalization (the same value must always look the same)."""
    from mouse_atlas.build.mouse_connectivity import CUSTOM_JS
    assert "displayValue" in CUSTOM_JS
    assert "Math.pow" in CUSTOM_JS
    assert "ACTIVITY_GAMMA = 0.45" in CUSTOM_JS
    assert "ACTIVITY_FLOOR = 0.005" in CUSTOM_JS
    assert "ACTIVITY_CAP = 1.1" in CUSTOM_JS
    # 500-800 ms per step (sequential animation requirement)
    assert "STEP_MS = 650" in CUSTOM_JS
    # no per-step normalization, and no write-back into the simulation frames
    assert "maxOf" not in CUSTOM_JS
    assert "now[i] =" not in CUSTOM_JS
    assert "frames[step] =" not in CUSTOM_JS


def test_custom_js_has_the_running_wheel_layer():
    from mouse_atlas.build.mouse_connectivity import CUSTOM_JS
    for needle in ("runStart", "runStop", "runReset", "runTrace", "runWheelSpokes",
                   "decodeMotor", "stepWheelPhysics", "thetaFrequency", "RUN_STATE_ZH",
                   "updateSimulation", "Developer motor test",
                   "mouseStage", "mouseStart", "mouseStop", "updateMouseStage",
                   "mouseWheelSpokes"):
        assert needle in CUSTOM_JS, f"missing running-wheel hook {needle!r}"


def test_motor_decoder_never_reads_display_scaling():
    """Model separation: the engineered decoder must consume RAW activity only,
    never the gamma display value (which is visualization-only)."""
    from mouse_atlas.build.mouse_connectivity import CUSTOM_JS
    body = CUSTOM_JS[CUSTOM_JS.index("function decodeMotor"):
                     CUSTOM_JS.index("function brainStep")]
    assert "displayValue" not in body
    assert "SIM.activity" in body or "rawOf" in body


def test_page_copy_describes_real_data_not_a_schematic_graph():
    """Guard the Phase 2 wording: the built page must not call its edges a
    schematic teaching graph, and must name the real source."""
    import mouse_atlas.build.mouse_connectivity as mod
    src = open(mod.__file__, encoding="utf-8").read()
    assert "schematic teaching" not in src
    assert "Allen Mouse Brain Connectivity Atlas" in src
