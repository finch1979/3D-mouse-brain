# Next phase: DeepSeek mechanical audit of nine mouse pages

Status: worker assigned; production release b9122f5 already verified.

## Objective

Read-only audit of bilingual consistency, link destinations and control wording
for the nine new mouse systems. Report concrete findings, not generic advice.
Prior completed router-install task is preserved in code-router-install-completed.md.

## Allowed work

- Read mouse/src/mouse_atlas/build/systems.py and adult_system.py.
- Read mouse/outputs/P56/pathway_meshes/systems.json (small hub registry).
- Read site/build_mouse.py, hub_design.py and templates/mouse.css.
- Read tests/check_mouse_systems_ui.py and docs/architecture/mouse-systems-evidence.md.
- Write ONLY .agents/dp_result.md, in Traditional Chinese.

## Forbidden

- Do not modify any other file, especially raw meshes/data, source, generated HTML,
  existing project_tree.txt, human/, web/lib/, external/ or C: copies.
- Do not run fetch/build/deploy/git mutations, install packages, access credentials,
  contact third parties, or perform network research. Do not change scientific claims.
- Do not read giant HTML/base64 mesh blobs; relevant wording is in the source registry.

## Assignment

DeepSeek via OpenCode: one focused audit pass. Check missing zh/en values,
misleading human-only wording, broken intended internal paths, navigation grouping,
and mismatches between documented controls and new-page behavior. Distinguish
verified findings from items requiring browser confirmation. Do not claim tests run.
Codex: independently verify the report, preserve source/data and review follow-up.

## Expected commands and acceptance

Read files and optionally run read-only text searches or git status. Every finding
must cite file/line and a specific reproduction/check. .agents/dp_result.md must
include files changed, commands run, passed/failed/skipped checks, assumptions,
data-safety statement and unrelated changes noticed. End with a prioritized list;
explicitly say if no actionable issue was found. Do not implement fixes.
