# DP / OpenCode result — Connectivity Explorer Phase 3 (inspect & trace)

Task: `.agents/current_task.md` (Phase 3 brief).
Worktree: `K:/my-code-project/mouse-brain-connectivity` on `feature/connectivity-explorer`.
Role: DP/OpenCode implementer + self-verification. Nothing committed, pushed, or deployed.

Scope executed: items 1–4 (full). Old Phase 2 brief preserved verbatim at
`.agents/archive/phase2_connectivity_realdata.md` before `current_task.md` was replaced.

---

## 1. Files changed

- `site/templates/scene.js` — **item 1** (shared, backward compatible). The stage note now
  uses `window.NEURO_CONNECTIONS_LABEL` (string or `(isChinese) => string`) when defined,
  otherwise the original `ATLAS PROPORTIONS · SCHEMATIC CONNECTIONS` text. 10 added lines,
  1 changed line; no other behaviour touched.
- `mouse/src/mouse_atlas/build/mouse_connectivity.py` — **items 2–4** (main work):
  - sets `window.NEURO_CONNECTIONS_LABEL` (bilingual) for the scene layer.
  - `buildEdge()` keeps its `CatmullRomCurve3` on `mesh.userData.curve` for tracing.
  - new state: `selectedEdge`, `focusMode`, `traceNodes`/`traceRecs`/`traceRun`, `detailMsg`,
    plus a single `pulse` sphere (no RNG).
  - new `strongestPath()` JS, a line-for-line mirror of the Python reference (ties by graph
    order).
  - `applyVisualState()`: focus dimming via **opacity only** (never emissive — `paint()`
    owns that), path/selected-edge highlight (`EDGE_HOT`), and a `data-conn-dimmed` QA count.
  - `renderEdges()` now keeps trace-path and selected edges visible even when outside the
    selected region's top-N; list rows are clickable (`conn-row--link`, `data-pair`), keyboard
    operable; new detail card (`#connDetail`), trace controls (`#connTraceTo`/`#connTraceBtn`/
    `#connTraceClear`), and focus toggle (`#connFocus`).
  - 3D picking now raycasts the visible tubes first, then region meshes.
  - `connTick()` advances the deterministic trace pulse along the real edge curves; under
    `prefers-reduced-motion` it shows the end-point statically instead.
  - `connApplyLang` re-renders the trace `<select>` and detail card on language switch.
- `mouse/src/mouse_atlas/build/connectivity_data.py` — added `strongest_path()` only (plus
  `import heapq`). No schema/function changes; the mock path and golden trace are untouched.
- `tests/test_connectivity.py` — 32 → 40 tests (added 6 `strongest_path` tests + 2 JS/scene
  guards; deleted/weakened none), then 41 after the Phase 3.5 display-only guard.
- `.agents/current_task.md` (Phase 3 brief), `.agents/archive/phase2_connectivity_realdata.md`,
  `.agents/dp_result.md`, `.agents/screenshots/phase3_trace.png`.

Regenerated artifact: `mouse/outputs/P56/pathway_meshes/connectivity/` (`mouse_connectivity_3d.html`
7.68 MB, `connectivity.json`, `manifest.json`, 18 `.obj`).

Not touched: `connectivity_data.py` schema, `fetch/connectivity.py`, `viewer_template.*`,
`build/mouse_{visual,whisker,olfactory}.py`, `human/`, `mouse/data/`, other `site/templates/*`.

## 2. Commands run (exact)

```powershell
$env:PYTHONPATH = "K:\my-code-project\mouse-brain-connectivity\mouse\src"
Set-Location "K:\my-code-project\mouse-brain-connectivity"
$env:MOUSE_CONN_STRICT_DRIVE = "1"

py -3.13 -m pytest tests/test_connectivity.py -q
py -3.13 -c "from mouse_atlas.build.mouse_connectivity import CUSTOM_JS; open(r'C:\Temp\opencode\custom_check.js','w',encoding='utf-8').write(CUSTOM_JS)"
node --check C:\Temp\opencode\custom_check.js

py -3.13 -m mouse_atlas.build.mouse_connectivity
py -3.13 site/build_hub.py
py -3.13 site/build_mouse.py

git diff --stat -- mouse/outputs/P56/pathway_meshes/visual `
  mouse/outputs/P56/pathway_meshes/whisker `
  mouse/outputs/P56/pathway_meshes/olfactory mouse/outputs/P56/mesh/manifest.json

# browser: Python Playwright 1.59, each script serves site/dist itself
py -3.13 C:\Temp\opencode\verify_phase3.py   # Phase 3 checks (14)
py -3.13 C:\Temp\opencode\verify_conn.py     # Phase 2 regression suite (21)
```

