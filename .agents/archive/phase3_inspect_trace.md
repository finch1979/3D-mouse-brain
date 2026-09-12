# Current task: Connectivity Explorer — Phase 3 (inspect & trace real edges)

Status: **ready for worker** — brief written by orchestrator after Phase 2 review.
Phase 2 brief archived verbatim at `.agents/archive/phase2_connectivity_realdata.md`.

Worktree: `K:/my-code-project/mouse-brain-connectivity` on `feature/connectivity-explorer`.
Sibling repo `C:\Users\User\Documents\my-code-project\mouse brain` (branch `main`) must stay
untouched. Always run from this worktree with
`PYTHONPATH=K:\my-code-project\mouse-brain-connectivity\mouse\src`, or the editable install
resolves to the C: checkout and writes outputs there.

## Objective

Phase 2 shipped the real 17-region / 136-edge Allen graph, but the edges are only browsable
as two ranked lists. Phase 3 makes the *real data* inspectable and traceable, and removes the
last place the deployed page still calls the connectivity schematic:

1. Evidence-label fix in the **shared deployed scene layer** (see below).
2. **Edge inspection** — click a list row or a 3D connection tube to see source → target,
   `raw_weight`, `normalized_weight`, `n_experiments`, bilingual note, evidence class; the
   chosen edge highlights.
3. **Pathway tracing** — from the selected region, pick a target and compute the strongest
   weighted path (`Dijkstra on -log(weight)`); highlight the chain and run a deterministic
   pulse along the real edge curves. Must reproduce `DG→CA3→CA1` and `SCs→LP→VISp`.
4. **Focus/dim mode** — when on, dim region meshes that are not the selected region and its
   direct neighbours, so a 17-region scene reads.

## Already done (do not redo)

Phase 2 is complete: `load_connectivity("allen")`, 17 baked meshes, grouped collapsible
picker, per-region top-N edges, `EXPERIMENTAL` tagging, 32 passing tests, clean regression
gate. Re-run `py -3.13 -m pytest tests/test_connectivity.py -q` (expect ≥32).

## The evidence-label bug (item 1, verified)

`site/dist/mouse/connectivity/index.html` contains the literal string
`SCHEMATIC CONNECTIONS`, injected from `site/templates/scene.js:492`:

```js
stageNote.textContent = compressed ? text('目前為壓縮示意模式','COMPRESSED TEACHING VIEW')
  : text('原始網格比例 · 連線為示意','ATLAS PROPORTIONS · SCHEMATIC CONNECTIONS');
```

That is correct for the pathway pages (their tube connections *are* schematic) but false for
the connectivity page, whose edges are Allen tracer measurements. Fix it in `scene.js` in a
**backward-compatible** way: if `window.NEURO_CONNECTIONS_LABEL` is set, use it; otherwise keep
exactly the current text. `mouse_connectivity.py`'s custom layer sets that global (bilingual).
Because `scene.js` is shared by every viewer, the fallback path MUST be byte-for-byte
behaviour-identical; verify a non-connectivity page still shows the old text.

## What is NOT done — the worker task

### Item 2 — edge inspection
- Make each `#connOut` / `#connIn` row clickable (carry enough data to identify the edge).
- Add a bilingual detail card in `#connBlock`: `SRC → TGT`, raw weight + units,
  normalized weight, `n_experiments`, the edge's `note_en` / `note_zh`, and its evidence tag.
- Raycast the 3D connection tubes on the existing canvas pointer handler (edges first, then
  region meshes as today); clicking a tube selects that edge. Tubes are thin — this is
  best-effort; the list rows are the guaranteed path.
- Selecting an edge highlights it (colour/opacity) over the region activity styling.

### Item 3 — pathway tracing
- From the selected region, a target `<select>` + a **Trace** button; **Clear** resets.
- Compute the strongest path in JS, mirroring a new Python `strongest_path()` exactly
  (ties broken by graph order; no randomness).
- Highlight every edge on the path and animate a deterministic pulse along the concatenated
  real edge curves (`TubeGeometry` curves must be kept on each edge record).
- Under `prefers-reduced-motion`, do not animate: show the path statically.
- `DG→CA1` must route `DG→CA3→CA1`; `SCs→VISp` must route `SCs→LP→VISp`.

