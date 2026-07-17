---
name: literary-engineering-project-skill
description: Project-type skill for Codex, Claude, and similar tool-layer agents to manage long-form fictional literature projects as engineering workspaces. Use when the agent needs to act as project director, creative director, editor, continuity auditor, style engineer, source-text analyst, scene planner, prose generator, reviewer, or release manager for novels, screenplays, pseudo-record texts, web fiction, short-drama scripts, or long-video prompt projects; especially when work involves AGENTS.md/agentread.yaml project onboarding, canon/character/plot/style file maintenance, importing existing works for continuation or rewrite, author style projects, mounted Style Skills, candidate asset review/promotion, hidden character background causality, scene simulation, branch planning, context packets, prompt packs, chapter exports, or optional local CLI tooling. The tool-layer platform provides the LLM, subagents, planning, and conversation; this skill provides the operating manual, file contracts, and deterministic helper commands.
---

# Literary Engineering Project Skill

Use this skill to let Codex, Claude, or another capable tool-layer agent manage a long-form fictional work as an engineering project. The platform agent is the project director. This repository is the operating manual and optional toolbox.

## Core Shift

- Treat Codex/Claude as the creative director, project manager, LLM provider, and subagent orchestrator.
- Treat this skill as project structure, contracts, procedures, prompts, schemas, and helper CLI.
- Do not assume the local `director-chat` command is the main interface. It is an optional experimental/local helper.
- Prefer direct tool-layer reasoning, file edits, review passes, and subagent delegation when the platform supports them.
- Use the local CLI only when deterministic project operations are useful: initialization, source import/chunking, indexing, context packet generation, style compilation, lint, audit, export, and packaging.

## Tool-Layer Participation Gate

The tool-layer agent that loaded this skill must lead every non-deterministic creative step. Formal workflow commands write platform-agent task sidecars and expected artifact paths; the platform agent fills those artifacts. Local model-backed commands and HTTP providers are legacy/debug helpers, not formal creative authorities.

Require tool-layer planning, prompting, inspection, and acceptance for:

- prose, project briefs, characters, hidden background stories, world rules, outlines, scenes, revisions, and style prompts;
- source-text reverse extraction for continuation, rewrite, adaptation, or analysis;
- LLM-authored JSON, schema repair, patch plans, committee reports, review findings, and candidate metadata;
- roleplay, branch, scene, consequence, and character-state simulations;
- free routing decisions, project-director decisions, candidate promotion recommendations, release choices, and any user-facing creative judgment.

When using formal local commands such as `source-ingest`, `extract-existing-work`, `agent-create-*`, `asset-create`, `agent-build-json`, `agent-review-scene`, `agent-canon-review`, `review-candidate-asset`, `agent-plan-patch`, `agent-style-prompt`, `agent-committee`, `style-prompt`, `style-prompt-eval`, `style-lab-compile`, `simulate-scene`, `branch-simulate`, `compose-scene`, `generate-scene`, `state-evolve`, or `run-workflow`, expect `.agent_tasks.md` files plus expected JSON/Markdown paths. The platform agent should read the task, perform the creative or review judgment, write the expected artifacts, then decide whether to revise, keep as candidate, ask the user, or promote after approval.

Use `agent-run`, `agent-repair`, provider-backed Python functions, `/director/chat`, or `director-chat` only for explicit legacy regression, local demos, or debugging. Do not route formal creative generation, JSON creation, scene/canon review, style-prompt creation, or second-level project decisions through local dry-run, HTTP chat, or an external agent service.

Never let generated JSON, simulation output, local-director output, model scores, or a CLI recommendation become canon, selected plot direction, approved style policy, final prose, or release authority by itself.

## First Move

1. Identify the workspace type:
   - **Skill root**: contains this `SKILL.md`, `AGENTS.md`, `agentread.yaml`, `references/`, `templates/`, `schemas/`, and either development `src/` or installed-package `scripts/` helper code.
   - **Work project**: contains `project.yaml`, `canon/`, `characters/`, `plot/`, `style/`, `sources/`, `scenes/`, `drafts/`, `reviews/`, `memory/`.
   - **Style library**: contains `authors/{author_id}/`, `works/`, `profiles/`, `style_skills/`.
2. Read `AGENTS.md` and `agentread.yaml` before changing a work project or this skill.
3. Select the smallest task route in `agentread.yaml`.
4. Apply the mandatory run protocol before doing work:
   - Read `references/agent-run-protocol.md` for every project task.
   - Read `references/cli-run-protocol.md` before using the optional CLI.
   - If using the CLI, run `python -m literary_engineering_workbench protocol <route>` first and follow its preflight, handoff points, completion gates, and forbidden shortcuts.
5. Load only the needed reference file:
   - `references/project-director-playbook.md` for project-director behavior and user interaction.
   - `references/artifact-contracts.md` before changing file layouts or writing project artifacts.
   - `references/workflows.md` for CLI command recipes.
   - `references/orchestration.md` for LangGraph, Dify, subagents, or external workflow design.
   - `references/punctuation-standard.md` before generating, reviewing, revising, or exporting Chinese prose.
   - `references/file-format-export.md` before exporting final work artifacts to DOCX or other concrete delivery formats.

## Mandatory Run Protocol

Every task must follow the loop in `references/agent-run-protocol.md`: classify workspace, choose a route, read route references, inspect project state, plan, execute deterministic helpers only as helpers, let the platform agent handle creative judgment, process `.agent_tasks.md`, validate outputs, decide candidate/revision/promotion status, and finish with an audit summary.

