# Workflows

These commands are optional deterministic helpers for a tool-layer director. In normal Codex/Claude use, the platform agent may reason, generate, review, and edit files directly by following `SKILL.md`, `AGENTS.md`, `agentread.yaml`, and `references/project-director-playbook.md`.

Use the CLI when repeatability matters: scaffolding, indexing, context packets, style compilation, schema/lint checks, audits, exports, and regression tests.

## Mandatory CLI Protocol

Before any route-specific command chain:

1. Select the primary route from `agentread.yaml`.
2. Read `references/agent-run-protocol.md`.
3. Read `references/cli-run-protocol.md` when a CLI command will be used.
4. Print the route runbook:

```powershell
$env:PYTHONPATH = "<skill-root>\\src"       # development copy
# or: $env:PYTHONPATH = "<skill-root>\\scripts"  # installed package
python -m literary_engineering_workbench protocol <route>
```

Use route keys such as `project-director`, `work-project-initialization`, `style-engineering`, `character-and-world-assets`, `scene-development`, `review-and-audit`, `export-and-release`, and `optional-cli`.

The task is not complete until the route completion gates in the runbook are accounted for.

## Tool-Layer Supervision Rule

Any command that writes creative material, drafts JSON, repairs schema output, simulates characters, scores branches, composes scenes, or chooses workflow steps is supervised by the tool-layer agent that loaded this skill. Formal commands write `.agent_tasks.md` sidecars and expected artifact paths; the platform agent fills those artifacts. The command must not become the project director by itself.

Before running such a command, the platform agent should choose the task, prompt/context packet, constraints, and approval boundary. After running it, the platform agent must read the task sidecar, write or inspect the expected artifacts, validate schema where relevant, check canon/character/style constraints, and decide whether to revise, keep as candidate, ask the user, or promote after approval.

This rule covers `source-ingest`, `extract-existing-work`, `agent-create-*`, `asset-create`, `agent-build-json`, `agent-review-scene`, `agent-canon-review`, `review-candidate-asset`, `agent-plan-patch`, `agent-style-prompt`, `agent-committee`, `style-prompt`, `style-prompt-eval`, `style-lab-compile`, `simulate-scene`, `branch-simulate`, `compose-scene`, `generate-scene`, `state-evolve`, and `run-workflow`.

`agent-run`, `agent-repair`, provider-backed Python functions, `/director/chat`, and `director-chat` are legacy/debug paths. Use them only when the user explicitly asks to test local provider behavior.

Use the bundled CLI through:

```powershell
$env:PYTHONPATH = "<skill-root>\\scripts"
python -m literary_engineering_workbench <command>
```

## Configure Global Provider Settings

Long-lived model and console defaults live in `%USERPROFILE%\.lew\config.json` by default. Use `LEW_CONFIG_PATH` only when you want a separate config file.

```powershell
python -m literary_engineering_workbench config-init
python -m literary_engineering_workbench config-show
```

For DeepSeek official API:

```powershell
$env:DEEPSEEK_API_KEY = "your-api-key"
python -m literary_engineering_workbench config-set-profile `
  --name deepseek `
  --api-base "https://api.deepseek.com" `
  --model "deepseek-v4-flash" `
  --api-key-env "DEEPSEEK_API_KEY" `
  --temperature 0.4 `
  --max-tokens 4000 `
  --timeout 120 `
  --activate
```

The config file can store provider settings and, for local use, a saved profile `api_key`. Config endpoints and previews redact the key. `LEW_MODEL_*` variables still work as temporary overrides.

Formal creative/review commands ignore provider routing and target the platform agent through task sidecars. Global provider settings remain only for legacy/debug commands and local API experiments.

## Initialize A Work Project

```powershell
python -m literary_engineering_workbench init "<work-dir>" --title "作品名" --premise "一句话故事前提" --genre "类型"
```

Creates:

- `project.yaml`
- `AGENTS.md`
- `agentread.yaml`
- `canon/`
- `characters/`
- `plot/`
- `style/`
- `sources/`
- `scenes/`
- `drafts/`
- `reviews/`
- `memory/`
- `branches/`
- `exports/`
- `releases/`

