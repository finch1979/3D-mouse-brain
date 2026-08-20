# mouse brain

Fetch/build pipelines and self-contained 3D/2D structure viewers for mouse
(Allen CCFv3 P56 adult, DeMBA P15, Developing Mouse P14) and human brain
atlases. Every viewer is a single static HTML file with its mesh/image data
baked in as base64 — open it directly in a browser, no server needed.

## Layout

Mouse and human are two independent sub-projects (own package, own data,
own outputs) sharing only the vendored JS libraries and third-party atlas
package at the repo root. See [PROJECT_MAP.md](PROJECT_MAP.md) for the full
map.

- `mouse/` — the mouse pipeline: `src/mouse_atlas/` (`fetch`/`build`/`common`),
  `configs/*.yaml`, `data/cache/`, `outputs/{P14,P15,P56}/`.
- `human/` — the human pipeline: `src/human_atlas/` (`build`/`render`/`common`),
  `data/cache/`, `outputs/{whole_brain,limbic,auditory_system}/`.
- `web/lib/` — vendored three.js + OrbitControls source, kept for reference
  (every viewer currently inlines its own copy, so nothing loads this at
  runtime).
- `external/brainglobe-atlasapi/` — vendored clone of the open-source
  [BrainGlobe Atlas API](https://github.com/brainglobe/brainglobe-atlasapi),
  used by the mouse P15 DeMBA pipeline (gitignored, not modified).

## Install

```bash
pip install -e mouse/
pip install -e human/
```

`brainglobe-atlasapi` (a `mouse/` dependency) can come from PyPI or, to pin
to the exact vendored commit, `pip install -e external/brainglobe-atlasapi`.
BrainGlobe atlases themselves (e.g. the DeMBA P15 volume) download on first
use to `~/.brainglobe/`, separate from this repo's `data/cache/` dirs.

## Running a script

```bash
# mouse
python -m mouse_atlas.fetch.atlas_3d --acronyms MOp MOs RSP
python -m mouse_atlas.fetch.atlas_plate --acronyms MOp MOs RSP
python -m mouse_atlas.build.plate_atlas p56_coronal_289
python -m mouse_atlas.build.demba_p15
python -m mouse_atlas.build.demba_p15_3d

# human
python -m human_atlas.build.human_auditory
```

Outputs land under `mouse/outputs/...` or `human/outputs/...`; open the
resulting `.html` file directly in a browser.
