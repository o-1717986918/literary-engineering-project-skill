# CLI Run Protocol

Use this protocol whenever the optional `literary_engineering_workbench` CLI participates in a project task. The CLI is a deterministic helper and task-sidecar generator. It does not replace the supervising platform agent.

## Environment Setup

Development workspace:

```powershell
$env:PYTHONPATH = "<skill-root>\\src"
python -m literary_engineering_workbench --help
```

Installed packaged skill:

```powershell
$env:PYTHONPATH = "<skill-root>\\scripts"
python -m literary_engineering_workbench --help
```

Before running task commands, use:

```powershell
python -m literary_engineering_workbench protocol <route>
```

The `protocol` command prints the required references, suggested CLI chain, platform-agent handoff points, completion gates, and forbidden shortcuts for that route.

## Command Attempt Rule

Do not decide in advance that a documented command is unusable because it sounds like it needs a model, an external agent, or a special environment. First run `--help`, print `protocol <route>`, or attempt the smallest safe command with the current project path. If it fails, record the exact command, error, and next workaround. Many `agent-*` commands, including `agent-review-scene`, generate task sidecars; the platform agent then performs the review or creative judgment itself.

## CLI Usage Loop

1. Choose the route first. Do not start with a command just because it exists.
2. Run `protocol <route>` and read the printed preflight and completion gates.
3. Confirm whether the target is a skill root, work project, or style library.
4. Record or prepare a reading receipt: route, references read, project files inspected, command runbook printed, and missing context.
5. Set `PYTHONPATH` for the current repository layout.
6. Run `--help` for unfamiliar commands before use.
7. Run the smallest deterministic command that prepares the next artifact; do not skip it without a concrete project-state reason.
8. Capture and inspect output paths printed by the command.
9. If the command writes `.agent_tasks.md`, read the task file immediately when feasible and have the platform agent fill the expected artifact paths. The CLI has not completed the creative/review step by writing a task file.
10. After filling sidecars, inspect the produced Markdown/JSON/prose and record whether it is candidate, pass, pass_with_notes, revise_required, or pending.
11. When sidecar or gate status is unclear, run `agent-task-status <project>` or `route-audit <project> --route <route>` and resolve or list pending items.
12. Validate artifacts:
   - `agent-validate` for agent run outputs.
   - schema-specific review for JSON candidates.
   - `canon-lint` for canon and character consistency.
   - `review-scene`, `agent-review-scene`, or platform review for prose.
   - `word-budget`, `longform-audit`, `chapter-workspace`, and approval summaries for longform/release.
13. Record whether each output remains a candidate, was revised, was promoted, or needs user approval.

## Common CLI Chains

### Project Initialization

```powershell
python -m literary_engineering_workbench protocol work-project-initialization
python -m literary_engineering_workbench init <project>
```

After scaffolding, the platform agent creates or revises the project brief, initial canon candidates, and approval boundaries.

### Source Ingest

```powershell
python -m literary_engineering_workbench protocol source-ingest
python -m literary_engineering_workbench source-ingest <project> --source <source-file-or-dir> --title "<title>" --work-id <work-id>
```

The CLI writes raw text, chunks, `source_manifest.json`, `source_ingest.md`, and `extract_project_files.agent_tasks.md`. The platform agent must read the sidecar and write extracted project brief, characters, world, outline, timeline, foreshadowing, style notes, and source-ingest review files as candidates. Do not promote source-derived material without evidence, review, and approval.

### Longform Planning

```powershell
python -m literary_engineering_workbench protocol longform-planning
python -m literary_engineering_workbench word-budget <project> --target-words 500000 --volumes 5 --genre mystery
```

The CLI writes `plot/word_budget/word_budget.md`, `plot/word_budget/word_budget.json`, and `plot/word_budget/word_budget.agent_tasks.md`. The platform agent must read the sidecar, create `plot/candidates/outlines/word_budget_expansion.md`, write `reviews/word_budget/word_budget_review.md`, and decide whether the project has enough narrative inventory before bulk generation.

