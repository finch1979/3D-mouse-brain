# Current task: install `code-router`

Status: complete

## Objective

Install the existing `code-router` skill as a repository-scoped Codex skill for this project.

## Non-goals

- Do not resume or alter the human visual-system deployment in this task.
- Do not modify mouse or human source, data, or generated viewer outputs.
- Do not commit or publish changes.

## Allowed files

- `.agents/current_task.md`
- `.agents/skills/code-router/SKILL.md`
- `.agents/skills/code-router/agents/openai.yaml`

## Forbidden files

- `mouse/data/`, `human/data/`, and `external/`
- Existing files under `mouse/outputs/` and `human/outputs/`
- Existing untracked visual-system work and `project_tree.txt`

## Safety requirements

- Preserve all raw data and generated outputs.
- Preserve unrelated worktree changes.
- Copy the existing user-level skill without changing its workflow semantics.

## Expected checks

- Confirm the installed directory contains `SKILL.md` and `agents/openai.yaml`.
- Compare installed files with the user-level source, allowing only platform line-ending normalization.
- Inspect `git status --short` and verify no unrelated files changed.

## Worker assignments

- Orchestrator only; no worker task is needed for this bounded installation.
- Required worker result files: none.

## Acceptance criteria

- Codex can discover `code-router` from `$REPO_ROOT/.agents/skills/code-router`.
- Installed files match `C:/Users/User/.codex/skills/code-router` apart from CRLF-to-LF normalization.
- Existing worktree changes remain untouched.

## Completion record

- Installed `SKILL.md` and `agents/openai.yaml` under the repository skill location.
- Normalized comparisons found no content differences; only CRLF-to-LF line endings differ.
- `git diff --check` passed.
- Existing untracked human visual-system files and `project_tree.txt` were left untouched.
