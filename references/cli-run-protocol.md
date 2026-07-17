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

## CLI Usage Loop

1. Choose the route first. Do not start with a command just because it exists.
2. Run `protocol <route>` and read the printed preflight and completion gates.
3. Confirm whether the target is a skill root, work project, or style library.
4. Set `PYTHONPATH` for the current repository layout.
5. Run `--help` for unfamiliar commands before use.
6. Run the smallest deterministic command that prepares the next artifact.
7. Capture and inspect output paths printed by the command.
8. If the command writes `.agent_tasks.md`, read the task file and have the platform agent fill the expected artifact paths. The CLI has not completed the creative step by writing a task file.
9. Validate artifacts:
   - `agent-validate` for agent run outputs.
   - schema-specific review for JSON candidates.
   - `canon-lint` for canon and character consistency.
   - `review-scene`, `agent-review-scene`, or platform review for prose.
   - `longform-audit`, `chapter-workspace`, and approval summaries for release.
10. Record whether each output remains a candidate, was revised, was promoted, or needs user approval.

## Common CLI Chains

### Project Initialization

```powershell
python -m literary_engineering_workbench protocol work-project-initialization
python -m literary_engineering_workbench init <project>
```

After scaffolding, the platform agent creates or revises the project brief, initial canon candidates, and approval boundaries.

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

`style-lab-compile` and `style-prompt-eval` write `.agent_tasks.md` sidecars; they do not finish the creative/evaluative step by themselves. Before `style-lab-build-skill`, the platform agent must create `style_prompt.md` and `style_prompt.agent.json`. Before default `style-lab-mount`, at least one `style_eval_*.json` effectiveness/risk review must exist and pass the mount readiness gate. Use `--allow-unreviewed` only for an internal experiment.

### Character And World Assets

```powershell
python -m literary_engineering_workbench protocol character-and-world-assets
python -m literary_engineering_workbench agent-create-character <project> --brief "<brief>"
python -m literary_engineering_workbench review-candidate-asset <project> <candidate>
python -m literary_engineering_workbench promote-candidate-asset <project> <candidate> --approval-run-id <id>
```

The platform agent writes candidate content, reviews motive/canon/style risks, and asks for approval before promotion.

### Scene Development

```powershell
python -m literary_engineering_workbench protocol scene-development
python -m literary_engineering_workbench context <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_workbench simulate-scene <project> --scene scenes/scene_0001.yaml --agent
python -m literary_engineering_workbench branch-simulate <project> --scene scenes/scene_0001.yaml --agent
python -m literary_engineering_workbench compose-scene <project> --scene scenes/scene_0001.yaml --agent-tasks
python -m literary_engineering_workbench generate-scene <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_workbench review-scene <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_workbench state-evolve <project> --scene scenes/scene_0001.yaml --agent-tasks
```

The platform agent must handle every task sidecar, draft prose candidate, review character causality and punctuation, then decide whether to revise or request promotion approval.

### Review And Audit

```powershell
python -m literary_engineering_workbench protocol review-and-audit
python -m literary_engineering_workbench canon-lint <project>
python -m literary_engineering_workbench agent-canon-review <project>
python -m literary_engineering_workbench agent-committee <project>
python -m literary_engineering_workbench longform-audit <project>
```

The platform agent turns findings into a ranked revision plan and never treats a clean deterministic report as a substitute for creative review.

### Export And Release

```powershell
python -m literary_engineering_workbench protocol export-and-release
python -m literary_engineering_workbench chapter-workspace <project> --chapter-id chapter_0001 --agent-review
python -m literary_engineering_workbench export-package <project> --chapter-id chapter_0001 --docx
python -m literary_engineering_workbench publish-chapter <project> --chapter-id chapter_0001 --approval-run-id <id>
```

Before delivery, confirm readiness, approvals, canon audit, punctuation, target format, and rollback notes.

## Completion Gate

Do not finish a CLI-backed task until:

- The route protocol was read or printed.
- Command output paths were inspected.
- `.agent_tasks.md` files were handled by the platform agent or listed as pending.
- Generated artifacts have explicit status.
- Relevant validation/review commands ran or were deliberately skipped with a reason.
- Final response reports commands run, important artifacts, checks, and pending approvals.