The same command also binds the budget to chapter and scene inventory. It writes `plot/word_budget/scene_inventory_expansion.agent_tasks.md`; the platform agent must use it to create `plot/candidates/scenes/word_budget_scene_inventory.md` and `reviews/word_budget/scene_inventory_review.md`. The scene inventory candidate should list per-chapter target words, existing cleaned body words, missing scenes, and expansion tasks instead of merely asking current scenes to grow longer.

Use `longform-budget` as an alias. Do not treat `word_budget.json` as final plot; it is a numerical scaffold and readiness signal.

Check route readiness before bulk scene generation:

```powershell
python -m literary_engineering_workbench route-audit <project> --route longform-planning
```

### Style Engineering

```powershell
python -m literary_engineering_workbench protocol style-engineering
python -m literary_engineering_workbench style-lab-author <style-library> <author-id>
python -m literary_engineering_workbench style-lab-work <style-library> <author-id> <work-id>
python -m literary_engineering_workbench style-lab-import <style-library> <author-id> <work-id> <source-text>
python -m literary_engineering_workbench style-lab-compile <style-library> <author-id>
python -m literary_engineering_workbench style-lab-build-skill <style-library> <author-id>
python -m literary_engineering_workbench style-lab-mount <project> <style-skill>
```

The platform agent must write or approve the LLM-facing style prompt and judge its effectiveness. Exact imitation is limited to public-domain or authorized corpora.

`style-lab-compile` and `style-prompt-eval` write `.agent_tasks.md` sidecars; they do not finish the creative/evaluative step by themselves. Before `style-lab-build-skill`, the platform agent must create `style_prompt.md` and `style_prompt.agent.json`; the prompt must be a detailed but executable 500-2500 non-whitespace content characters and include the required high-quality prompt blocks. Before default `style-lab-mount`, at least one `style_eval_*.json` effectiveness/risk review must exist and pass the mount readiness gate. Formal Skill hosts must not use `--allow-unreviewed` to bypass style readiness.

### Character And World Assets

```powershell
python -m literary_engineering_workbench protocol character-and-world-assets
python -m literary_engineering_workbench agent-create-character <project> --brief "<brief>"
python -m literary_engineering_workbench review-candidate-asset <project> <candidate>
python -m literary_engineering_workbench promote-candidate-asset <project> <candidate> --approval-run-id <id>
```

The platform agent writes candidate content, reviews motive/canon/style risks, and asks for approval before promotion.

### Scene Development

The following chain is for one scene. In a chapter or volume batch, repeat it for every `scenes/{scene_id}.yaml`; never use one completed scene as a proxy for the remaining scenes.

```powershell
python -m literary_engineering_workbench protocol scene-development
python -m literary_engineering_workbench context <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_workbench simulate-scene <project> --scene scenes/scene_0001.yaml --agent
python -m literary_engineering_workbench branch-simulate <project> --scene scenes/scene_0001.yaml --agent
# Platform agent fills branches/scene_0001/branch_selection.md with decision: selected and selected_branch.
python -m literary_engineering_workbench compose-scene <project> --scene scenes/scene_0001.yaml --agent-tasks
python -m literary_engineering_workbench route-audit <project> --route scene-development
python -m literary_engineering_workbench generate-scene <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_workbench agent-review-scene <project> --scene scenes/scene_0001.yaml --draft drafts/candidates/scene_0001-platform-agent.md
# Read reviews/agent/scene_0001_scene_review.agent_tasks.md, including Style Lint evidence, then write the expected scene_review.v1 JSON and Markdown report yourself as platform agent.
python -m literary_engineering_workbench promote-candidate <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_workbench review-scene <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_workbench revise-scene <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_workbench state-evolve <project> --scene scenes/scene_0001.yaml --agent-tasks
```

