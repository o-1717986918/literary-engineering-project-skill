---
name: literary-engineering-project-skill
description: Project-type skill for Codex, Claude, and similar tool-layer agents to manage long-form fictional literature projects as engineering workspaces. Use when the agent needs to act as project director, creative director, editor, continuity auditor, style engineer, scene planner, prose generator, reviewer, or release manager for novels, screenplays, pseudo-record texts, web fiction, short-drama scripts, or long-video prompt projects; especially when work involves AGENTS.md/agentread.yaml project onboarding, canon/character/plot/style file maintenance, author style projects, mounted Style Skills, candidate asset review/promotion, hidden character background causality, scene simulation, branch planning, context packets, prompt packs, chapter exports, or optional local CLI tooling. The tool-layer platform provides the LLM, subagents, planning, and conversation; this skill provides the operating manual, file contracts, and deterministic helper commands.
---

# Literary Engineering Project Skill

Use this skill to let Codex, Claude, or another capable tool-layer agent manage a long-form fictional work as an engineering project. The platform agent is the project director. This repository is the operating manual and optional toolbox.

## Core Shift

- Treat Codex/Claude as the creative director, project manager, LLM provider, and subagent orchestrator.
- Treat this skill as project structure, contracts, procedures, prompts, schemas, and helper CLI.
- Do not assume the local `director-chat` command is the main interface. It is an optional experimental/local helper.
- Prefer direct tool-layer reasoning, file edits, review passes, and subagent delegation when the platform supports them.
- Use the local CLI only when deterministic project operations are useful: initialization, indexing, context packet generation, style compilation, lint, audit, export, and packaging.

## First Move

1. Identify the workspace type:
   - **Skill root**: contains this `SKILL.md`, `AGENTS.md`, `agentread.yaml`, `references/`, `templates/`, `schemas/`, and either development `src/` or installed-package `scripts/` helper code.
   - **Work project**: contains `project.yaml`, `canon/`, `characters/`, `plot/`, `style/`, `scenes/`, `drafts/`, `reviews/`, `memory/`.
   - **Style library**: contains `authors/{author_id}/`, `works/`, `profiles/`, `style_skills/`.
2. Read `AGENTS.md` and `agentread.yaml` before changing a work project or this skill.
3. Select the smallest task route in `agentread.yaml`.
4. Load only the needed reference file:
   - `references/project-director-playbook.md` for project-director behavior and user interaction.
   - `references/artifact-contracts.md` before changing file layouts or writing project artifacts.
   - `references/workflows.md` for CLI command recipes.
   - `references/orchestration.md` for LangGraph, Dify, subagents, or external workflow design.

## Operating Rules

- Project state is source code; generated prose is an artifact.
- Canon, character facts, and approved plot decisions are hard constraints.
- Retrieval results, roleplay output, model summaries, and style matches are evidence, not canon.
- New characters, world rules, locations, organizations, relationship graphs, outlines, and major plot turns start as candidates.
- Promote candidates only after review and explicit user approval unless the user clearly asks for an internal experimental branch.
- Preserve `background_story` as hidden behavioral causality. It should shape choices, avoidance, speech, misreadings, and relationship pressure; do not dump it as exposition unless the scene intentionally reveals it.
- Mounted Style Skills have highest priority for expression-level choices: narrative distance, syntax rhythm, imagery, sensory balance, dialogue density, and psychological presentation. They never override canon, character facts, plot causality, safety/legal boundaries, or explicit user constraints.
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
- Style learning: use author-as-project, work-as-subproject, and Style Skill output. Read `references/project-director-playbook.md` and `references/workflows.md`.
- Scene work: build context, simulate character behavior, branch plot options, compose a scene packet, generate candidate prose, review, then propose state patches.
- Review/audit: run canon, character, plot, style, and release checks before treating text as ready.
- Export/release: confirm chapter readiness, longform audit status, and approval records before packaging or release.

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

Use `--provider dry-run` only for offline deterministic checks. In normal Codex/Claude use, the platform's own model and subagents should do creative reasoning and generation unless the user explicitly wants the local provider path.

## Validation

After modifying this skill or helper code:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

For an installed package without `src/`, use `$env:PYTHONPATH = "scripts"` and run a CLI smoke check such as `python -m literary_engineering_workbench --help`. For pure instruction/reference edits, also validate `SKILL.md` frontmatter with the skill validation script when available.