## 3. Results (actual output)

Tests:

```
$ py -3.13 -m pytest tests/test_connectivity.py -q
........................................                                 [100%]
40 passed in 0.79s
```

`node --check C:\Temp\opencode\custom_check.js` → exit 0 (the injected JS parses).

Build: `graph: 17 nodes, 136 edges (product-5-ccfv3)`, page written 7.68 MB; site rebuilt
(12 human viewers + mouse section).

Regression gate: **empty** (`git diff --stat` printed nothing, exit 0). The three pathway
artifact trees and `mesh/manifest.json` are byte-identical.

Browser — Phase 3, **14 / 14**:

```
PASS list rows are clickable  -- 8
PASS detail card shows raw/normalized/n  -- ...raw 0.523 · mean normalized projection volume normalized 0.161 n = 139 ...
PASS detail card shows evidence class
PASS detail card bilingual note present
PASS DG->CA1 traces via CA3   -- DG → CA3 → CA1
PASS SCs->VISp traces via LP  -- SCs → LP → VISp
PASS focus toggle engages     -- true
PASS focus dims non-neighbour regions -- 7
PASS focus toggle releases    -- 0
PASS connectivity stage note says EXPERIMENTAL -- ATLAS PROPORTIONS · EXPERIMENTAL CONNECTIONS
PASS connectivity stage note not SCHEMATIC
PASS connectivity zero console errors
PASS visual stage note keeps SCHEMATIC (fallback intact) -- ATLAS PROPORTIONS · SCHEMATIC CONNECTIONS
PASS visual zero console errors
```

Browser — Phase 2 suite re-run after the rewrite, **21 / 21** (grouped picker, per-region
top-N, slider, EXPERIMENTAL source panel, language toggle, deterministic Stimulate, 390px
mobile, visual page no `#connBlock`). Screenshots: `.agents/screenshots/phase3_trace.png`
(shows the `SCs → LP → VISp` detail card, trace controls, highlighted path, and the corrected
`EXPERIMENTAL CONNECTIONS` stage note).

## 4. Known failures / skipped validation

- **Reduced-motion pulse path is implemented but not browser-verified.** Playwright cannot
  easily force `prefers-reduced-motion: reduce`; the branch is code-reviewed only. The animated
  path was verified (screenshot shows the pulse).
- **3D tube click is best-effort.** Tubes are thin; the automated test selects edges via the
  list rows (guaranteed). Tube raycast is wired (edges first) but not asserted by a synthetic
  click.
- **Focus dimming is asserted by count** (`data-conn-dimmed` = 7 for SCs, 0 off), not by
  pixel inspection. Screenshot inspection confirms the visual effect.
- Did not fetch from Allen (cache present), did not deploy, did not commit.

## 5. Assumptions

- "Strongest" = max product of `normalized_weight`; ties break by graph order, matching the
  Python `strongest_path()` (verified: `DG→CA1` → `DG→CA3→CA1`; `SCs→VISp` → `SCs→LP→VISp`).
- Trace and edge selection are mutually exclusive; selecting a region or the other action
  clears the previous one.
- Focus dims region meshes at 16% opacity and never touches `emissive`/`emissiveIntensity`,
  so the activity paint and scene.js materials stay correct; root/skull are never dimmed.
- The `data-conn-dimmed` attribute is a harmless observability hook, not rendered.
- `scene.js` override is opt-in: absent the global, the text is character-for-character the
  old string.

## 6. Data safety

No raw inputs modified. `mouse/data/` cache untouched; `connectivity_data.py` schema and all
pre-existing functions unchanged (only `strongest_path()` added). No prohibited artifact
regenerated. `raw_weight` is preserved on every edge and is now surfaced in the detail card.

## 7. Unrelated changes noticed (left untouched)

- `.agents/codex_result.md` (Phase 2 worker result) is still present, untracked.
- `mouse/outputs/P56/mesh/218.obj` remains untracked (flagged in Phase 2; all 17 meshes present).
- `site/build_mouse.py` carries the Phase 2 connectivity metadata edit (not this round).
- A stale `http.server` was already bound to port 8790 from an earlier session; verification
  used 8793/8794.

---

## Phase 3.5 addendum — activity display layer (follow-up, corrected)

**Scope: visualization only. The propagation model was NOT changed.** `propagate()` in
`connectivity_data.py` and its JS mirror are untouched; `test_propagation_matches_golden_trace`
still pins the raw frames.

