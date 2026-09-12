# Current task: Mouse Brain Connectivity Explorer — Phase 2 (real Allen data)

Status: **handoff to Codex** — orchestrator (Claude Code) stops implementing here.

Worktree: `K:/my-code-project/mouse-brain-connectivity` on `feature/connectivity-explorer`.
Sibling repo `C:\Users\User\Documents\my-code-project\mouse brain` (branch `main`) must
stay untouched — always run from this worktree, with
`PYTHONPATH=K:\my-code-project\mouse-brain-connectivity\mouse\src`, or Python's editable
install resolves to the C: checkout and writes outputs there instead.

## Objective

Phase 1 (done, merged into this branch) shipped a working Connectivity Explorer page with a
**hand-made 4-edge mock graph**. The user was not told this clearly enough up front and was
surprised the shown connections weren't real data. Phase 2 replaces the mock graph with
**real Allen Mouse Brain Connectivity Atlas projection data**, already fetched and proven to
work (see below). Codex's job is to wire that real data into the actual viewer page and
verify nothing broke.

## What is ALREADY DONE (do not redo)

1. **`mouse/src/mouse_atlas/fetch/connectivity.py`** — fetches real projection data from the
   Allen RMA API (product 5, `ProjectionStructureUnionize`, hemisphere=both). Confirmed
   working: `py -3.13 -m mouse_atlas.fetch.connectivity` produced
   `mouse/data/cache/P56/connectivity/allen_projection_p56.json` with **17 nodes, 136 edges**,
   real numbers. Textbook circuits fell out unprompted: `DG→CA3→CA1` (trisynaptic loop),
   `LGd→VISp`, `LP→VISp` (the collicular road the old visual page had to omit). This cache is
   gitignored (`mouse/data/` is not committed) — re-run the fetch if it's missing; it takes
   ~2 minutes and hits the live Allen API.
2. **`mouse/src/mouse_atlas/build/connectivity_data.py`** — `load_connectivity(source=...)`
   now supports both `"mock"` (6-node teaching graph, unchanged, still the propagation
   model's test fixture) and `"allen"` (reads the cache from step 1, merges in
   name_en/name_zh/color/system from `NODE_SPECS`, fills `propagation` from the same
   constant). `NODE_SPECS` now covers **17 regions across 6 systems** (visual,
   somatosensory/whisker, olfactory, motor, association, hippocampal) — see `SYSTEM_NAMES`.
3. **`tests/test_connectivity.py`** — 26 tests pass, including a new
   `test_allen_source_loads_the_cached_real_graph` that asserts the trisynaptic loop appears
   and every edge is `EXPERIMENTAL` with `n_experiments > 0`.
4. **Mesh `218.obj` (LP)** already downloaded and git-tracked.

Run `py -3.13 -m pytest tests/test_connectivity.py -q` from the worktree root
(with `PYTHONPATH` set) to confirm — should say `26 passed`.

## What is NOT done — this is Codex's actual task

**`mouse/src/mouse_atlas/build/mouse_connectivity.py` still builds the OLD 6-region mock
page.** It calls `load_connectivity("mock")`, and its `REGION_SPECS` / mesh-baking loop only
handles the original 6 regions (LGd, VISp, SCs, LP, RSP, MOs). It has NOT been updated to:

1. Switch to `load_connectivity("allen")`.
2. Bake all **17 region meshes** (see `NODE_SPECS` in `connectivity_data.py` for the full
   list with structure ids — all 17 `.obj` files already exist in `mouse/outputs/P56/mesh/`,
   confirmed present, nothing more to fetch).
3. Handle **136 edges** instead of 4 in the `custom_js` layer — `EDGES.slice(0, 50)` in the
   current `CUSTOM_JS` string already caps rendering at 50, sorted by weight, so this may
   work unchanged, but it has not been tested against a graph this size.
4. Add **system-based grouping** to the UI: `NODE_SPECS` and `SYSTEM_NAMES` now carry a
   `system` field per region (visual / somatosensory / olfactory / motor / association /
   hippocampal) specifically so the region picker and legend can group 17 regions instead of
   listing them flat. This did not exist in Phase 1's 6-region design. Minimum bar: don't
   dump 17 ungrouped buttons in a list — group by `system`, using `SYSTEM_NAMES[sys]["en"/"zh"]`
   as section headers.