Every CLI-backed task must follow `references/cli-run-protocol.md`. The CLI is never the creative authority. A command that writes `.agent_tasks.md` has prepared work for the platform agent; it has not completed the creative or review step.

Before final response, explicitly account for the relevant completion gates: route selected, references read, project state inspected, task sidecars handled or listed as pending, schema/canon/character/style/punctuation/release checks applied when relevant, and approval boundaries recorded.

## Operating Rules

- Project state is source code; generated prose is an artifact.
- Canon, character facts, and approved plot decisions are hard constraints.
- Retrieval results, roleplay output, model summaries, and style matches are evidence, not canon.
- Source-derived extraction is evidence, not canon. Existing-work imports must write extracted characters, world rules, outlines, timelines, foreshadowing, and style notes to candidate/review locations before any promotion.
- LLM-authored JSON is a draft artifact until the tool-layer agent validates schema, checks project constraints, and accepts it as a candidate or asks for approval.
- New characters, world rules, locations, organizations, relationship graphs, outlines, and major plot turns start as candidates.
- Promote candidates only after review and explicit user approval unless the user clearly asks for an internal experimental branch.
- Preserve `background_story` as hidden behavioral causality. It should shape choices, avoidance, speech, misreadings, and relationship pressure; do not dump it as exposition unless the scene intentionally reveals it.
- Mounted Style Skills have highest priority for expression-level choices: narrative distance, syntax rhythm, imagery, sensory balance, dialogue density, and psychological presentation. They never override canon, character facts, plot causality, safety/legal boundaries, or explicit user constraints.
- A mountable Style Skill must contain a reliable LLM-facing `prompt.md`: detailed but executable, 500-1500 non-whitespace content characters, with explicit identity/boundary, priority, core mechanism, narrative distance, syntax/rhythm, punctuation, imagery/sensory, psychology/behavior, dialogue/tone, forbidden tendencies, and output self-check blocks. Shorter, longer, or structurally vague prompts must be revised before default mounting.
- Standard Chinese punctuation is a baseline expression constraint under every Style Skill: Chinese prose should use full-width punctuation, `……` for ellipsis, `——` for dashes, Chinese quotation marks, and no unexplained English punctuation mixed into Chinese sentences.
- Generated prose should reduce visible AI habits: avoid dense “不是……而是……” contrast frames, abstract summary language, explanatory psychology labels, template transitions, symmetric slogan rhythm, omniscient theme explanation, and aphoristic endings unless a scene intentionally needs them.
- Store each character in a separate `characters/{character_id}.yaml`. Mark major characters with `importance: major`; secondary/cameo characters are loaded into scene context only when listed in `participants`, `referenced_characters`, or `character_refs`.
- Exact author-style imitation is appropriate only for public-domain or authorized corpora. For other authors, abstract higher-level craft features.
- Never store API keys or provider secrets in a work project. If local tools need keys, use the platform secret mechanism, environment variables, or local global config.
- Keep changes auditable: explain what files changed, what remains candidate-only, what needs user approval, and what tests/checks ran.

## Tool-Layer Director Pattern

When the user gives a broad creative direction, act directly as the director:

1. Restate the creative intent briefly.
2. Inspect project state through the relevant route.
3. Decide whether to plan, create candidate assets, revise drafts, audit continuity, learn style, or ask one high-level question.
4. Use subagents when useful for independent passes: character logic, worldbuilding, plot, style, canon audit, prose revision.
5. Write outputs into the correct candidate/review/draft locations.
6. Return a concise user-facing summary plus next creative choices.

Do not expose raw schemas, internal file paths, or command chatter unless the user asks for implementation details.

## Common Routes

- New work project: read `references/project-director-playbook.md`, then initialize or propose a work project. Use the CLI `init` only when deterministic scaffolding is useful.
- Existing project direction: inspect `project.yaml`, recent `reviews/`, `workflow/`, `director/`, and relevant canon/character/plot files. Then act as director.
- Existing work import: read `references/workflows.md` and `references/artifact-contracts.md`, use `source-ingest` only to store source chunks and task sidecars, then let the platform agent reverse-extract candidate project files with evidence and confidence.
- Style learning: use author-as-project, work-as-subproject, and Style Skill output. Read `references/project-director-playbook.md` and `references/workflows.md`.
- Scene work: build context, simulate character behavior, branch plot options, compose a scene packet, generate candidate prose, review, then propose state patches.
- Review/audit: run canon, character, plot, style, and release checks before treating text as ready.
- Export/release: confirm chapter readiness, longform audit status, approval records, and requested delivery formats such as DOCX before packaging or release.

## Optional CLI

For this copied development workspace:

```powershell
$env:PYTHONPATH = "<skill-root>\\src"
python -m literary_engineering_workbench --help
```

For an installed packaged skill that uses a `scripts/` directory:

```powershell
$env:PYTHONPATH = "<skill-root>\\scripts"
python -m literary_engineering_workbench --help
```

Provider flags on formal commands are compatibility fields. In normal Codex/Claude use, the platform's own model and subagents should do creative reasoning, generation, JSON drafting, review, and second-level decisions. Use local provider paths only when the user explicitly asks for legacy/debug behavior.

Before using a route-specific command chain, print the runbook:

```powershell
$env:PYTHONPATH = "<skill-root>\\src"
python -m literary_engineering_workbench protocol scene-development
```

## Validation

After modifying this skill or helper code:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

For an installed package without `src/`, use `$env:PYTHONPATH = "scripts"` and run a CLI smoke check such as `python -m literary_engineering_workbench --help`. For pure instruction/reference edits, also validate `SKILL.md` frontmatter with the skill validation script when available.
