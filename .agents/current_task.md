# Current task: none — all prior work merged, one audit not yet actioned

Status: idle. Read this file's history via `git log -p -- .agents/current_task.md`
for the full trail; this entry summarizes where things landed.

## What's done and merged onto `main`

1. **Connectivity Explorer** (Phases 1-4: real Allen data, propagation,
   edge tracing, the Virtual Mouse Neural Controller running-wheel
   behavior) — complete, tested, merged, pushed, and deployed to
   production. See `.agents/dp_result.md` (Phase 3) and
   `.agents/archive/` for the phase briefs, `.agents/codex_result.md`
   and `.agents/screenshots/` for the Phase 4 implementation record.
2. **Nine evidence-backed adult systems** (auditory/autonomic/
   cerebellum/gustatory/limbic/pain/sleep/somatosensory/vestibular) —
   already on `main`, already deployed.
3. **The "mouse hub lost its extra systems" incident** a Phase 4 worker
   flagged here — two independent local clones of this repo had
   diverged, and one clone's commits (the nine systems) had never been
   pushed to GitHub, so a `site/build_hub.py` rebuild in the other
   clone looked like it destroyed content it had in fact never had.
   **Resolved**: both clones' work is merged and pushed; see
   `AI_STATE.md`'s 2026-09-12 handoff log entry for the full incident
   and the "Known clones of this repo" list, which now exists
   specifically so this can't recur silently.
4. **Two Brains coordination protocol** (`AI_STATE.md`, `CLAUDE.md`,
   the addition to `AGENTS.md`) — installed for exactly this reason.
5. **Open-source prep** — `LICENSE` (GPL-3.0), `.gitattributes` fix for
   a second Windows line-ending corruption site, `mouse_connectivity.py`'s
   ~1,400-line embedded JS extracted to its own file.

## Not yet actioned — next worth picking up

**DeepSeek's read-only audit of the nine system pages**
(`.agents/dp_result_nine_systems_audit.md`) found 8 findings against the
currently-deployed pages, none fixed yet. Most notable:

- **F3 (worth fixing first)**: the shared explanation text injected by
  `site/templates/scene.js` says "approximate head shell starts hidden"
  on every mouse page — but the mouse pages have no skull mesh
  (`adult_system.py` only loads `root` + region meshes). A human-specific
  string is live, in both languages, on nine deployed pages.
- **F1/F2**: the hub's "structures" group subtitle and its zh/en labels
  no longer match its own membership after the nine systems were added,
  and the hub vs. the location-nav-map use different label text for the
  same group.
- **F4-F8**: lower severity - see the audit file for the full list and
  exact file/line reproductions.

None of these were in scope for the Connectivity Explorer work and
weren't touched by it. Whoever picks this up: read
`.agents/dp_result_nine_systems_audit.md` in full first, then update
`AI_STATE.md`'s handoff log per the usual protocol before editing.

## Locked files

None.