5. Update the page's bilingual strings (`subtitle`, `walk_0`/`walk_1`/`walk_2`, `legend_note`)
   to stop saying the graph is a "schematic teaching graph" — it now needs to say the edges
   are **real Allen Connectivity Atlas data** (`EXPERIMENTAL`), while keeping the propagation
   disclaimer (`COMPUTATIONAL`, not a spike-timing model) exactly as-is — that part is still
   true and required by the project's methodology doc. The evidence-source panel
   (`connSrc` in `custom_js`) currently hardcodes a `SCHEMATIC` tag on the connectivity line
   — that must become `EXPERIMENTAL` when built from `source="allen"`.
6. Reconsider `EDGE_COLOR` / opacity scaling and the `Edges` slider max (currently hardcoded
   `min(50, EDGES.length)` with default 10 — check this still reads at n=136 candidate edges
   → 50 kept). Performance was validated at 4 edges only; re-verify at 50.
7. Rebuild the site (`py -3.13 site/build_hub.py && py -3.13 site/build_mouse.py`) and rerun
   the full browser check (see Verification below) against the real 17-node graph.

**Do not throw away the mock path.** Keep `load_connectivity("mock")` working and keep
`tests/test_connectivity.py`'s golden propagation trace (indexed against the 6-node mock
graph) passing — it's the fast, deterministic fixture for testing `propagate()`. The page
itself should switch to `"allen"`; the mock stays as a test-only code path.

## Files allowed to edit

- `mouse/src/mouse_atlas/build/mouse_connectivity.py` (main target)
- `mouse/src/mouse_atlas/build/connectivity_data.py` (only if the allen/mock merge needs
  small fixes — e.g. missing fields the viewer needs; do not change the schema shape)
- `mouse/outputs/P56/pathway_meshes/connectivity/` (regenerated artifact)
- `site/build_mouse.py` (only the `connectivity` entry's `fact`/`route` strings, if the
  17-region graph makes the old 6-region blurb inaccurate)
- `tests/test_connectivity.py` (add tests for the new build script output if useful; do not
  weaken or delete the existing 26)

## Files forbidden to edit

- `mouse/src/mouse_atlas/render/viewer_template.html` / `viewer_template.py` — shared with
  whisker/olfactory pages and byte-identical to the human copy. The whole point of the
  `custom_js` injection point is that this file never changes for this feature.
- `build/mouse_visual.py`, `mouse_whisker.py`, `mouse_olfactory.py`
- Existing artifacts under `mouse/outputs/P56/pathway_meshes/{visual,whisker,olfactory}/`
- `mouse/outputs/P56/mesh/manifest.json` — `fetch/atlas_3d.py` rewrites it wholesale; do not
  run its `main()`. All 17 meshes already exist; no fetch should be needed.
- `mouse/src/mouse_atlas/fetch/connectivity.py` — already built and tested; if it looks wrong,
  flag it in the result file rather than rewriting silently.
- All of `human/`, `mouse/data/` (gitignored cache, but don't hand-edit it — regenerate via
  the fetch script if it needs to change), `external/`
- No deploy (`wrangler pages deploy`) — out of scope for this task.

## Safety requirements

- Preserve the `custom_js`-only injection discipline: the generated JS must not contain any
  literal `site/viewer_upgrade.py:prepare_viewer` patches against (see the
  `FORBIDDEN_ANCHORS` / `FORBIDDEN_IDS` lists in `tests/test_connectivity.py` — there are
  passing tests for this; keep them passing).
- No randomness in the propagation path — `signal=None` must stay, so the template's
  `Math.random()` swarm code never runs on this page.
- Raw data discipline: `connectivity_data.py`'s documents keep both `raw_weight` and
  `normalized_weight` on every edge; do not drop `raw_weight` when adapting the build script.
- Every node/edge/model element must carry one of the four evidence classes
  (EXPERIMENTAL / ATLAS-DERIVED / COMPUTATIONAL / SCHEMATIC) — `validate()` in
  `connectivity_data.py` already enforces this; call it in the build script before writing
  HTML (it already is called — keep that call).
- Do not silently regenerate `mouse/outputs/P56/pathway_meshes/visual/`,
  `.../whisker/`, or `.../olfactory/` — confirm via `git diff --stat` after building that
  they are byte-identical to before.

## Expected commands and tests

