# Agent notes

Conventions for anyone (human or agent) adding to this repo.

- **`mouse/` and `human/` are independent sub-projects.** Separate packages
  (`mouse_atlas`, `human_atlas`), separate `data/`/`outputs/`, separate
  `pip install -e`. Don't add cross-imports between them; if logic is
  genuinely needed in both, duplicate the small helper (as already done for
  `common/paths.py`) rather than reintroducing a shared package. Only
  `web/lib/` and `external/` are shared, at the repo root.
- **Fetch vs. build** (mouse only — human's single script does both):
  `mouse_atlas/fetch/` only talks to the Allen Brain Map API and writes raw
  data (structure lookups, meshes, plate images). `mouse_atlas/build/` and
  `human_atlas/build/` turn raw/fetched data into a finished, self-contained
  HTML viewer. Don't blur fetch and build — a `build/` script shouldn't make
  ad-hoc network calls beyond its declared atlas download, and a `fetch/`
  script shouldn't emit HTML.
- **Viewers are self-contained.** Every `.html` output inlines its own copy
  of three.js/OrbitControls and its mesh/image data as base64. `web/lib/`
  already has its `<script>...</script>` tags baked into the file itself
  (extracted verbatim from an inline block) — embed it bare as `{three_js}`/
  `{orbit_js}` in a template, never wrapped in another `<script>` tag, or
  the nested script silently breaks (`Unexpected token '<'`, `THREE is not
  defined`). Don't add `<script src=...>` references between output files —
  `web/lib/` is a reference copy only, nothing loads it at runtime.
- **Adding a new mouse age**: add `mouse/configs/<age>.yaml` with its atlas
  identity (Allen `atlas_id` and/or BrainGlobe atlas name, default
  acronyms), load it via `mouse_atlas.common.config.load_config`, and add a
  `mouse/outputs/<age>/` output folder. Don't hardcode the literal in the
  script itself.
- **Paths**: always resolve species-root-relative locations via
  `mouse_atlas.common.paths` / `human_atlas.common.paths` (`OUTPUTS_DIR`,
  `DATA_CACHE_DIR`, `WEB_LIB_DIR`, ...) rather than deriving them from
  `__file__` in each script.
- **`external/brainglobe-atlasapi/` is vendored and gitignored.** Don't edit
  it in place; if a fix is needed, patch it upstream.
- **Human structures are mostly schematic, not real segmentations** — check
  `human/src/human_atlas/build/human_auditory.py`'s module docstring before
  assuming a new structure has a downloadable atlas source; several obvious
  candidates (cochlear nucleus, medial geniculate via FreeSurfer, inferior
  colliculus/superior olivary complex via the Bianciardi lab atlas) were
  already investigated and ruled out as impractical in this environment.

## Multi-agent coordination (Two Brains protocol)

This repo is worked on by more than one AI agent (Claude Code, Codex,
others), sometimes from **more than one independent local clone at once**
— not just git worktrees of one clone, but genuinely separate `.git`
checkouts. On 2026-09-12 this caused a real incident: a "nine evidence-
backed adult systems" feature was built and committed on `main` in a
second clone that nobody else's session knew about, and its commits sat
unpushed for an unknown time while a different agent, in a different
clone, branched off the older `main` for unrelated work. Production ended
up running content neither clone's checkout matched. Full account in
`AI_STATE.md`'s handoff log.

Rules, binding on every agent:

1. **Read `AI_STATE.md` before any work.** It lists every known clone of
   this repo and the current task/owner/locked files.
2. Before creating a new branch or worktree, confirm your clone is not
   behind `origin/main` (`git fetch && git log origin/main..main` and
   `..origin/main`), and check `AI_STATE.md`'s clone list for anything you
   don't recognize.
3. Write a plan entry to `AI_STATE.md` (or the active `.agents/current_task.md`)
   before editing, and a result entry after — see `AI_STATE.md` for the
   exact template.
4. Don't let finished work sit unpushed in a local-only clone indefinitely
   — that is precisely the failure mode above. Push (with the human's
   go-ahead) once work is stable.
5. Full protocol, role split, and risk levels: see `CLAUDE.md`.