### Item 4 — focus/dim mode
- A toggle. When on, non-neighbour region meshes dim (opacity only — do NOT touch
  `emissive`/`emissiveIntensity`, the activity `paint()` owns those). Restore exactly when
  off or when the selection changes.
- Root/skull stay as context, never dimmed.
- While a trace is active, dim non-path edges; while an edge is selected, emphasise it.

## Files allowed to edit

- `mouse/src/mouse_atlas/build/mouse_connectivity.py` (main target)
- `mouse/src/mouse_atlas/build/connectivity_data.py` — add `strongest_path()` only; do not
  change the schema shape or existing functions.
- `site/templates/scene.js` — item 1 override ONLY; must be backward compatible.
- `mouse/outputs/P56/pathway_meshes/connectivity/` (regenerated artifact)
- `tests/test_connectivity.py` (add tests; keep all existing)
- `.agents/current_task.md`, `.agents/dp_result.md`, `.agents/archive/`, `.agents/screenshots/`

## Files forbidden to edit

- `mouse/src/mouse_atlas/render/viewer_template.html` / `viewer_template.py`
- `build/mouse_visual.py`, `mouse_whisker.py`, `mouse_olfactory.py`
- Existing artifacts under `mouse/outputs/P56/pathway_meshes/{visual,whisker,olfactory}/`
- `mouse/outputs/P56/mesh/manifest.json` — do not run `fetch/atlas_3d.py:main()`
- `mouse/src/mouse_atlas/fetch/connectivity.py`
- All of `human/`, `mouse/data/` (regenerable cache; do not hand-edit), `external/`
- Other `site/templates/*` (only `scene.js` per item 1)
- No deploy (`wrangler pages deploy`) — out of scope

## Safety requirements

- Keep the `custom_js`-only injection discipline: no literal from `FORBIDDEN_ANCHORS`
  (`tests/test_connectivity.py`) and no `FORBIDDEN_IDS` (`neuroNav` / `naViewport` / `naRail`).
- No randomness anywhere in the propagation/pulse path; `signal=None` stays.
- Keep both `raw_weight` and `normalized_weight`; show `raw_weight` in the detail card.
- Call `validate()` before writing HTML (already does — keep it).
- Preserve the mock path and the golden propagation trace.
- Do not regenerate `visual/`, `whisker/`, `olfactory/`, or `mesh/manifest.json`; after
  building, confirm with `git diff --stat`.

## Expected commands and tests

```powershell
$env:PYTHONPATH = "K:\my-code-project\mouse-brain-connectivity\mouse\src"
Set-Location "K:\my-code-project\mouse-brain-connectivity"

# tests — must be >= 32, never fewer
py -3.13 -m pytest tests/test_connectivity.py -q

# rebuild page + site (scene.js is inlined at site build, so build_hub is required)
py -3.13 -m mouse_atlas.build.mouse_connectivity
py -3.13 site/build_hub.py
py -3.13 site/build_mouse.py

# regression gate — MUST be empty
git diff --stat -- mouse/outputs/P56/pathway_meshes/visual `
  mouse/outputs/P56/pathway_meshes/whisker `
  mouse/outputs/P56/pathway_meshes/olfactory mouse/outputs/P56/mesh/manifest.json
```

Browser check (Playwright, Python, served from `site/dist`), minimum:

- connectivity: grouped picker still 6 sections / 17 regions.
- clicking an `#connOut` row opens the detail card with raw + normalized + n + note.
- Trace `DG→CA1` reports the chain `DG→CA3→CA1`; Trace `SCs→VISp` reports `SCs→LP→VISp`.
- Focus toggle dims non-neighbours, restores when off.
- deployed stage note no longer says `SCHEMATIC` on the connectivity page.
- `/mouse/visual/` regression: still loads, zero console errors, and its stage note still
  shows the original `SCHEMATIC CONNECTIONS` text (fallback intact).

## Worker assignment

Single worker: the DP/OpenCode implementer. Result file: **`.agents/dp_result.md`**.

## Acceptance criteria

- `py -3.13 -m pytest tests/test_connectivity.py -q` passes, count ≥ 32.
- Items 1–4 implemented; `scene.js` fallback proven unchanged on a non-connectivity page.
- Regression gate on the three pathway artifacts + `manifest.json` is empty.
- Browser checklist passes with actual output/screenshots recorded in
  `.agents/dp_result.md` — not just "it works".
- Nothing pushed, nothing deployed, no commit.