Character files include `background_story`. Use it as an internal cause of behavior, not as direct exposition in final prose.

For long projects, keep each character in a separate `characters/{character_id}.yaml` file and set `importance`. Major characters are loaded into most scene context packets; secondary/cameo characters are loaded only when the scene includes them in `participants`, `referenced_characters`, or `character_refs`. Scene files should therefore list every on-page participant and any off-page character whose memory, threat, relationship, or background pressure materially affects the scene.

## Import Existing Works For Continuation Or Rewrite

Use this when the user provides an existing text, old draft, complete work, script, or pseudo-record source and wants the project to continue, rewrite, adapt, or analyze it.

```powershell
python -m literary_engineering_workbench protocol source-ingest
python -m literary_engineering_workbench source-ingest "<work-dir>" `
  --source "<source-file-or-dir>" `
  --title "源作品标题" `
  --work-id "source-work" `
  --mode continuation
```

`--source` accepts `.txt`, `.md`, or `.markdown` files and directories. `--text` can be used for short pasted material:

```powershell
python -m literary_engineering_workbench source-ingest "<work-dir>" --text "源文本片段" --title "旧稿" --work-id old-draft
```

The command writes:

- `sources/imports/{work_id}/raw/*.txt`
- `sources/imports/{work_id}/chunks/chunk_0001.md`
- `sources/imports/{work_id}/source_manifest.json`
- `sources/imports/{work_id}/source_ingest.md`
- `sources/imports/{work_id}/extract_project_files.agent_tasks.md`

The platform agent must then read `extract_project_files.agent_tasks.md` and write the expected candidate outputs:

- `sources/imports/{work_id}/extracted/project_brief.md`
- `characters/candidates/extracted/{work_id}_characters.md`
- `canon/candidates/extracted/{work_id}_world.md`
- `plot/candidates/extracted/{work_id}_outline.md`
- `plot/candidates/extracted/{work_id}_timeline.md`
- `plot/candidates/extracted/{work_id}_foreshadowing.md`
- `style/candidates/{work_id}_style_generation_notes.md`
- `reviews/source_ingest/{work_id}_extraction_review.md`

Every extracted claim should include evidence references, confidence, unknowns, and contradiction notes. Do not copy long source passages into project files. Do not promote extracted settings into formal canon, character files, plot files, or mounted style without review and user approval.

## Build A Demo Project

```powershell
python -m literary_engineering_workbench demo-project "<demo-work-dir>" --title "文学工程 Demo"
```

The demo uses original sample text and writes platform-agent task sidecars for asset creation, scene/canon review, committee review, and workflow continuation. It does not call local dry-run or HTTP providers for formal artifacts.

## Build Memory And Context

```powershell
python -m literary_engineering_workbench index "<work-dir>"
python -m literary_engineering_workbench search "<work-dir>" "人物 地点 线索"
python -m literary_engineering_workbench knowledge-build "<work-dir>"
python -m literary_engineering_workbench knowledge-search "<work-dir>" "人物 地点 线索" --canon-status confirmed
python -m literary_engineering_workbench context "<work-dir>" --scene scenes/scene_0001.yaml --rebuild-index
```

Use `context` before scene drafting or roleplay simulation. Use `knowledge-build` when a workflow needs metadata-rich retrieval with canon status, source kind, scene id, chapter id, or character id.

## Compile A Style Profile

```powershell
python -m literary_engineering_workbench style-profile "<corpus-dir>" --out-dir "<work-dir>\\style\\demo-author" --name "示例文风" --author "示例作者" --source-note "公版或授权语料"
```

Use exact imitation only for public-domain or authorized corpora. For other authors, abstract high-level craft features. The final style-learning asset is an LLM-facing prompt, not the metrics report:

```powershell
python -m literary_engineering_workbench style-prompt "<work-dir>\\style\\demo-author"
```