The main platform agent must handle every task sidecar, formally record branch selection before composition/generation, personally draft the prose candidate, review the exact candidate before promotion, then review promoted draft character causality, mounted style adherence, punctuation, deterministic Style Lint evidence, and state-patch consequences. Subagents may provide only bounded mechanical support such as evidence summaries, issue lists, schema checks, continuity tables, and word-count inventories; they must not draft, rewrite, polish, expand, or finalize body text. `agent-review-scene` must be tried, not guessed about: it generates the review task, `Style Lint (auto-detected)` evidence, and expected report paths; the supervising platform agent performs the review and writes `scene_review.v1`, explicitly handling medium-or-higher lint findings. `promote-candidate` blocks unless `reviews/agent/{scene_id}_scene_review.json` cites the exact candidate path and has a clean `conclusion=pass`; formal Skill hosts must not use `--allow-unreviewed` or `--allow-review-notes`. `route-audit --route scene-development` is the per-scene ledger and must show that each scene has context, RP, branch manifest, formal branch selection, ready composition, prose candidate, exact-candidate review, promotion manifest, promoted draft, and state patch before chapter/export readiness. When `style/active_style_skill.json` exists, formal chapter readiness and export require `style_adherence.status=pass`; `pass_with_notes`, `not_applicable`, missing, or `revise_required` blocks readiness/export until revised and re-reviewed. Use `revise-scene` when `agent-review-scene`, `review-scene`, style adherence, or human notes identify local fixes; it writes a revision prompt manifest and `.agent_tasks.md` that asks the main platform agent to produce a revision candidate and report without overwriting the formal draft.

### Review And Audit

```powershell
python -m literary_engineering_workbench protocol review-and-audit
python -m literary_engineering_workbench canon-lint <project>
python -m literary_engineering_workbench agent-canon-review <project>
python -m literary_engineering_workbench agent-committee <project>
python -m literary_engineering_workbench longform-audit <project>
python -m literary_engineering_workbench agent-task-status <project>
python -m literary_engineering_workbench route-audit <project> --route review-and-audit
```

The platform agent turns findings into a ranked revision plan and never treats a clean deterministic report as a substitute for creative review.

### Task And Route Dashboard

```powershell
python -m literary_engineering_workbench agent-task-status <project>
python -m literary_engineering_workbench route-audit <project> --route scene-development
```

`agent-task-status` scans project `.agent_tasks.md` files, checks whether their expected artifact paths exist, and writes `workflow/agent_task_status.md` / `.json`. `route-audit` writes `workflow/route_audit.md` / `.json` and adds route-specific gates such as word-budget expansion, scene sidecar completion, promotion candidate review, mounted-style adherence review, chapter readiness, and export readiness. These commands are diagnostic; the platform agent must still complete creative tasks or record why they remain pending.

### Export And Release

```powershell
python -m literary_engineering_workbench protocol export-and-release
python -m literary_engineering_workbench chapter-workspace <project> --chapter-id chapter_0001 --agent-review
python -m literary_engineering_workbench export-package <project> --chapter-id chapter_0001 --docx
python -m literary_engineering_workbench publish-chapter <project> --chapter-id chapter_0001 --approval-run-id <id>
```

Before delivery, confirm readiness, approvals, canon audit, punctuation, target format, and rollback notes. `export-package` rebuilds or verifies the chapter workspace before packaging and blocks non-ready scenes by default; formal Skill hosts must not use `--include-blocked`.

If `export-package` blocks, do not write a custom export script, use debug flags, or call the output final. Run `chapter-workspace` / `route-audit`, resolve missing scene reviews or sidecars, then export through the formal path.

## Completion Gate

Do not finish a CLI-backed task until:

- The route protocol was read or printed.
- Documented commands needed by the route were tried or skipped only with a concrete project-state reason.
- Reading receipt was recorded or summarized.
- Command output paths were inspected.
- `.agent_tasks.md` files were handled by the platform agent or listed as pending.
- `agent-task-status` or route-specific `route-audit` ran when completion state was ambiguous.
- Generated artifacts have explicit status.
- Relevant validation/review commands ran or were deliberately skipped with a reason.
- Final response reports commands run, important artifacts, checks, and pending approvals.
