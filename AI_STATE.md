# AI_STATE.md

Shared coordination + handoff file for Claude Code, Codex, and any other
agent working on this repo (`finch1979/3D-mouse-brain`). **Read this before
any work.** See [CLAUDE.md](CLAUDE.md) and [AGENTS.md](AGENTS.md) for the
rules this file's protocol depends on.

For a single active task's detailed plan/allowed-files/acceptance-criteria,
see `.agents/current_task.md` (maintained by the `code-router` skill) — this
file is the repo-wide, cross-branch, cross-clone summary; `.agents/current_task.md`
is the per-task detail. Check both.

## Current task

Idle. All merges below are complete and pushed. One item is not yet
actioned: DeepSeek's audit of the nine system pages
(`.agents/dp_result_nine_systems_audit.md`) found real issues, most
notably human-specific "head shell" wording live on the mouse pages —
see `.agents/current_task.md` for the prioritized list. Nobody has
picked this up yet.

## Previous task

Reconciling two independently-developed lines of mouse-atlas work
(connectivity/stimulation explorer + nine new adult systems) that had
diverged across two separate local clones. See handoff log below for the
full incident. As of this entry, both are merged onto `main` and verified
working together.

## Current owner

None (idle). Whoever picks up work next: fill this in with your agent name
and the **exact working-directory path** you are using, before you start.

## Locked files

None.

## Known clones of this repo (fill in / update as you find more)

This repo has been checked out in more than one place on this machine.
**Before creating a new branch or worktree, confirm you know about every
clone below and that yours is not behind `origin/main`:**

- `C:\Users\User\Documents\my-code-project\mouse brain` — primary clone.
  Worktrees: `mouse-brain-redesign` (branch `design/neuro-atlas-upgrade`),
  `K:\my-code-project\mouse-brain-connectivity` (branch
  `feature/connectivity-explorer`), `.claude/worktrees/agent-a92e29d3070ea60d8`.
- `K:\my-code-project\notebooklm\mouse brain` — a **second, independent**
  clone (own `.git`, not a worktree of the primary clone). Worktrees:
  `outputs/neuro-atlas-nine-release`, `outputs/neuro-atlas-nine-release-final`,
  `outputs/neuro-atlas-mobile-release`.

If you find yet another clone or worktree not listed here, add it.

## Latest status

`main` is at the commit that merged the "nine evidence-backed adult
systems" work; the connectivity/stimulation explorer branch
(`feature/connectivity-explorer`) has been rebased onto it and both are
confirmed working together in the same build. Neither has been deployed
to production since this reconciliation — the last verified production
deploy predates both.

## Handoff log

### Template

Date:
Agent:
Working directory (full path):
Role:
Plan:
Files to edit:
Files changed:
Commands run:
Result:
Remaining issues:
Next step:

---

### 2026-09-12 11:21 - Claude Code

Working directory: `K:\my-code-project\mouse-brain-connectivity` (worktree of
the primary clone), plus direct operations against
`C:\Users\User\Documents\my-code-project\mouse brain` and
`K:\my-code-project\notebooklm\mouse brain`.

Role: Debugging / Reconciliation / Planning

**Incident, for future agents to learn from:** a connectivity/stimulation
explorer feature (built in this session, in a worktree of the primary
clone off `main`@`1708a13`) and a "nine evidence-backed adult systems"
feature (built earlier by another agent session, committed on `main` in a
**second, independent clone** at `K:\my-code-project\notebooklm\mouse brain`)
diverged for an unknown period because **neither agent knew the other
clone existed**, and the second clone's 4 commits (including the nine
systems) were never pushed to GitHub — only deployed directly to
production from a local build folder. Production
(`neuro-atlas.pages.dev/mouse/`) ended up showing content that neither
this session's repo state nor GitHub's `main` reflected, which is what
surfaced the problem: the user noticed the live site had systems the
local checkout didn't.

Plan (executed): (1) verify the second clone's unpushed commits were a
clean fast-forward of `origin/main`, (2) push them, (3) fast-forward the
connectivity branch onto the new `main`, (4) resolve the resulting
uncommitted-work conflicts in `site/build_mouse.py` and
`site/templates/scene.js` (both features touch the mouse pathway
registry), (5) discovered and fixed an unrelated pre-existing bug this
surfaced: `mouse/outputs/P56/mesh/997.obj` (and others) had been silently
CRLF-corrupted in the primary clone's working tree by Windows
`core.autocrlf`, predating `.gitattributes`'s `-text` fix for that path —
forced a clean re-checkout of `mouse/outputs/P56/mesh/` to fix.

Files changed (uncommitted, on `feature/connectivity-explorer` as of this
entry): `site/build_mouse.py`, `site/templates/scene.js` (both merged, not
overwritten), plus new connectivity-explorer files under
`mouse/src/mouse_atlas/{build,fetch}/` and `tests/`. Re-checked-out (no
content change relative to git, only fixed working-tree corruption):
`mouse/outputs/P56/mesh/*.obj`.

