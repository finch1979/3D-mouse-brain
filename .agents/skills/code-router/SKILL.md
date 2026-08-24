---
name: code-router
description: "Multi-agent coding router. Use when the user says: 用 code router, 用 code-router, 叫 DP, 叫 DeepSeek, Codex usage 不夠, 多代理寫程式, multi-agent coding, or asks to route coding/data/repository work across Codex, Claude Code, and DeepSeek/OpenCode. Act as active orchestrator, create .agents/current_task.md, require worker result files, and verify diffs, tests, regression checks, raw-data safety, and unrelated changes before accepting output."
---

# Code Router

Use this skill as an active orchestration workflow for coding, data, automation, and repository-maintenance tasks. Do not treat it as blind delegation. The orchestrator remains responsible for scope, safety, integration, and verification.

## Required Reads

Before planning or dispatching, read the target repository's local instructions when present:

```text
AGENTS.md
CLAUDE.md
AI_STATE.md
SYNC.md
README.md
CONTRIBUTING.md
package.json / pyproject.toml / Makefile / make.cmd
```

Read only the files relevant to the current repository and task. If the target repo requires a shared state or handoff file, follow that repo's format before editing.

## Start The Router

1. Inspect ownership, locks, and active tasks in local coordination files when they exist.
2. Inspect `git status --short` and meaningful diffs before changing anything.
3. Preserve unfinished `.agents/current_task.md` content by archiving or appending a handoff note before replacing it.
4. Create `.agents/current_task.md` with:
   - objective and non-goals
   - files allowed to edit
   - files forbidden to edit
   - safety requirements, including raw-data or generated-output rules from the target repo
   - expected commands and tests
   - worker assignments
   - required result file paths
   - acceptance criteria
5. If the task is high risk, explain the risk and narrow the scope before implementation.

## Routing Rules

- Route high-risk implementation, data integrity, statistics, migrations, security-sensitive edits, and regression-test design to Codex-style careful implementation.
- Route mechanical implementation, repetitive edits, data-prep, search-and-replace work, scaffolding, or fallback attempts to DeepSeek/OpenCode only when the output can be verified from local artifacts.
- Route planning, architecture review, and risk identification to Claude Code when available or when the repository's rules call for reviewer behavior.
- Prefer existing project tools, scripts, and skills over inventing a parallel workflow.
- If the task touches a domain with a dedicated local skill, use that skill before dispatching.
- If a requested worker or tool is unavailable, record that in `.agents/current_task.md` and continue with the safest local fallback.

## Worker Contract

Every worker task must specify a result file. Use these defaults unless the current task needs more specific names:

```text
.agents/codex_result.md
.agents/dp_result.md
.agents/claude_review.md
```

Worker results must include:

- files changed
- commands run
- tests or checks passed/failed
- known failures or skipped validation
- assumptions
- data-safety statement when data files are involved
- unrelated changes noticed

Do not accept a worker's claim without checking the actual files, diff, and command output where possible.

## Safety Gates

Apply these gates before accepting implementation:

- Respect forbidden files and directories from the target repo.
- Preserve raw inputs unless the user explicitly asked to modify them and the repo permits it.
- Do not fabricate statistics, test results, generated outputs, or command output.
- Do not overwrite another agent's unfinished work.
- Do not include unrelated worktree changes in a commit or patch.
- For generated artifacts, regenerate and verify them when the source change requires it, or record why they were not regenerated.
- For report, figure, manuscript, PowerPoint, statistics, or caption changes, follow the target repo's report synchronization rules and use any dedicated report-sync skill when available.

## Verification Before Acceptance

Before integrating or reporting success:

1. Re-read worker result files.
2. Run `git status --short` and inspect meaningful diffs.
3. Verify forbidden or raw input files were not changed.
4. Run task-relevant tests and checks.
5. Run regression checks for the behavior touched.
6. Confirm generated outputs are regenerated when required, or record the blocker.
7. Check for unrelated changes and leave them untouched unless the user explicitly asked to include them.
8. Update the target repo's coordination or handoff file when its local rules require it.

## Failure Handling

If a worker stalls, produces no result file, edits forbidden files, or cannot be verified, reject that output. Record the reason in `.agents/current_task.md` or the repo's coordination file, then either re-dispatch with a narrower task or implement locally.