This writes `style_prompt.agent_tasks.md` plus expected `style_prompt.md` and `style_prompt.agent.json` paths. The platform agent reads the task and writes the actual LLM-facing style constraint prompt.

Evaluate a back-translated or outline-expanded candidate:

```powershell
python -m literary_engineering_workbench style-eval "<work-dir>\\style\\demo-author" --reference "<reference.txt>" --candidate "<candidate.txt>" --mode back-translation
```

Outputs JSON metrics and a markdown report under `evaluation_results/{mode}/`, including style similarity and copy-risk indicators.

Ask the platform agent to generate a back-translation / outline-expansion candidate through `style_prompt.md`, then evaluate prompt effectiveness:

```powershell
python -m literary_engineering_workbench style-prompt-eval "<work-dir>\\style\\demo-author" --reference "<reference.txt>" --input "<english-or-outline.txt>" --mode back-translation
```

## Style Lab

The local frontend exposes this as `文风学习`. Treat each author as a style project, each source work as a subproject, and the generated Style Skill as the mountable artifact for creative projects.

```powershell
python -m literary_engineering_workbench style-lab-author --name "作者名" --source-note "公版或授权语料"
python -m literary_engineering_workbench style-lab-work --author-id "<author-id>" --title "作品名"
python -m literary_engineering_workbench style-lab-import --author-id "<author-id>" --work-id "<work-id>" --file "<source.txt>"
python -m literary_engineering_workbench style-lab-compile --author-id "<author-id>"
python -m literary_engineering_workbench style-lab-build-skill --author-id "<author-id>"
python -m literary_engineering_workbench style-lab-mount "<work-dir>" --style-id "<style-id>"
```

`style-lab-compile` and the front-end `/style-lab/compile` endpoint compile deterministic profile/metrics, then write a platform-agent task sidecar for `style_prompt.md` and `style_prompt.agent.json`. They do not call a local provider for the LLM-facing prompt. The platform agent must read the task, write both expected artifacts, and inspect them before building a Style Skill. A release-grade prompt must be 500-1500 non-whitespace content characters: under 500 is too thin to constrain style, while over 1500 is too diffuse for stable mounting. It must also satisfy high-quality prompt structure: identity/boundary, priority, core mechanism, narrative distance, syntax/rhythm, punctuation, imagery/sensory, psychology/behavior, dialogue/tone, forbidden tendencies, and output self-check.

`style-prompt-eval` and `/style-lab/evaluate` likewise write a platform-agent task for the back-translation / outline-expansion candidate. After the platform agent writes the expected candidate and manifest, run deterministic `style-eval` or provide an equivalent `style_eval_*.json` review before mounting.

`style-lab-mount` requires readiness evidence by default: `prompt.md`, a prompt detail length of 500-1500 non-whitespace content characters, required style-prompt content blocks, `style_prompt.agent.json`, and at least one accepted `evaluation_results/*/style_eval_*.json`. Use `--allow-unreviewed` only for internal experiments, and record that the mounted style is not ready for release-grade writing.

Mounted style skills are stored in the creative project under `style/mounted/{style_id}/` with `style/active_style_skill.json` as the active pointer. During generation, the mounted `prompt.md` is the highest-priority expression constraint, while canon, character facts, plot causality, safety boundaries, and explicit user constraints still take precedence.

`references/punctuation-standard.md` is the baseline expression hygiene layer below every Style Skill. A style prompt may specify punctuation rhythm, density, and pauses, but it should not cause English punctuation to leak into Chinese prose, replace `……` with `...`, or use nonstandard dashes unless the project records a deliberate exception.

## Generic Agent Run

Use `agent-run` only for legacy/debug local provider regression. For formal JSON, patch, style, asset, scene, canon, or committee work, use the specialized platform-task commands.

```powershell
python -m literary_engineering_workbench agent-run "<work-dir>" `
  --agent-id scene-reviewer `
  --task review-scene `
  --system-text "You are a literary engineering review agent." `
  --user-text "Review scene_0001 for character logic, canon risk, and revision actions."
```