Commands run: `git fetch`/`merge --ff-only`/`push` on both clones; `git
stash` + `merge --ff-only origin/main` + `stash pop` on the connectivity
worktree; `git checkout HEAD -- mouse/outputs/P56/mesh/` (twice — first
attempt used `find ... -exec rm` which also deleted an *uncommitted* new
mesh file, `218.obj`, that had to be re-downloaded via
`mouse_atlas.fetch.atlas_3d.download_mesh(218)` — **lesson: check
`git status` for untracked files in a directory before bulk-deleting it,
even when re-checkout is the intended fix**); `pytest tests/` (68 passed +
9 subtests, all suites); manual Playwright browser verification of the
merged hub, the connectivity explorer, a new system page (auditory), and
a regression check on the untouched visual page — all passed.

Result: Both features build and run together correctly. Nothing has been
pushed from the connectivity branch yet, and nothing has been deployed.

What was verified: full test suite; browser checks (region counts, page
load, no console errors) on hub / connectivity / auditory / visual pages
in a local build served over http.server. NOT verified: mobile layout for
the merged hub with 14 nav entries; the production deploy checklist in
this project's Pre-Deploy Gate (not attempted — no deploy was requested).

Remaining issues: `feature/connectivity-explorer`'s work is still
uncommitted in its worktree. The second clone
(`K:\my-code-project\notebooklm\mouse brain`) still has a few harmless
uncommitted `.agents/*` files of its own that were not touched.

Recommended next step: commit the connectivity-explorer changes on its
branch (only when the user asks — not done automatically per this
project's git-safety rules), then decide whether to merge that branch to
`main` or open a PR. This `AI_STATE.md` file itself, plus `CLAUDE.md` and
the `AGENTS.md` addition below, are being added specifically so this
divergence incident cannot repeat silently.

---

### 2026-09-12 (later same day) - Claude Code

Working directory: all three known clones/worktrees (see the list above).

Role: Implementation / Reconciliation

Plan: on explicit request, commit and push the connectivity-explorer
work; add hover tooltips on 3D connection tubes and an always-visible
Start CTA for the running-wheel behavior (user-requested UX fixes);
prepare the repo for open-sourcing (LICENSE, a second
`core.autocrlf`-corruption site this incident's own `.gitattributes`
fix had missed, extracting `mouse_connectivity.py`'s ~1,400-line
embedded JS to its own file for readability).

Files changed: see commits `da369cc`, `48d2f54`, `c95c62c` on `main`.

**A second near-miss, same root cause as the incident above:** pushing
this work surfaced that the second clone
(`K:\my-code-project\notebooklm\mouse brain`) had *more* uncommitted
work nobody else's session knew about — a completed, never-integrated
DeepSeek read-only audit of the nine system pages
(`.agents/dp_result.md` + an edited `.agents/current_task.md`). A
naive `git push`/force-merge from another clone would have silently
destroyed it. It also collided at the filename level: an unrelated,
already-committed Phase 3 result already lived at the generic path
`.agents/dp_result.md`, so the incoming merge and the audit's local
file were two *different* documents fighting over one path (an add/add
conflict, not a false alarm). Resolved by committing the audit first
(commit `dc2bf9a`), then a real (non-fast-forward) merge splitting the
two documents into `.agents/dp_result.md` (kept as the Phase 3 record)
and `.agents/dp_result_nine_systems_audit.md` (the audit, new), and
hand-writing a merged `.agents/current_task.md` (merge commit
`d16f13d`) — see that file for what the audit actually found.

Commands run: `git commit`/`fetch`/`merge --ff-only`/`push` across all
three clones; a real `git merge origin/main` (not `--ff-only`) in the
clone with local changes, conflict resolution by hand for
`.agents/current_task.md` and `.agents/dp_result.md`; `pytest tests/`
in each clone after copying the gitignored
`mouse/data/cache/P56/connectivity/` fetch cache into whichever clone
was missing it (68 passed + 9 subtests, every clone); a Playwright pass
against a locally-served rebuild (CTA, hover tooltips, propagation,
language toggle) and against live production after deploying.

Result: all three clones converged on `main` @ `d16f13d`, pushed,
deployed. Nothing lost.

What was verified: full test suite in every clone; live production
HTTP checks (200 on real paths, 404 on junk paths, no relative-link
self-nesting); a full Playwright pass on both the local rebuild and
production.

Remaining issues: the nine-systems audit's findings (see "Current
task" above) are not yet fixed. `project_tree.txt` keeps reappearing
untracked at the repo root in every clone (now gitignored going
forward, but something keeps regenerating it — never identified what).

Recommended next step: action the audit's F3 finding (human-specific
"head shell" wording on mouse pages) first — it's user-visible, in
both languages, on nine live pages, and the fix is scoped to
`site/templates/scene.js`'s explanation text needing a species branch.
