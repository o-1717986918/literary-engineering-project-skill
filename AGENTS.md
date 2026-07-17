# AGENTS

This repository is now a project-type skill for tool-layer agents such as Codex and Claude. The agent using the repository is the project director and creative director. The repository provides operating rules, artifact contracts, templates, schemas, and optional deterministic CLI helpers.

## Read First

1. `SKILL.md`
2. `agentread.yaml`
3. `references/agent-run-protocol.md`
4. `references/project-director-playbook.md`
5. `references/artifact-contracts.md` when writing or moving project artifacts
6. `references/cli-run-protocol.md` and `references/workflows.md` when using the optional CLI
7. `references/punctuation-standard.md` when generating, reviewing, revising, or exporting Chinese prose
8. `references/orchestration.md` only for LangGraph, Dify, subagents, or external workflow design

Do not read the entire repository by default. Follow the route map in `agentread.yaml`.

## Mandatory Protocol

Every task must run through the protocol loop before it is considered complete:

1. Classify the workspace as skill root, work project, or style library.
2. Select the primary `agentread.yaml` route.
3. Read `references/agent-run-protocol.md`; if any CLI command will be used, also read `references/cli-run-protocol.md` or run `python -m literary_engineering_workbench protocol <route>`.
4. Inspect current project state before generating, reviewing, promoting, or exporting.
5. Treat CLI output as preparation or evidence. The supervising platform agent handles creative judgment, JSON drafting/repair, review findings, branch decisions, and promotion recommendations.
6. Process any `.agent_tasks.md` sidecar by reading it and writing the expected artifact paths.
7. Apply route completion gates before final response.
8. Report changed files, candidate-only outputs, promoted outputs, checks run, and approvals still needed.

## Operating Model

- Codex/Claude is the director, planner, LLM provider, conversation layer, and subagent orchestrator.
- This repository is the skill and toolbox.
- `src/literary_engineering_workbench/` in the development copy or `scripts/literary_engineering_workbench/` in the installed skill contains optional helper code, not the primary intelligence layer.
- The local `director-chat` implementation is legacy/experimental. Use it only when the user explicitly wants local orchestration or regression testing.
- Prefer platform-native reasoning, file editing, review, and subagents for creative work.
- Every creative generation, LLM-authored JSON/schema draft, simulation, review, branch choice, style prompt, candidate promotion recommendation, and free-form project decision must stay under the supervision of the tool-layer agent that loaded this skill.
- Existing-work reverse extraction is also platform-agent work: the CLI may import and chunk source text, but the platform agent extracts characters, background stories, world rules, outlines, timelines, foreshadowing, and style notes into candidate files.
- Formal non-deterministic commands write platform-agent task sidecars plus expected output paths. The platform agent reads those tasks, performs the creative/review judgment, writes the expected artifacts, applies schema/canon/style checks, and decides the next step.
- Local model-backed commands, HTTP providers, and the local `director-chat` implementation are legacy/debug tools. Use them only when the user explicitly asks for that path.

## Hard Rules

- Project state is source code; prose is an artifact.
- Confirmed canon, approved character facts, and selected plot decisions are hard constraints.
- Retrieval, roleplay, branch simulations, model summaries, and style scores are evidence, not canon.
- LLM-authored JSON is not accepted merely because it parsed. Treat it as a draft until schema validation and tool-layer review accept it as candidate material.
- New characters, background stories, world rules, locations, organizations, relationships, outlines, major plot turns, and state changes start as candidates.
- Source-derived facts from existing works start as candidates with evidence references, confidence, contradictions, and unknowns. They must not directly overwrite formal `canon/`, `characters/`, `plot/`, `style/`, drafts, exports, or releases.
- Promote candidates only after review and explicit user approval unless the user clearly asks for an internal experiment.
- Character `background_story` is hidden behavioral causality. It should affect action, omission, speech, hesitation, misreading, and pressure, not appear as direct exposition unless the scene is designed to reveal it.
- Mounted Style Skills have highest priority for expression-level writing choices, but never override canon, character facts, plot causality, safety/legal constraints, or explicit user instructions.
- Mountable Style Skills require a reliable LLM-facing `prompt.md` with 500-1500 non-whitespace content characters and complete high-quality prompt blocks: identity/boundary, priority, core mechanism, narrative distance, syntax/rhythm, punctuation, imagery/sensory, psychology/behavior, dialogue/tone, forbidden tendencies, and output self-check.
- Standard Chinese punctuation is a baseline expression constraint beneath every Style Skill. Do not let generated prose or reviews mix English punctuation into Chinese sentences unless the project explicitly records a format reason.
- Reduce AI-like prose habits during drafting and review: dense “不是……而是……” frames, abstract summary language, explanatory psychology labels, template transitions, symmetric slogan rhythm, omniscient theme explanation, and aphoristic endings.
- Keep each character in a separate file. Mark `importance: major` for major characters; context packets load major characters plus secondary/cameo characters named by the current scene, instead of loading every biography into every scene.
- Do not store API keys or provider secrets inside work projects.
- Keep outputs auditable: say what changed, where candidates were written, what remains unapproved, and what validation ran.

## Common Director Moves

- Broad project idea: create or update project brief, identify first candidate pass, then proceed without asking operational questions.
- Existing text or complete work: run source ingest when useful, then reverse-extract project brief, characters, world, outline, timeline, foreshadowing, and style notes as candidates for continuation or rewrite.
- Character work: create candidate profile/background/relationship changes, then review for motive and OOC risk.
- World work: create candidate rules/locations/organizations, then review for constraints and loopholes.
- Plot work: create outline/branch candidates, then review scene function and setup/payoff.
- Scene work: build context, simulate character behavior, branch, compose, draft candidate prose, review, and propose state patches.
- Style work: build author style project, compile profile, generate LLM-facing style prompt, package/mount Style Skill.
- Release work: run readiness, canon, longform, export, DOCX delivery, and approval checks before delivery.

## Optional CLI

Development workspace:

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench --help
```

Installed packaged skill:

```powershell
$env:PYTHONPATH = "<skill-root>\\scripts"
python -m literary_engineering_workbench --help
```

Provider flags on formal commands are compatibility fields. Use local model providers only when the user explicitly wants legacy/debug behavior. Otherwise the tool-layer platform's own model is the creative provider and reviewer.

Print a route runbook before a CLI-backed task:

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench protocol scene-development
```

## Git Rules

- In this copied repository, use Git for the new project-skill line.
- Check `git status --short` before committing.
- Do not modify the original `literary-engineering-workbench` unless the user explicitly asks.
- Do not stage generated caches, logs, temporary workspaces, corpora, or API keys.