It writes:

- `agents/runs/{run_id}/input.prompt.json`
- `agents/runs/{run_id}/raw_output.md`
- `agents/runs/{run_id}/parsed_output.json`
- `agents/runs/{run_id}/validation_report.md`

For an explicit real HTTP model endpoint:

```powershell
$env:DEEPSEEK_API_KEY = "your-api-key"
python -m literary_engineering_workbench config-show
python -m literary_engineering_workbench agent-run "<work-dir>" --agent-id canon-reviewer --task review-canon --system "<system-prompt.md>" --user "<user-prompt.md>"
```

Agent output is not canon. Even parsed JSON should be treated as evidence until a schema gate, review command, and platform-agent review accept it as candidate material; human approval is still required before promotion when the change affects canon, character state, plot direction, style policy, release status, or user-facing decisions.

## Creative Director

The tool-layer platform agent is the preferred Creative Director. Use normal Codex/Claude conversation, file inspection, edits, and subagents first.

Use the local `director-chat` command only for legacy regression, local demos, or when the user explicitly asks to exercise the built-in director implementation:

```powershell
python -m literary_engineering_workbench director-chat "<work-dir>" --message "把项目推进成双主角悬疑长篇，先补强角色压力和世界观限制"
python -m literary_engineering_workbench director-status "<work-dir>"
```

The local director chooses the internal workflow, runs schema-gated specialist agents, and writes:

- `director/runs/{run_id}/director_decision.json`
- `director/runs/{run_id}/director_report.md`
- `director/runs/{run_id}/agent_decision/`
- `director/runs/{run_id}/tool_loop.json`
- `director/runs/{run_id}/agent_observe_{step}/`
- optional delegated `workflow/runs/{run_id}-wf/`

`director_tools` is a bounded local tool loop: the local director decides the next safe tool, executes it, observes artifacts/status, and then decides whether another tool is needed.

For the project-type skill route, prefer the platform agent's own planning and subagents. If the local director is exercised, treat its `director_decision.json`, `tool_loop.json`, delegated agent runs, and report as evidence for the platform agent to review, not as the final project decision.

## Agent Asset Workshop

Write platform-agent tasks for project-seeding candidates:

```powershell
python -m literary_engineering_workbench agent-create-character "<work-dir>" --brief "谨慎的调查者" --target-id linzhou
python -m literary_engineering_workbench agent-create-world "<work-dir>" --brief "档案被垄断的城市"
python -m literary_engineering_workbench agent-create-outline "<work-dir>" --brief "调查旧档案的三幕结构"
python -m literary_engineering_workbench list-candidate-assets "<work-dir>"
```

Write platform-agent review tasks and then promote only after the expected candidate/review artifacts exist and approval has been recorded:

```powershell
python -m literary_engineering_workbench review-candidate-asset "<work-dir>" "<candidate-id-or-path>"
python -m literary_engineering_workbench promote-character-candidate "<work-dir>" "<candidate-id-or-path>" --approval-run-id "<candidate-id>"
```

For internal experiments only, pass `--allow-unapproved`. Candidate assets are written under `characters/candidates/`, `canon/candidates/`, and `plot/candidates/`; they are not canon until promoted. The platform agent should inspect every generated candidate and review report before asking for approval or using it in later planning.

Validate or repair an agent run:

```powershell
python -m literary_engineering_workbench agent-validate "<work-dir>" --run-id "<run-id>" --schema generic_agent_output.v1
python -m literary_engineering_workbench agent-repair "<work-dir>" --run-id "<run-id>" --schema scene_review.v1
```

Run specialized agent review commands:

```powershell
python -m literary_engineering_workbench agent-review-scene "<work-dir>" --scene scenes/scene_0001.yaml
python -m literary_engineering_workbench agent-canon-review "<work-dir>"
python -m literary_engineering_workbench agent-plan-patch "<work-dir>" --target characters/linzhou.yaml --source drafts/scenes/scene_0001.md
python -m literary_engineering_workbench agent-style-prompt "<work-dir>\\style\\demo-author"
python -m literary_engineering_workbench agent-committee "<work-dir>" --subject scene-0001 --source drafts/scenes/scene_0001.md
```

