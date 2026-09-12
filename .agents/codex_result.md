# Codex result — Mouse Brain Connectivity Explorer, Phase 2 (real Allen data)

Task: `.agents/current_task.md`
Worktree: `K:/my-code-project/mouse-brain-connectivity` on `feature/connectivity-explorer`
Role this round: implementation + tests + verification (per CLAUDE.md default split).
Nothing committed, nothing merged, nothing deployed.

---

## 1. Files changed

Written / modified in this round:

- `mouse/src/mouse_atlas/build/mouse_connectivity.py` — the main change:
  - `REGION_SPECS` is now derived from `connectivity_data.NODE_SPECS` (17 regions, 6
    systems) instead of a hand-written 6-region tuple list; mesh bake and legend follow it.
  - `main()` builds from `load_connectivity("allen")` (was `"mock"`), bakes all 17 meshes.
  - `CUSTOM_JS` now injects `{graph, systems}` under the single `__CONN_JSON__` token:
    `CONN = PAYLOAD.graph`, `SYSTEMS = PAYLOAD.systems`. `connectivity.json` stays the pure
    schema (verified: no `systems` key in the artifact).
  - Grouped, collapsible picker (one section per system, default open, click header to
    toggle) replacing the flat 17-button list.
  - Per-selected-region top-N edges in both directions (new `OUT_BY`/`IN_BY` rankings);
    removed the global `.slice(0, 50)`. Slider now means "edges per direction for this
    region", default 10, max `MAX_PER_DIR` (14). All 136 edge meshes are built resident and
    toggled by visibility.
  - Data-source panel tag is derived from the data (`CONN.edges[0].evidence_class`), so it
    reads `EXPERIMENTAL`, not the hardcoded `SCHEMATIC`.
  - Row tooltips now carry the per-edge injection count `n=<n_experiments>`.
  - Rewrote `subtitle`, `walk_0`, `walk_1`, `legend_note` to describe real Allen data and to
    state the mesoscale/uneven-n caveats. `walk_2` (propagation disclaimer) untouched.
- `site/build_mouse.py` — only the `connectivity` entry: `source`, `route`, `fact` updated
  (now "Allen CCFv3 + Allen Mouse Brain Connectivity Atlas", 17 regions / 136 edges).
- `tests/test_connectivity.py` — 26 → 32 tests (added 6, none weakened or deleted).
- `.agents/codex_result.md` — this file.
- `.agents/screenshots/connectivity_desktop.png`, `connectivity_mobile.png`,
  `connectivity_picker.png` — verification evidence.

Regenerated artifacts (untracked; `mouse/outputs/` is gitignored content):

- `mouse/outputs/P56/pathway_meshes/connectivity/` — `mouse_connectivity_3d.html` (7.66 MB),
  `connectivity.json`, `manifest.json`, 18 `*.obj` (root + 17 regions).

Deliberately **not** touched:

- `mouse/src/mouse_atlas/build/connectivity_data.py` — the allen/mock merge already produced
  everything the viewer needed, so no fix was required (per the brief, only small fixes were
  allowed). Schema shape unchanged.
- `mouse/src/mouse_atlas/fetch/connectivity.py` — cache present, confirmed working.
- `render/viewer_template.html` / `viewer_template.py`, `build/mouse_visual.py`,
  `mouse_whisker.py`, `mouse_olfactory.py`, `human/`, `external/`.

---

## 2. Commands run (exact)

```powershell
$env:PYTHONPATH = "K:\my-code-project\mouse-brain-connectivity\mouse\src"
Set-Location "K:\my-code-project\mouse-brain-connectivity"
$env:MOUSE_CONN_STRICT_DRIVE = "1"

# data cache already present (never re-fetched; did NOT run fetch/connectivity.py)
Test-Path mouse\data\cache\P56\connectivity\allen_projection_p56.json   # True

# tests
py -3.13 -m pytest tests/test_connectivity.py -q

# build connectivity page (allen)
py -3.13 -m mouse_atlas.build.mouse_connectivity

# full site
py -3.13 site/build_hub.py
py -3.13 site/build_mouse.py

# regression gate
git diff --stat -- mouse/outputs/P56/pathway_meshes/visual `
  mouse/outputs/P56/pathway_meshes/whisker `
  mouse/outputs/P56/pathway_meshes/olfactory `
  mouse/outputs/P56/mesh/manifest.json

# browser verification (script starts its own http.server on 127.0.0.1:8793
# serving site/dist, then drives Chromium via Python Playwright 1.59.0)
py -3.13 C:\Temp\opencode\verify_conn.py
```

---

## 3. Test / check results (actual output)

```
$ py -3.13 -m pytest tests/test_connectivity.py -q
................................                                         [100%]
32 passed in 0.76s
```

Build:

```
  graph: 17 nodes, 136 edges (product-5-ccfv3)
  baking root (98638 faces) ... [17 regions] ...