```powershell
$env:PYTHONPATH = "K:\my-code-project\mouse-brain-connectivity\mouse\src"
Set-Location "K:\my-code-project\mouse-brain-connectivity"

# 0. confirm the real-data cache exists (re-fetch if missing, ~2 min, hits live Allen API)
Test-Path mouse\data\cache\P56\connectivity\allen_projection_p56.json
# if missing: py -3.13 -m mouse_atlas.fetch.connectivity

# 1. unit tests — must stay at "26 passed" or grow, never shrink
py -3.13 -m pytest tests/test_connectivity.py -q

# 2. build the connectivity page against real data
py -3.13 -m mouse_atlas.build.mouse_connectivity

# 3. full site build
py -3.13 site/build_hub.py
py -3.13 site/build_mouse.py

# 4. regression gate — MUST be empty
git diff --stat -- mouse/outputs/P56/pathway_meshes/visual mouse/outputs/P56/pathway_meshes/whisker mouse/outputs/P56/pathway_meshes/olfactory mouse/outputs/P56/mesh/manifest.json

# 5. serve and browser-check (Playwright is installed; chromium at
#    C:\Users\User\AppData\Local\ms-playwright\chromium-1217\chrome-win64\chrome.exe)
py -3.13 -m http.server 8790 --bind 127.0.0.1 --directory site/dist
```

Manual/Playwright checks against `http://127.0.0.1:8790/mouse/connectivity/`:
- All 17 regions selectable, grouped by system in the picker/legend.
- Selecting a hub region (e.g. `MOs`, which has 107 experiments) shows a sane number of
  outgoing/incoming rows, not an overwhelming unsorted wall.
- Edge slider works up to whatever cap is chosen (≤50 per the existing perf ceiling); no
  frame-rate collapse — this needs actual visual/perf inspection, not just "it loads".
  If it stutters, first thing to try is reducing `TOP_TARGETS_PER_SOURCE` in
  `fetch/connectivity.py` and picking a smaller node set, before touching rendering code.
- Stimulate still runs 8 steps, deterministic, activity list matches all 17 regions.
- Data-source panel says `EXPERIMENTAL` for connectivity, not `SCHEMATIC`.
- Language toggle (twice) still works on every new/changed label.
- Mobile width (390px): no horizontal overflow, panel still usable with 17 regions — this is
  the part most likely to need actual redesign (grouped picker, possibly collapsed sections).
- `/mouse/visual/` regression: loads with zero console errors, no `#connBlock` present.

## Worker assignment

Single worker: **Codex**, implementation + tests + verification per its default role
(CLAUDE.md: "Codex: implementation, bug fixing, tests, refactoring, file operations, command
execution"). Claude Code reviews after, per CLAUDE.md's default split — do not have Codex
also write the review.

Required result file: **`.agents/codex_result.md`**, containing:
- files changed (exact list)
- commands run (exact list, copy from Expected commands above plus anything else run)
- tests/checks passed or failed, with actual output pasted, not paraphrased
- known failures or skipped validation (e.g. "did not test at exactly 50 edges because…")
- assumptions made (e.g. how regions were grouped in the UI, any deviation from this brief)
- confirmation the regression gate (existing 3 pathway artifacts) is empty
- any unrelated changes noticed in the working tree, left untouched

## Acceptance criteria

- `py -3.13 -m pytest tests/test_connectivity.py -q` passes, count ≥ 26.
- `mouse_connectivity.py` builds a page from `load_connectivity("allen")` — 17 regions, real
  weighted edges, correct evidence-class labelling throughout.
- Regression gate on the three existing pathway artifacts is empty.
- Browser checklist above passes, with actual screenshots or a written walkthrough in
  `.agents/codex_result.md` — not just "it works".
- Nothing pushed, nothing deployed. This branch (`feature/connectivity-explorer`) is not
  merged to `main` and no commit is created unless the human asks for one separately.

## Reference: Phase 1 handoff notes carried forward

1. `fetch/atlas_plate.lookup_structure("LP")` returns id **3793** from a different Allen
   ontology graph, which 404s (no precomputed mesh). Correct id is **218** (graph_id=1). Same
   trap could bite other acronym lookups — verify `graph_id == 1` for anything new.
2. The shared template's `applyLang()` reads `STRINGS.signal_name` / `signal_desc`
   unconditionally, even when `signal=None` — omitting those keys throws and the page never
   finishes loading. `mouse_connectivity.py` already supplies them; keep them if the strings
   dict is restructured.
3. 3D connection curves need `depthTest: false` on their material — the centroids they join
   sit inside opaque region meshes, so a depth-tested tube is invisible from the default
   camera angle. Already applied in `CUSTOM_JS`; preserve it.
