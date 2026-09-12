# CLAUDE.md

This repository (`finch1979/3D-mouse-brain`) may be edited by more than one
AI coding agent — Claude Code, Codex, or others — sometimes in different
local clones on the same machine. Claude Code must not behave as an
isolated agent. Coordinate through the shared state file.

## Project identity

Project name: **3D-mouse-brain** (the Neuro Atlas project's mouse half;
`human/` is the sibling, intentionally-independent half).

Main purpose: build self-contained, single-HTML 3D/2D viewers of the Allen
Mouse Brain Atlas (CCFv3 adult, DeMBA P15, Developing Mouse P14), plus
schematic sensory-pathway pages and a region-connectivity/network-
propagation explorer, deployed to Cloudflare Pages as the "Neuro Atlas"
site (`neuro-atlas.pages.dev`).

## Required files to read before doing any work

Before planning, editing, refactoring, or reviewing, always read:

```text
AI_STATE.md   ← shared cross-clone/cross-branch state; read FIRST
AGENTS.md     ← technical conventions (fetch/build split, self-contained
                viewers, path helpers) AND the multi-agent coordination
                rules appended at its end
README.md
PROJECT_MAP.md
.agents/current_task.md   ← if present: the active task's detailed brief
                             (written by the `code-router` skill)
```

If `AI_STATE.md` does not exist, create it using the template in this
repo's own history (see `git log -- AI_STATE.md`) or ask the human.

## Coordination rule (Two Brains protocol)

This repository has, in the past, been checked out into **more than one
independent local clone at the same time** (not just worktrees of one
clone — genuinely separate `.git` directories, e.g. one under
`C:\Users\User\Documents\my-code-project\mouse brain` and another under
`K:\my-code-project\notebooklm\mouse brain`), and work diverged silently
between them for an unknown period because neither agent session checked
for the other. See `AI_STATE.md`'s handoff log entry from 2026-09-12 for
the full incident. Rules that follow are a direct response to that:

1. **Before starting any new branch or worktree**, run `git remote -v` and
   compare `git log -1 main` (or the relevant branch) against
   `git ls-remote origin <branch>`. If your local branch is behind the
   remote, fetch and fast-forward before branching off it.
2. **Read `AI_STATE.md`'s "Known clones of this repo" list.** If you are
   working from a path not on that list, add it before you start, and
   check whether another listed clone has unpushed work you should pull in
   first.
3. Do not assume Codex knows what Claude Code did, or vice versa. Do not
   assume a fresh clone/worktree of this repo has seen work done in
   another clone/worktree — **git history is only shared once it is
   pushed**; local commits sitting in an unpushed clone are invisible
   to everyone else, including future sessions of the same agent.
4. All cross-agent communication must be written into `AI_STATE.md`
   (repo-wide) and/or `.agents/current_task.md` (per-task detail, per the
   `code-router` skill already in use in this repo).
5. Before editing files, append a plan entry to `AI_STATE.md` (or update
   `.agents/current_task.md` if one is already open for this work).
6. After editing files, append a result entry.
7. If another agent/clone is listed as the current owner of a file or
   area, review only unless explicitly told to implement.
8. Never silently overwrite another agent's unfinished work. If you find
   uncommitted changes or an unfamiliar branch, investigate before
   touching it — see this project's git-safety rules below.
9. **Push non-trivial finished work to `origin`** rather than leaving it
   only in a local clone's `main` — an unpushed `main` is exactly the
   failure mode this file exists to prevent. Confirm with the human before
   pushing, per normal git-safety practice, but don't let real work sit
   local-only indefinitely.

## Default role split

Unless the human gives different instructions:

```text
Claude Code:
- architecture review
- planning
- pipeline / atlas-build design
- scientific/anatomical accuracy checking
- code review
- identifying risks (including cross-clone divergence risk)
- improving prompts and Markdown structure

Codex:
- implementation
- bug fixing
- tests
- refactoring
- file operations
- command execution
```

Claude Code should usually act as planner/reviewer first, implementer
second. The human can override at any time.

## Before editing code

Before modifying any file, append an entry to `AI_STATE.md` (or the
current `.agents/current_task.md`) with: role, plan, files to edit, reason
for change, and a risk level.

Risk levels:

| Level | Meaning | Action |
|-------|---------|--------|
| Low | Isolated change, easy to revert | Proceed |
| Medium | Touches shared code (e.g. `site/build_mouse.py`, `site/templates/scene.js`, `render/viewer_template.*`), needs validation | Proceed with caution, check for conflicting in-flight work first |
| High | Rewrites atlas/pipeline architecture, changes output formats, deletes scripts, touches more than one clone's history | **Stop and explain before editing** |

High-risk changes also include anything that could repeat the divergence
incident: creating a new clone of this repo, working in a clone not listed
in `AI_STATE.md`, or advancing a clone's `main` without an intent to push
it soon.

## After editing code

After any code change, append a result entry to `AI_STATE.md` (or
`.agents/current_task.md`): files changed, commands run, result, what was
verified, remaining issues, recommended next step. If no tests were run,
say so explicitly — do not imply validation happened if it did not.

## Git safety rule

Before starting meaningful work, inspect state on **every clone you know
about** (see `AI_STATE.md`), not just your own working directory:

```bash
git status
git diff
git log --oneline -5
git log origin/main..main   # anything of yours not yet pushed?
```

Before finishing, inspect again and summarize the diff in `AI_STATE.md`.
Never hide uncommitted changes. Never bulk-delete a directory (e.g. to
force a clean re-checkout) without first checking `git status` for
untracked files in it — an untracked file has no git copy to restore from.

## Existing technical conventions

This file governs coordination. For the repo's technical conventions
(fetch/build split, self-contained viewer rules, path helpers, per-age
config pattern), see [AGENTS.md](AGENTS.md) — read it as part of the
required-reads above, not as a separate optional document.
