# Workflows

These commands are optional deterministic helpers for a tool-layer director. In normal Codex/Claude use, the platform agent may reason, generate, review, and edit files directly by following `SKILL.md`, `AGENTS.md`, `agentread.yaml`, and `references/project-director-playbook.md`.

Use the CLI when repeatability matters: scaffolding, indexing, context packets, style compilation, schema/lint checks, audits, exports, and regression tests.

## Tool-Layer Supervision Rule

Any command that calls a model, writes creative material, drafts JSON, repairs schema output, simulates characters, scores branches, composes scenes, or chooses workflow steps is supervised by the tool-layer agent that loaded this skill. The command may create draft artifacts; it must not become the project director by itself.

Before running such a command, the platform agent should choose the task, prompt/context packet, constraints, and approval boundary. After running it, the platform agent must inspect raw and parsed artifacts, validate schema where relevant, check canon/character/style constraints, and decide whether to revise, keep as candidate, ask the user, or promote after approval.

This rule covers `agent-run`, `agent-create-*`, `asset-create`, `agent-build-json`, `agent-repair`, `agent-review-scene`, `agent-canon-review`, `review-candidate-asset`, `agent-plan-patch`, `agent-style-prompt`, `agent-committee`, `style-prompt`, `style-prompt-eval`, `style-lab-compile`, `simulate-scene`, `branch-simulate`, `compose-scene`, `generate-scene`, `state-evolve`, `run-workflow`, and `director-chat`.

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

Agent and model-backed commands default to `provider=auto`, which resolves to the configured real `http-chat` model. Use `--provider dry-run` only when you intentionally want an offline deterministic check.

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
- `scenes/`
- `drafts/`
- `reviews/`
- `memory/`
- `branches/`
- `exports/`
- `releases/`

Character files include `background_story`. Use it as an internal cause of behavior, not as direct exposition in final prose.

## Build A Demo Project

```powershell
python -m literary_engineering_workbench demo-project "<demo-work-dir>" --title "文学工程 Demo"
```

The demo uses original sample text and dry-run agents. It writes `reviews/agent/demo_walkthrough.md`, Agent scene/canon review artifacts, a committee review, and a workflow state.

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

Use `--provider dry-run` only for an offline style-prompt contract sample.

Evaluate a back-translated or outline-expanded candidate:

```powershell
python -m literary_engineering_workbench style-eval "<work-dir>\\style\\demo-author" --reference "<reference.txt>" --candidate "<candidate.txt>" --mode back-translation
```

Outputs JSON metrics and a markdown report under `evaluation_results/{mode}/`, including style similarity and copy-risk indicators.

Generate a back-translation / outline-expansion candidate through `style_prompt.md`, then evaluate prompt effectiveness:

```powershell
python -m literary_engineering_workbench style-prompt-eval "<work-dir>\\style\\demo-author" --reference "<reference.txt>" --input "<english-or-outline.txt>" --mode back-translation
```

## Style Lab

The local frontend exposes this as `文风学习`. Treat each author as a style project, each source work as a subproject, and the generated Style Skill as the mountable artifact for creative projects.

```powershell
python -m literary_engineering_workbench style-lab-author --name "作者名" --source-note "公版或授权语料"
python -m literary_engineering_workbench style-lab-work --author-id "<author-id>" --title "作品名"
python -m literary_engineering_workbench style-lab-import --author-id "<author-id>" --work-id "<work-id>" --file "<source.txt>"
python -m literary_engineering_workbench style-lab-compile --author-id "<author-id>" --provider dry-run
python -m literary_engineering_workbench style-lab-build-skill --author-id "<author-id>"
python -m literary_engineering_workbench style-lab-mount "<work-dir>" --style-id "<style-id>"
```

Mounted style skills are stored in the creative project under `style/mounted/{style_id}/` with `style/active_style_skill.json` as the active pointer. During generation, the mounted `prompt.md` is the highest-priority expression constraint, while canon, character facts, plot causality, safety boundaries, and explicit user constraints still take precedence.

## Generic Agent Run

Use `agent-run` when the task is an LLM-backed review, prompt generation, JSON draft, or future repair pass that needs auditable input/output but does not yet have a specialized command.

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

Generate project-seeding candidates:

```powershell
python -m literary_engineering_workbench agent-create-character "<work-dir>" --brief "谨慎的调查者" --target-id linzhou
python -m literary_engineering_workbench agent-create-world "<work-dir>" --brief "档案被垄断的城市"
python -m literary_engineering_workbench agent-create-outline "<work-dir>" --brief "调查旧档案的三幕结构"
python -m literary_engineering_workbench list-candidate-assets "<work-dir>"
```