## Canon / Plot Lint

```powershell
python -m literary_engineering_workbench canon-lint "<work-dir>"
```

Use this before chapter readiness checks, exports, publication, or large-scale expansion. It writes:

- `reviews/canon_lint.md`
- `reviews/canon_lint.json`

The lint only reports project-state issues. It does not edit canon, approve candidates, or modify drafts.

## Scene Loop

```powershell
python -m literary_engineering_workbench simulate-scene "<work-dir>" --scene scenes/scene_0001.yaml --rebuild-context
python -m literary_engineering_workbench simulate-scene "<work-dir>" --scene scenes/scene_0001.yaml --agent
python -m literary_engineering_workbench branch-simulate "<work-dir>" --scene scenes/scene_0001.yaml --rebuild-context
python -m literary_engineering_workbench compose-scene "<work-dir>" --scene scenes/scene_0001.yaml --rebuild-context
python -m literary_engineering_workbench generate-scene "<work-dir>" --scene scenes/scene_0001.yaml --rebuild-context
python -m literary_engineering_workbench promote-candidate "<work-dir>" --scene scenes/scene_0001.yaml
python -m literary_engineering_workbench draft-scene "<work-dir>" --scene scenes/scene_0001.yaml --rebuild-context
python -m literary_engineering_workbench review-scene "<work-dir>" drafts/scenes/scene_0001.md
python -m literary_engineering_workbench state-evolve "<work-dir>" --scene scenes/scene_0001.yaml
```

`branch-simulate` writes scored branch candidates under `branches/{scene_id}/`:

- `branch_simulation.md`
- `branch_manifest.json`
- `branch_selection.md`

Branches are not canon. The recommended branch is only a scoring hint; the platform agent should evaluate it against story direction, canon, character pressure, and user intent before recording the actual human or tool-layer decision in `branch_selection.md`.

Use `branch-simulate --agent` / `--agent-tasks` to write `branch_manifest.agent_tasks.md`. This sidecar tells the platform agent how to review branch scores and choose or revise a branch without polluting `branch_manifest.json`.

`compose-scene` turns the formally selected branch into a creation packet under `drafts/compositions/{scene_id}_composition.md` and `.json`, including scene beats, subtext, dialogue intents, sensory palette, prose seed, revision targets, and writeback candidates. If `branch_manifest.json` exists but `branch_selection.md` still lacks `decision: selected` plus `selected_branch`, formal composition is blocked. The recommended branch is never used by default; `--allow-recommended-branch` is only for internal experiments and writes `selection_source: recommended`, which is not ready for generation.

Use `compose-scene --agent-tasks` to write `drafts/compositions/{scene_id}_composition.agent_tasks.md`. Keep `[AGENT_TASK: ...]` out of the composition Markdown because it may be read into `generate-scene` prompt packs.

When character `background_story` is present, scene and branch work should convert it into choices, hesitation, avoidance, misreadings, tone, and relationship pressure. Do not turn it into an explanatory background paragraph unless the selected scene explicitly reveals the past.

`generate-scene` writes a prompt manifest and `drafts/candidates/{scene_id}-platform-agent.agent_tasks.md`. It does not call a local provider, does not overwrite `drafts/scenes/`, and does not write canon. If a composition packet exists, `generate-scene` requires `selection_source: selection`; unselected or recommended-only composition packets are blocked unless `--allow-unselected-composition` is explicitly passed for internal preview. The platform agent reads the prompt manifest, writes the expected candidate Markdown and manifest JSON, then reviews the candidate before promotion.

The prompt manifest includes `generation_standards.style`. This is a generation-time contract, not merely a review checklist: before drafting, the platform agent should translate the mounted Style Skill / style profile into concrete scene tactics for narrative distance, syntax/paragraph rhythm, imagery and sensory routing, psychological presentation, dialogue density, and punctuation cadence. Do not output that plan in the candidate; use it to reduce style-review failures before they happen.