First attempt used a per-step max normalization (`pow(a / maxThisStep, 0.4)`). Review correctly
found this over-normalized: at step 8 (max raw ~0.03) the whole brain lit up as if maximally
active, and the same value looked different depending on the step. Replaced with a single fixed
scale.

### Final design (all in `mouse_connectivity.py` CUSTOM_JS)

- **One fixed display scale for the whole run**, relative to the seed amplitude of 1.0:
  `display = Math.pow(activity, 0.45)`, with a visibility floor `ACTIVITY_FLOOR = 0.005` and an
  emissive cap `ACTIVITY_CAP = 1.1`. No `maxOf` / per-step normalization and no per-step fade,
  so **the same activity always maps to the same brightness at any step**.
  (The cap was first set to 0.6 per the original "conservative 0.5–0.7" note, but a pixel
  measurement showed that only moved the brain ROI by ~3/255 at step 2 and ~2/255 at step 8 —
  visually "dark". Cause: three.js converts the mid-tone emissive colour to linear, so a cap of
  0.6 leaves almost no added light. Raised to 1.1 after the human chose that option; emissive
  colour is still the region's own hue, never white, so this brightens rather than washes out.)
- `paint()` now keeps the **anatomical base colour** (`mat.emissive.copy(b.em)`, no lerp to
  white) and uses activity only to raise `emissiveIntensity` from its base toward the cap.
- Every region with display > 0 glows each step (not just the seed); values below 0.005 produce
  no highlight at all.
- Step pacing `STEP_MS` 420 → **650 ms** (500–800 ms), sequential.
- Connection glow is driven by the **source** region's display value, giving a source→target
  directional cue (glow, not a moving particle, to stay clear of the trace pulse).
- Activity panel: bars use display intensity; the printed number is the **raw** activity
  (3 decimals below 0.01). Model note states, bilingually, the fixed `activity^0.45` scale and
  that the numbers are unmodified.
- QA hooks: `#connBlock[data-conn-active]` (regions glowing) and `[data-conn-peak]` (max display
  intensity this frame), used to prove the fixed scale.

Numeric example (cap 1.1): seed 1.0 → display 1.0 → intensity 1.10 (bright); step-8 peak 0.03
→ display 0.215 → intensity ≈ 0.30 (clearly weaker, still lit); 0.004 → 0 (no highlight).
Measured on-screen ROI brightness change vs idle: ~5.3/255 at step 2 and ~3.6/255 at step 8
(roughly double the cap-0.6 version). Late residual is intentionally fainter than early.

### Verification

```
$ py -3.13 -m pytest tests/test_connectivity.py -q
41 passed in 0.81s
```

`node --check` on the injected JS → exit 0.

Browser (`verify_phase3.py`) — **21 / 21**, including:

```
PASS stimulate advances step-by-step (not instant 8/8)  -- Step 3 / 8
PASS multiple regions glow mid-run (non-zero activity)  -- 15
PASS fixed scale: early peak is bright                  -- 0.814
PASS fixed scale: late peak is faint (<0.45)            -- 0.215
PASS fixed scale: brightness decays over the run        -- ('0.814', '0.215')
PASS final step still shows some residual activity      -- 14
PASS activity panel keeps numeric values  -- ...0.008 0.007 0.007 0.005 0.002 0.001 ...
```

`verify_conn.py` (Phase 2 suite) — **21 / 21**. Regression gate empty. Screenshot
`.agents/screenshots/phase35_activity.png`: step 8/8, anatomical colours intact, bars graded,
only faint residual glow.

### Not verified

- Edge "source→target" cue is a glow; a travelling particle per edge was not added.
- Reduced-motion shows the final step on the same fixed scale (static), code-reviewed only.

---

## Phase 4 — Virtual Mouse Running-Wheel Neural Simulation

Additional behavioral layer on top of the P56 connectivity / Phase 3 propagation.
The atlas, meshes, coordinates and the existing diffusion model are unchanged.

### Files changed

- `mouse/src/mouse_atlas/build/running_model.py` (new) — the four engineered models
  (motor decoder, wheel physics, synthetic theta/LFP, state label) plus the single
  `RUNNING_MODEL_CONFIG`. Pure functions, no atlas dependency.
- `mouse/src/mouse_atlas/build/connectivity_data.py` — added `step_activity()` only:
  the same recurrence as `propagate()` with an optional additive per-node input, used
  to inject the cue continuously. Schema/behaviour of everything else unchanged, and a
  test proves `step_activity` reproduces `propagate` step for step.
- `mouse/src/mouse_atlas/build/mouse_connectivity.py` — the injected `CUSTOM_JS` gains
  the running-wheel layer: `#runPanel` UI, `SIM` state, `updateSimulation(dt)`, and the
  single `connTick` loop now advances either the impulse animation or the behaviour
  simulation. `RUNNING_MODEL_CONFIG` is injected as `PAYLOAD.running`.
- `tests/test_running_model.py` (new, 22 tests) and `tests/test_connectivity.py`
  (+2 guards, plus the `step_activity` parity test). Total 65 passing.
- `.agents/current_task.md`, `.agents/archive/phase3_inspect_trace.md`, this file.

### How motorDrive is calculated (engineered)

`motorRaw = 0.5*rawActivity[MOp] + 0.5*rawActivity[MOs]` then
`motorDrive = clamp((motorRaw - 0.05) / (1 - 0.05), 0, 1)`. It reads **RAW** region
activity only — never the gamma display value — and is a BCI-like readout, not a claim
that these regions encode wheel speed. `MOp`/`MOs` are pinned by the engineered cue
(`run_cue_input = 1.0` added per brain step at those two nodes, clipped to 1), so drive
reaches ~1 while running and decays when the cue is removed.

### How wheel speed is calculated (engineered)

First-order integration per animation frame:
`accel = 20*motorDrive - 1.5*velocity`; `velocity = clamp(velocity + accel*dt, 0, 30)`;
`distance += velocity*dt`; `wheelAngle += (velocity/8)*dt`. Terminal speed at full drive
is ~13.3 cm/s (drive_gain/drag), below the 30 cm/s clamp. The Start button only enables
the cue; speed always builds through this physics and coasts down under drag.

### How CA1 theta is generated (engineered / synthetic)

`f = 6 + 3*v/(v+10)` (≈6 Hz rest, ~7.7 Hz at running speed), amplitude
`0.3 + 0.7*(v/30)`, sample `amp*sin(phase) + 0.02*noise(index)` with a reproducible
hash-based noise (no RNG state). Phase advances by `2π f dt`; the wheel trace shows the
LFP-like, motor-drive and speed series from an 8 s / 30 Hz history. The frequency
equation is a documented model mapping, NOT an experimentally fitted equation.

### Data-derived vs engineered (the honesty boundary)

- **Data-derived**: the 17 regions, their CCFv3 meshes, the 136 Allen tracer edges and
  the diffusion recurrence (`decay`/`gain`/`clip`) are the same measured/atlas material
  as Phase 2/3.
- **Engineered / model assumptions**: the run cue and motor decoder, wheel physics,
  theta frequency/amplitude mapping, noise, and the display transform. None is measured
  mouse physiology.

### Model separation

`rawActivity` (SIM.activity) → motor decoder → wheel → LFP. `displayActivity`
(`displayValue`/`paint`) is applied only when painting the 3D scene and is never read
by the decoder, wheel or LFP. Guard test `test_motor_decoder_never_reads_display_scaling`
scans the injected JS between `decodeMotor` and `brainStep` for any `displayValue` use.
`displayValue` is never fed back into the brain. Existing fixed-scale/no-per-frame
normalization is retained.

### Verification

```
$ py -3.13 -m pytest tests/test_connectivity.py tests/test_running_model.py -q
65 passed
```

### Right-side virtual mouse stage (follow-up)

A second, always-visible floating panel `#mouseStage` on the right (below the
orientation indicator; media-query sized on mobile) shows a mouse running on a wheel.
Its wheel rotation and leg gait are read OUT of the same `SIM` state (`angle`,
`distance`, `velocity`), so it is a downstream view of the neural controller, not an
independent animation. "跑動滾輪 / Run wheel" and "停止 / Stop" share `startRunning()`
/ `stopInput()` with the rail buttons, and both button sets stay `aria-pressed` in
sync. Gait phase = `distance * 1.5`; legs, body bob and tail freeze when
`velocity <= stop_speed_eps`. The user can therefore watch the network activate while
the mouse runs, and watch it coast down on Stop.

Browser (`verify_running.py`) — **25 / 25**: rail panel present; initial stationary;
Start does not jump speed to max; run cue raises network activity (16 regions active)
and motorDrive (1.00); wheel accelerates gradually (13.1 cm/s) and the spokes rotate;
Stop → COASTING and speed decays (12.9 → 1.0) while theta returns toward baseline
(7.7 → 6.3 Hz); Reset zeros everything; developer motor test spins the wheel (11.1 cm/s)
with zero brain activity; bilingual ("開始跑步"); **right-side stage: starts stopped,
Run wheel starts the mouse (12.9 cm/s, legs animating), rail Start stays in sync, Stop
coasts down, reset returns to stopped**; zero console errors. Screenshots:
`.agents/screenshots/running_start.png`, `running_panel.png`, `mouse_stage_running.png`.

Prior suites re-run unchanged: `verify_phase3.py` 21/21, `verify_conn.py` 21/21,
regression gate (visual/whisker/olfactory + manifest) empty. Nothing committed or
deployed.

### Not implemented (explicitly deferred per §18)

Muscular biomechanics, spinal motor neurons, spiking neurons, EMG, place cells, reward
learning, fatigue, AD/TDP-43 presets, reinforcement learning, realistic gait, multiple
sensory modalities.

### Notes / limitations

- The behavior panel lives inside the existing `#connBlock` rail (Layers pane) so it is
  mobile-safe; it is not a separate always-on overlay.
- The cue pins MOp/MOs near 1 while held; the network may keep some residual activity
  briefly after Stop because recurrent edges exist — this is the existing model, not a
  new behavior.

---

## Phase 4 handoff — missing mouse hub source (open, human investigating)

### What was delivered and is verified this session

- Phase 2 (real Allen graph), Phase 3 (edge inspect / path trace / focus), Phase 3.5
  (fixed activity display scale), and Phase 4 (Virtual Mouse Neural Controller: run cue,
  motor decoder, wheel physics, synthetic CA1 LFP, right-side mouse-on-wheel stage).
- Evidence: `pytest tests/` 65 passed; browser `verify_running.py` 26/26, `verify_phase3.py`
  21/21, `verify_conn.py` 21/21; regression gate (visual/whisker/olfactory + mesh manifest)
  empty. Code-router artifacts: `.agents/current_task.md`, `.agents/dp_result.md`,
  `.agents/archive/phase2_connectivity_realdata.md`, `.agents/archive/phase3_inspect_trace.md`.
- Screenshots: `.agents/screenshots/` (running_start, running_panel, mouse_stage_running,
  phase35_activity, phase3_trace, connectivity_*, anim_*, diag_*).

### The open issue (not caused by the Phase 2–4 work)

Symptom (human): the mouse hub's "依位置探索" map lost its many entries after the local
site was rebuilt; the human hub still shows 12.

Evidence gathered:

- `site/build_hub.py` lines 275–276 `shutil.rmtree` / `unlink` **delete every child of
  `site/dist`** before rebuilding. Running `site/build_hub.py` (done this session, as the
  documented build step) therefore wiped whatever was in `site/dist/mouse` and
  `site/build_mouse.py` rebuilt it from *this repo's* registry.
- This repo (HEAD = `main` = `origin/main` = 1708a13) registers only **11 mouse viewers**
  and only **5** have an anatomical `hotspot`, so the map shows 5:
  visual / whisker / olfactory / motor / hippocampus.
- Live production differs: `https://neuro-atlas.pages.dev/mouse/` lists **18** systems
  (adds 聽覺, 體感, 味覺, 平衡, 小腦, 邊緣, 睡眠, 疼痛, 自律), and
  `https://neuro-atlas.pages.dev/mouse/auditory/` returns a real page
  ("聽覺系統（小鼠）"). So the deployed site was built from a source NOT in this checkout.
- No local branch/worktree/remote contains them: `origin` is `finch1979/3D-mouse-brain`
  with only `main` @1708a13; the `design/neuro-atlas-upgrade` / `mouse-brain-redesign`
  worktree also has only the 5 hotspots; the C: sibling `main` likewise. `git fsck
  --unreachable` found one unrelated dangling commit (pain page).
- `git diff` shows the only site source edits this session are the connectivity entry in
  `site/build_mouse.py` and the label override in `site/templates/scene.js`; no viewer
  files were deleted.

### How to finish it once the source is found

1. Locate the checkout/folder that produced production (it must contain mouse
   auditory/somatosensory/gustatory/vestibular/cerebellum/limbic/sleep/pain/autonomic
   viewers and their registries; production `/mouse/<slug>/` pages are the reference).
2. Back up `site/dist` first, then bring those source files into this worktree.
3. Rebuild and verify (note: step 1 wipes `site/dist` again):
   ```powershell
   $env:PYTHONPATH = "K:\my-code-project\mouse-brain-connectivity\mouse\src"
   py -3.13 site/build_hub.py
   py -3.13 site/build_mouse.py
   ```
4. Confirm `/mouse/` lists the expected entries and `/mouse/auditory/` etc. load.
5. Do NOT commit or deploy until the human confirms.

### If the source cannot be found

The live production pages can be imported into `site/dist` as a temporary preview only;
they are not reproducible from this repo and any future `build_hub.py` run will remove
them. That decision belongs to the human.

