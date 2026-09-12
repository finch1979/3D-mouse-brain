# Current task: Virtual Mouse Running-Wheel Neural Simulation (Phase 4)

Status: **complete, handed off** — see `.agents/dp_result.md` (Phase 4 section).
Phase 3 brief archived verbatim at `.agents/archive/phase3_inspect_trace.md`.

## Open issue (NOT caused by this work) — mouse hub lost its extra systems

The human will investigate. Details and evidence in `.agents/dp_result.md`
("Phase 4 handoff — missing mouse hub source"). Summary:

- `site/build_hub.py` **wipes `site/dist`** (`shutil.rmtree`) on every run. Rebuilding
  therefore replaced the local `site/dist/mouse` with this repo's registry.
- This repo (feature branch = `main` = `origin/main` @1708a13) has only **11 mouse
  viewers / 5 map hotspots**. The live production `/mouse/` shows **18 systems**
  (聽覺/體感/味覺/平衡/小腦/邊緣/睡眠/疼痛/自律 + the local ones) and
  `/mouse/auditory/` really exists.
- Those extra mouse viewers exist in **no** local branch/worktree/remote and no
  dangling commit; the source that produced production is outside this checkout.
- Do NOT run `site/build_hub.py` again until the missing source is found or
  `site/dist` is backed up — it will wipe the directory again.

Worktree: `K:/my-code-project/mouse-brain-connectivity` on `feature/connectivity-explorer`.
Run from this worktree with `PYTHONPATH=...\mouse\src`; do not touch the C: sibling checkout.
Do not deploy until local browser validation succeeds.

## Objective

Add a **behavioral simulation layer** on top of the existing P56 connectivity /
Phase 3 propagation: a run cue enters the network, an engineered motor decoder reads
MOp/MOs, a virtual wheel is driven by first-order physics, and a synthetic CA1
theta-like LFP is visualised. This must **not** rewrite the atlas architecture, meshes,
coordinates, or the existing propagation model.

Terminology (mandatory): "Virtual Mouse Neural Controller", "Region-level network
simulation", "Synthetic CA1 LFP-like signal". Never "complete mouse brain simulation",
"real motor physiology", or "real EEG".

## Required reads (done by orchestrator)

README.md, PROJECT_MAP.md, AGENTS.md, site/README.md, site/build_mouse.py,
site/viewer_upgrade.py, site/templates/scene.js, mouse/src/mouse_atlas/{build,render}/*.

Integration points reported:
- Phase 3 raw activity is produced by `propagate()` in the `CUSTOM_JS` of
  `build/mouse_connectivity.py`; the impulse animation keeps it transiently in
  `run = {frames, t0}`, advanced/painted by the single `connTick()` rAF loop.
- The diffusion step is `next = decay*cur + gain*(Wᵀ cur)` clipped [0,1]
  (`P.decay=0.35`, `gain=0.65`), mirrored in `connectivity_data.propagate`.
- Activity reaches three.js through `paint(key, a)` (region `emissiveIntensity`);
  `displayValue(v)=v^0.45` is display-only.
- Integration point: a persistent raw-activity vector + continuous `brainStep()`
  reusing the same recurrence/edges/constants, driven by the one `connTick` loop,
  with the behaviour UI inside the existing `#connBlock`.

## Four separated systems (do not mix)

A. neural activity (raw) — reuses the existing recurrence + an engineered run cue
B. motor decoder — `motorDrive = clamp((0.5*MOp + 0.5*MOs - 0.05)/0.95, 0, 1)`
C. wheel physics — `accel = 20*motorDrive - 1.5*v`, `v` clamped `[0,30]`,
   `angle += (v/8)*dt`, `distance += v*dt`
D. synthetic CA1 LFP — `f = 6 + 3*v/(v+10)`, `amp = 0.3+0.7*(v/30)`,
   `lfp = amp*sin(phase) + 0.02*noise(index)`, reproducible hash noise

All parameters live in one config object: `mouse_atlas/build/running_model.py`'s
`RUNNING_MODEL_CONFIG`, injected into the page as `PAYLOAD.running`.

## Hard rules

- **Raw activity only** enters the decoder, wheel physics and LFP. `displayValue`
  and `paint` are visualization-only and must never feed back. This is enforced by a
  test (`test_motor_decoder_never_reads_display_scaling`).
- Keep the corrected Phase 3 fixed display scale and anatomical colours; do not
  per-frame normalize.
- One master animation loop; no competing timers.
- The Start button enables the cue; it must not set wheel velocity directly.
- Reset restores all state to initial.

## Files allowed to edit

- `mouse/src/mouse_atlas/build/mouse_connectivity.py` (UI + injected JS)
- `mouse/src/mouse_atlas/build/connectivity_data.py` (add `step_activity()` only)
- `mouse/src/mouse_atlas/build/running_model.py` (new)
- `tests/test_running_model.py` (new), `tests/test_connectivity.py` (add guards)
- `.agents/*` (brief, archive, result, screenshots)

## Files forbidden to edit

`render/viewer_template.*`, `build/mouse_{visual,whisker,olfactory}.py`, existing
`pathway_meshes/{visual,whisker,olfactory}/`, `mesh/manifest.json`,
`fetch/connectivity.py`, `human/`, `mouse/data/`, `external/`, other `site/templates/*`.
No deploy.

## Acceptance

- Python tests: motor decoder, wheel physics, theta generator, integration (§17 of the
  request). Existing suites still pass; regression gate empty.
- Browser: Start → MOp/MOs raw activity rises → motorDrive rises → wheel accelerates
  gradually; Stop → decay/coast; Reset → initial. Developer motor test spins the wheel
  with zero brain activity. Bilingual labels + scientific disclaimer.
- Result file: `.agents/dp_result.md` (Phase 4 section), including the required
  explanation of files, motorDrive, wheel speed, theta generation, and which parts are
  data-derived vs engineered.