Generated candidates and promoted drafts should pass the standard Chinese punctuation gate. `review-scene` reports punctuation issues under `Punctuation Standard Test`; fix those before chapter readiness or export unless the user explicitly approves a recorded exception.

Generated candidates and promoted drafts should also pass the AI trace reduction gate. `review-scene` reports dense “不是……而是……” frames, abstract summary language, explanatory psychology labels, template transitions, symmetric slogan rhythm, omniscient theme explanation, and aphoristic endings under `AI Trace Reduction Test`. Treat these as revision signals unless the project records a deliberate stylistic exception.

`promote-candidate` turns a selected model candidate into `drafts/scenes/{scene_id}.md` and writes `drafts/promotions/{scene_id}_promotion.md` / `.json`. It does not confirm canon and does not write characters.

The prompt manifest records system/user messages and source files for the platform agent. It must remain pure audit data and must not contain `[AGENT_TASK: ...]`.

Review conclusions:

- `pass`: ready for chapter workspace.
- `pass_with_notes`: usable after human acceptance.
- `revise_required`: not exportable.
- `reject`: not exportable.

`state-evolve` builds a reviewable character-state patch under `characters/state_patches/` from a scene draft, generated candidate, or composition artifact. If the source is a composition packet, it must have passed the same formal branch-selection gate as `generate-scene`; unselected or recommended-only composition packets are blocked. It does not modify `characters/*.yaml`; the platform agent must inspect the patch for hidden-background causality, canon risk, and unintended relationship drift. Major character state changes still require human confirmation before any later writeback.

Use `state-evolve --agent-tasks` to write `characters/state_patches/{scene_id}_state_patch.agent_tasks.md` for platform-agent review while keeping the JSON patch clean.

After a workflow run is approved, apply a character state patch with:

```powershell
python -m literary_engineering_workbench state-apply "<work-dir>" --patch characters/state_patches/scene_0001_state_patch.json --approval-run-id "<approved-run-id>"
```

`state-apply` writes only approved character state, arc, relationship, and memory reference fields. It does not write canon.

## Chapter Workspace

```powershell
python -m literary_engineering_workbench chapter-workspace "<work-dir>" --chapter-id chapter_0001 --build-missing --review-drafts
```

Scene states:

- `ready`: draft exists, static review passed, platform Agent scene review JSON exists, schema passes, and conclusion is `pass` or `pass_with_notes`.
- `needs_draft`: no usable body.
- `needs_review`: body exists but review missing.
- `needs_agent_review`: static review exists but formal platform Agent scene review JSON is missing.
- `blocked`: review failed.

## Longform Audit

```powershell
python -m literary_engineering_workbench longform-audit "<work-dir>" --target-length 100000
```

Audits:

- scene schema completeness;
- character inventory gaps;
- draft and review readiness;
- context packet presence;
- chapter workspace presence;
- foreshadowing debt;
- lightweight graph structure.

## Export Package

```powershell
python -m literary_engineering_workbench export-package "<work-dir>" --chapter-id chapter_0001
python -m literary_engineering_workbench export-package "<work-dir>" --chapter-id chapter_0001 --formats md,docx
python -m literary_engineering_workbench export-docx "<work-dir>\\exports\\chapter_0001\\chapter_0001_novel.md" --kind novel
```

Outputs:

- novel chapter draft;
- screenplay working draft;
- long-video prompt pack;
- optional editable DOCX files for the same artifacts;
- `export_manifest.json`.

By default only `ready` scenes are exported. Use `--include-blocked` only for internal preview.

Final exported prose and screenplay files are cleaned delivery artifacts. They should not expose scene workbench sections, writeback candidates, canon notes, prompt manifests, review status, workflow IDs, or “导出规则” text. Audit and provenance remain in `export_manifest.json`, release manifests, review files, and workflow logs.

## Publish Chapter