Wrote .../mouse_connectivity_3d.html (7.66 MB)
```

Artifact sanity (`connectivity.json`):

```
Allen Mouse Brain Connectivity Atlas - region projection graph
product-5-ccfv3
nodes 17 edges 136
has systems key: False
edge classes {'EXPERIMENTAL'}
node classes {'ATLAS-DERIVED'}
```

Regression gate: **empty** (`git diff --stat` printed nothing, exit 0). The three existing
pathway artifact trees and `mesh/manifest.json` are byte-identical.

Browser verification — **21 / 21 checks passed** (full output archived at
`.agents/screenshots/`; representative lines):

```
PASS 6 system sections
PASS 17 region buttons
PASS system headers EN        -- ['Visual','Somatosensory (whisker)','Olfactory','Motor','Association','Hippocampal']
PASS collapse first section   -- ('false', 'none')
PASS MOs outgoing rows > 0    -- 8
PASS MOs incoming rows > 0    -- 10
PASS slider max matches busiest direction (14) -- 14
PASS slider max shows full incoming list -- 14
PASS source panel says EXPERIMENTAL
PASS source panel not SCHEMATIC
PASS system headers zh
PASS source panel still EXPERIMENTAL in zh
PASS toggle back to EN
PASS activity lists all 17 regions -- 17
PASS stimulate deterministic across runs
PASS no horizontal overflow at 390px
PASS mobile still has 17 regions -- 17
PASS rail has no horizontal overflow at 390px
PASS visual page has no #connBlock
PASS visual page zero console errors
PASS connectivity page zero console errors
SUMMARY 21 / 21 checks passed
```

Manual walkthrough (desktop 1440×900, mobile 390×844):

- Page open, Layers rail shows **six system headers**; each header collapses/expands its
  region buttons.
- Selecting the hub `MOs` shows 8 outgoing and up to 14 incoming rows (sorted strongest
  first), not an unsorted wall. Slider max is 14 (incoming is the busiest direction for
  MOs/DG/RSP).
- `Stimulate` runs all 8 steps and lists all 17 regions; a second run gives identical
  displayed values.
- Data-source panel reads `Connectivity: Allen ... (downloaded 2026-09-12) EXPERIMENTAL`.
- Language toggle twice restores all labels (headers, source panel, model note).
- `/mouse/visual/` loads with zero console errors and no `#connBlock`.

---

## 4. Known failures / skipped validation / caveats

- **Not tested at exactly 50 simultaneous edges.** The chosen per-region design caps at
  `MAX_PER_DIR = 14` per direction, so at most the union of top-14 in + top-14 out is
  visible (≤28), below the old global 50 ceiling. Headless Chromium showed no stutter, but
  headless is not a real GPU frame-rate benchmark; a human visual pass on real hardware is
  still worth doing.
- **Browser test opens the site-layer "Layers" rail pane.** In the published site,
  `viewer_upgrade.py` moves `#legendPanel` into a hidden `#naPane-layers`; the viewer's own
  artifact shows the legend on load, but the deployed page requires clicking the Layers
  button. This is expected site behaviour (same for all viewers), not a regression — the
  script clicks `#naButton-layers` to reach the picker.
- **One literal "schematic" remains in the shipped HTML**, and it is in the shared
  `viewer_template.html:477` comment (`pathway chains: schematic tube ...`). That file is
  forbidden to edit and is byte-shared with the human/whisker/olfactory pages. The two
  occurrences that came from my injected `CUSTOM_JS` comments were reworded out.
- **`.agents/current_task.md` was already modified** in the working tree before this round
  (a pre-existing change, not mine); left untouched.
- **`mouse/outputs/P56/mesh/218.obj` is untracked**, although the brief states it is
  git-tracked. All 17 region meshes are present on disk so this blocked nothing; flagging so
  the tree is not assumed clean.
- A leftover `http.server` was already bound to port 8790 from an earlier session, so the
  verification script used 8793 instead.

---

## 5. Assumptions / deviations from the brief

1. **Edge cap semantics changed per the human's explicit choice** ("each selected region
   takes its own top N", not global top-50). One slider N applies per direction for the
   selected region; default 10, max 14. This supersedes brief item 3/6.
2. **Grouped picker** uses six collapsible sections defaulting to open, ordered by first
   appearance in `NODE_SPECS` (visual → somatosensory → olfactory → motor → association →
   hippocampal). Supersedes the "minimum bar" in brief item 4.
3. **Scientific correction (not in the brief).** The live cache contains a real
   `SCs → VISp` edge (normalized 0.002, n=8), so the Phase-1 claim "SCs does NOT project
   directly to VISp" would have contradicted an edge drawn on the same page. `walk_1`, the
   module docstring, and `site/build_mouse.py`'s `fact` were reworded to state the measured
   ordering instead: `LGd → VISp` dominant, `SCs → LP → VISp` the main collicular route, and
   a much weaker direct `SCs → VISp`.
4. The mock path is intact and untouched; `load_connectivity("mock")` and the golden 6-node
   propagation trace still pass. Only the page build switched to `"allen"`.
5. All 17 regions remain `default_checked` in the legend (same policy as the old 6).

---

## 6. Confirmation

- Regression gate on `visual/`, `whisker/`, `olfactory/`, `mesh/manifest.json`: **empty**.
- `validate()` is still called in the build before writing HTML.
- No randomness introduced; `signal=None` preserved; template-injection discipline tests
  (forbidden anchors/ids/tokens) all still pass.
- Not committed, not pushed, not deployed.

---

## 7. Architecture / handoff note (multi-agent workflow)

The `.agents/current_task.md` brief was a strong handoff: the "what is already done / what is
NOT done" split, the explicit file allow/forbid lists, and the exact command list removed
almost all ambiguity. Two things it could not have known and that the next brief should carry
a check for:

- A **data-vs-narrative contradiction** (`SCs → VISp` exists) was only visible after loading
  the cache. A handoff that pins specific scientific claims should include a "re-verify these
  claims against the cache" step, or state them as checks rather than prose.
- A **stated repo fact was stale** (`218.obj` "git-tracked" — actually untracked). A one-line
  `git status` snapshot in the brief would prevent that.