Review and promote candidates:

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

`compose-scene` turns the selected or recommended branch into a creation packet under `drafts/compositions/{scene_id}_composition.md` and `.json`, including scene beats, subtext, dialogue intents, sensory palette, prose seed, revision targets, and writeback candidates. It is a pre-draft planning artifact, not final prose. The platform agent must inspect generated JSON before using it as a prompt pack or writeback source.

Use `compose-scene --agent-tasks` to write `drafts/compositions/{scene_id}_composition.agent_tasks.md`. Keep `[AGENT_TASK: ...]` out of the composition Markdown because it may be read into `generate-scene` prompt packs.

When character `background_story` is present, scene and branch work should convert it into choices, hesitation, avoidance, misreadings, tone, and relationship pressure. Do not turn it into an explanatory background paragraph unless the selected scene explicitly reveals the past.

`generate-scene` writes model candidates under `drafts/candidates/`; it does not overwrite `drafts/scenes/` and does not write canon. The platform agent reviews the candidate prose, prompt manifest, and constraints before promotion.

`promote-candidate` turns a selected model candidate into `drafts/scenes/{scene_id}.md` and writes `drafts/promotions/{scene_id}_promotion.md` / `.json`. It does not confirm canon and does not write characters.

For a real HTTP model endpoint:

```powershell
$env:DEEPSEEK_API_KEY = "your-api-key"
python -m literary_engineering_workbench config-show
python -m literary_engineering_workbench generate-scene "<work-dir>" --scene scenes/scene_0001.yaml --provider http-chat --rebuild-context
```

Each generation writes a prompt manifest next to the candidate: `drafts/candidates/{scene_id}-{provider}-{timestamp}.prompt.json`. It records system/user messages and source files, but not API keys.

Use `generate-scene --agent-tasks` to write `drafts/candidates/{scene_id}-{provider}-{timestamp}.agent_tasks.md`. The platform agent should read both the candidate and `.prompt.json`; the prompt manifest itself must remain pure audit data and must not contain `[AGENT_TASK: ...]`.

Review conclusions:

- `pass`: ready for chapter workspace.
- `pass_with_notes`: usable after human acceptance.
- `revise_required`: not exportable.
- `reject`: not exportable.

`state-evolve` builds a reviewable character-state patch under `characters/state_patches/` from a scene draft, generated candidate, or composition artifact. It does not modify `characters/*.yaml`; the platform agent must inspect the patch for hidden-background causality, canon risk, and unintended relationship drift. Major character state changes still require human confirmation before any later writeback.

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

- `ready`: draft exists and review passed.
- `needs_draft`: no usable body.
- `needs_review`: body exists but review missing.
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
```

Outputs:

- novel chapter draft;
- screenplay working draft;
- long-video prompt pack;
- `export_manifest.json`.

By default only `ready` scenes are exported. Use `--include-blocked` only for internal preview.

## Publish Chapter

```powershell
python -m literary_engineering_workbench publish-chapter "<work-dir>" --chapter-id chapter_0001 --approval-run-id "<approved-run-id>"
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
python -m literary_engineering_workbench run-workflow "<work-dir>" --mode scene-loop --generate-candidate --provider dry-run
```

Use `--provider http-chat` only when the global provider profile is configured and an API key is available from `LEW_MODEL_API_KEY`, the configured `api_key_env`, or saved profile `api_key`. The resulting candidate remains under the same platform-agent review and approval gates.

Add schema-gated agent review nodes:

```powershell
python -m literary_engineering_workbench run-workflow "<work-dir>" --mode scene-loop --agent-review
```

Generate platform-agent task sidecars throughout the scene loop:

```powershell
python -m literary_engineering_workbench run-workflow "<work-dir>" --mode scene-loop --agent-tasks --generate-candidate --provider dry-run
```

This records `simulation_agent_tasks`, `branch_agent_tasks`, `scene_composition_agent_tasks`, `candidate_agent_tasks`, and `state_patch_agent_tasks` in `workflow_state.json` when the corresponding artifacts exist.

Promote the generated or latest candidate into the review lane:

```powershell
python -m literary_engineering_workbench run-workflow "<work-dir>" --mode scene-loop --generate-candidate --promote-candidate --provider dry-run
```

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