```powershell
python -m literary_engineering_workbench publish-chapter "<work-dir>" --chapter-id chapter_0001 --approval-run-id "<approved-run-id>"
python -m literary_engineering_workbench publish-chapter "<work-dir>" --chapter-id chapter_0001 --approval-run-id "<approved-run-id>" --export-formats md,docx
```

Default gates:

- `canon-lint` has no blocking issues.
- `chapter-workspace` has no non-ready scenes.
- `export-package` exports every scene without skips.
- `workflow/approvals/index.jsonl` contains an `approve` record.

Outputs:

- `releases/{chapter_id}/{release_id}/publish_manifest.json`
- `releases/{chapter_id}/{release_id}/release_notes.md`
- `releases/{chapter_id}/{release_id}/rollback.md`
- optional published `.docx` delivery files when `--export-formats md,docx` is used
- `releases/{chapter_id}/latest.json`

Use `--allow-unapproved` only for internal candidate releases.

## Workflow Runner

```powershell
python -m literary_engineering_workbench run-workflow "<work-dir>" --mode full-cycle --scene scenes/scene_0001.yaml --chapter-id chapter_0001
```

Modes:

- `scene-loop`: index, context, roleplay simulation, branch simulation, scene composition, optional generation, optional promotion, draft workspace, review, character state patch.
- `chapter-publish`: chapter workspace, longform audit, export package.
- `full-cycle`: scene loop followed by chapter publish.
- `project-seeding`: world, character, and outline candidate creation plus review.
- `character-lab`: character, background-story, and relationship candidates plus review.
- `worldbuilding-lab`: world, location, and organization candidates plus review.
- `outline-lab`: outline, chapter-plan, and scene-list candidates plus review.

Outputs:

- `workflow/runs/{run_id}/workflow_state.json`
- `workflow/runs/{run_id}/workflow_log.md`
- `workflow/runs/index.jsonl`

The runner preserves existing drafts by default. Use `--overwrite-draft` only when the user wants to regenerate the draft workspace.

Add candidate generation to the scene loop:

```powershell
python -m literary_engineering_workbench run-workflow "<work-dir>" --mode scene-loop --generate-candidate
```

This writes `candidate_task`, `expected_candidate`, `expected_candidate_manifest`, and `prompt_manifest` in workflow state. The platform agent must write the expected candidate before promotion can proceed.

Add schema-gated agent review nodes:

```powershell
python -m literary_engineering_workbench run-workflow "<work-dir>" --mode scene-loop --agent-review
```

Generate platform-agent task sidecars throughout the scene loop:

```powershell
python -m literary_engineering_workbench run-workflow "<work-dir>" --mode scene-loop --agent-tasks --generate-candidate
```

This records `simulation_agent_tasks`, `branch_agent_tasks`, `scene_composition_agent_tasks`, `candidate_task`, and `state_patch_agent_tasks` in `workflow_state.json` when the corresponding artifacts exist.

Promote the generated or latest candidate into the review lane:

```powershell
python -m literary_engineering_workbench run-workflow "<work-dir>" --mode scene-loop --generate-candidate --promote-candidate
```

If the platform-agent candidate has not been written yet, promotion is deferred instead of invoking a local provider.

Stable run id and linked retry:

```powershell
python -m literary_engineering_workbench run-workflow "<work-dir>" --mode scene-loop --run-id scene-0001-pass-1
python -m literary_engineering_workbench run-workflow "<work-dir>" --mode scene-loop --run-id scene-0001-pass-2 --resume-run-id scene-0001-pass-1
```

## Approval Summary

```powershell
python -m literary_engineering_workbench approval-summary "<work-dir>"
```

Reads `workflow/approvals/index.jsonl` and writes `workflow/approvals/approval_summary.md`. `revise` and `reject` decisions create follow-up tasks under `workflow/tasks/`.

## LangGraph Adapter

Install optional orchestration dependencies before using LangGraph:

```powershell
python -m pip install fastapi uvicorn pydantic langgraph
```

For the development repo:

```powershell
$env:PYTHONPATH = "<repo-root>\\src"
python -m literary_engineering_workbench run-langgraph "<work-dir>" --scene scenes/scene_0001.yaml --chapter-id chapter_0001 --thread-id demo-thread-001
```

For an installed skill copy:

```powershell
$env:PYTHONPATH = "<skill-root>\\scripts"
python -m literary_engineering_workbench run-langgraph "<work-dir>" --scene scenes/scene_0001.yaml --chapter-id chapter_0001 --thread-id demo-thread-001
```

The LangGraph adapter wraps the same file-backed runner. Current graph:

- `scene-loop`
- `chapter-publish`

Status is merged by severity: `failed > blocked > completed_with_skips > completed`.

## Dify / HTTP Backend

Install optional runtime packages, then start the local API:

```powershell
python -m pip install fastapi uvicorn pydantic langgraph
$env:PYTHONPATH = "<skill-root>\\scripts"
python -m literary_engineering_workbench serve-api --host 127.0.0.1 --port 8765 --allowed-root "<parent-workspace>" --api-token "your-token"
```

Primary endpoints:

- `GET /health`
- `GET /`
- `GET /config`
- `POST /config`
- `POST /assistant/chat`
- `POST /director/chat`
- `POST /workflow/run`
- `GET /workflow/runs/{run_id}?project_root=<work-dir>`
- `GET /workflow/artifact?project_root=<work-dir>&path=<relative-artifact-path>`
- `POST /workflow/approve`

For a platform-agent or creative-director UX, call `/director/chat` with `project_root`, `message`, `provider`, `auto_execute`, and optional `agent_tasks`. The director can run delegated workflows and, when `agent_tasks=true`, those workflows write platform-agent task sidecars for later Codex/Claude inspection.

For specialist/debug workflows, call `/workflow/run` directly. Its request body accepts `agent_review=true` for schema-gated model reviews and `agent_tasks=true` for sidecar task directives. Display the returned log or state, collect `approve / revise / reject` with Human Input, then call `/workflow/approve`. Do not let Dify edit canon files directly.

The same service hosts a local front-end console at:

```text
http://127.0.0.1:8765/
```

Use it for global config, explicit local API key setup, project summary, workflow execution, and creative-director chat.

If `--api-token` is enabled, send either:

```text
Authorization: Bearer your-token
```

or:

```text
X-LEW-API-Token: your-token
```

## Dify Workflow DSL Starter

Generate an import-safe workflow YAML starter:

```powershell
$env:PYTHONPATH = "<skill-root>\\scripts"
python -m literary_engineering_workbench dify-dsl --api-base "http://127.0.0.1:8765"
```

This writes:

```text
docs/integrations/dify/literary-workbench-reviewer.workflow.yml
```

If generating inside an installed skill directory is not desired, pass `--out` to write into a project folder:

```powershell
python -m literary_engineering_workbench dify-dsl --out "<work-dir>\\prompts\\dify\\literary-workbench-reviewer.workflow.yml"
```

The DSL starter uses the workbench HTTP contract:

- `POST /director/chat`
- `GET /workflow/artifact`

The default DSL declares version `0.6.0` and intentionally keeps only Start, HTTP Request, and End nodes because Dify Human Input / classifier node fields vary by version. It exposes `auto_execute` and `agent_tasks` as Start variables; set `agent_tasks=true` when you want delegated workflows to produce platform-agent sidecars. If your Dify instance requires a newer declared DSL version, add:

```powershell
python -m literary_engineering_workbench dify-dsl --dsl-version "0.7.0"
```

After import, add Human Input and a final HTTP Request node in Dify UI to call `POST /workflow/approve`.

If the target Dify version rejects an internal node field, first import a reduced Start -> Run workflow -> End version, then rebuild the remaining HTTP Request and Human Input nodes in Dify UI.

## Orchestration Blueprint

```powershell
python -m literary_engineering_workbench orchestration-plan "<work-dir>"
```

Use this before implementing LangGraph nodes, Dify workflows, or knowledge-base adapters.
