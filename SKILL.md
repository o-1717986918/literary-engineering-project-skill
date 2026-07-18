---
name: literary-engineering-project-skill
description: Project-type skill for Codex, Claude, and similar tool-layer agents to manage long-form fictional literature projects as engineering workspaces. Use when the agent needs to act as project director, creative director, editor, continuity auditor, style engineer, source-text analyst, longform word-budget planner, scene planner, prose generator, reviewer, or release manager for novels, screenplays, pseudo-record texts, web fiction, short-drama scripts, or long-video prompt projects; especially when work involves AGENTS.md/agentread.yaml project onboarding, canon/character/plot/style file maintenance, importing existing works for continuation or rewrite, target length planning, author style projects, mounted Style Skills, candidate asset review/promotion, hidden character background causality, scene simulation, branch planning, context packets, prompt packs, chapter exports, or formal route CLI sidecars. The tool-layer platform provides the LLM, subagents, planning, and conversation; this skill provides the operating manual, file contracts, and deterministic helper commands.
---

# Literary Engineering Project Skill

Use this skill to let Codex, Claude, or another capable tool-layer agent manage a long-form fictional work as an engineering project. The platform agent is the project director. This repository is the operating manual, artifact contract, and formal-route toolbox.

## Core Shift

- Treat Codex/Claude as the creative director, project manager, LLM provider, and subagent orchestrator.
- Treat this skill as project structure, contracts, procedures, prompts, schemas, and helper CLI.
- Do not assume the local `director-chat` command is the main interface. It is an optional experimental/local helper.
- Prefer direct tool-layer reasoning, file edits, review passes, and subagent delegation when the platform supports them.
- Treat the local CLI as optional only for informal brainstorming or exploratory notes. Formal routes that generate, review, promote, or export project artifacts must use the route CLI sidecar/provenance chain where the skill provides one, or record an attempted-command failure and a clearly marked CLI-equivalent workaround.

## Formal Route CLI Clarification

"CLI optional" means a user may discuss ideas, ask for analysis, or request exploratory snippets without running local tools. It does not mean formal project routes can be hand-written around the CLI.

For formal `scene-development`, `style-engineering`, `longform-planning`, `source-ingest`, `review-and-audit`, and `export-and-release`, run the route protocol and the documented deterministic commands when they are available. Manual files with the same names as CLI outputs are exploratory/debug-only unless the agent first tried the command, recorded the exact failure, and marked the replacement artifact as a CLI-equivalent workaround for route audit and human review.

Formal candidates must carry provenance. A scene candidate cannot be promoted or exported merely because `drafts/candidates/*.md` exists; it must also have prompt manifest, `.agent_tasks.md`, platform-agent candidate manifest, exact-candidate review, Style Lint, and route-audit gates.

## Tool-Layer Participation Gate

The tool-layer agent that loaded this skill must lead every non-deterministic creative step. Formal workflow commands write platform-agent task sidecars and expected artifact paths; the platform agent fills those artifacts. Local model-backed commands and HTTP providers are legacy/debug helpers, not formal creative authorities.

Require tool-layer planning, prompting, inspection, and acceptance for:

- prose, project briefs, characters, hidden background stories, world rules, outlines, scenes, revisions, and style prompts;
- source-text reverse extraction for continuation, rewrite, adaptation, or analysis;
- longform target-length planning, budgeted outline expansion, and narrative-inventory sufficiency judgments;
- LLM-authored JSON, schema repair, patch plans, committee reports, review findings, and candidate metadata;
- roleplay, branch, scene, consequence, and character-state simulations;
- free routing decisions, project-director decisions, candidate promotion recommendations, release choices, and any user-facing creative judgment.

When using formal local commands such as `source-ingest`, `extract-existing-work`, `word-budget`, `longform-budget`, `agent-task-status`, `route-audit`, `agent-create-*`, `asset-create`, `agent-build-json`, `agent-review-scene`, `agent-canon-review`, `review-candidate-asset`, `agent-plan-patch`, `agent-style-prompt`, `agent-committee`, `style-prompt`, `style-prompt-eval`, `style-lab-compile`, `simulate-scene`, `branch-simulate`, `compose-scene`, `generate-scene`, `revise-scene`, `state-evolve`, or `run-workflow`, expect `.agent_tasks.md` files plus expected JSON/Markdown paths. The platform agent should read the task, perform the creative or review judgment, write the expected artifacts, then decide whether to revise, keep as candidate, ask the user, or promote after approval.

Use `agent-run`, `agent-repair`, provider-backed Python functions, `/director/chat`, or `director-chat` only for explicit legacy regression, local demos, or debugging. Do not route formal creative generation, JSON creation, scene/canon review, style-prompt creation, or second-level project decisions through local dry-run, HTTP chat, or an external agent service.

Never let generated JSON, simulation output, local-director output, model scores, or a CLI recommendation become canon, selected plot direction, approved style policy, final prose, or release authority by itself.

## Execution Discipline Gate

- Do not declare a documented CLI step, sidecar step, or platform-agent task impossible until you have actually probed it: run `--help`, run `protocol <route>`, or attempt the smallest safe command. If it fails, record the exact command, error, and next workaround.
- A command that emits `.agent_tasks.md` has not completed the step. It has handed executable work to the platform agent that loaded this skill. Read the sidecar immediately when possible, write the expected Markdown/JSON/prose artifacts, inspect them, then continue the route.
- `agent-review-scene` is not an external model dependency by itself. It prepares the scene-review task, deterministic `Style Lint (auto-detected)` evidence, and expected `scene_review.v1` outputs; the supervising platform agent performs the review, handles lint findings explicitly, and writes the files.
- If a formal command such as `promote-candidate`, `chapter-workspace`, or `export-package` blocks on missing review/readiness gates, do not bypass it with an ad hoc script, debug flag, or unreview instruction. Resolve the gate, run `revise-scene`, run `agent-task-status` / `route-audit`, and complete the missing review/approval.

## Formal Host Debug-Waiver Ban

- A Skill host using this skill for real project work must not use debug or bypass parameters, including `--allow-unreviewed`, `--allow-review-notes`, `--include-blocked`, `--allow-unapproved`, `--allow-unresolved`, `--allow-missing-composition`, `--allow-unselected-composition`, `--allow-recommended-branch`, and `--allow-missing-branch`.
- User wording such as “先跳过 review”, “unreview”, “快速放行”, “内部实验”, or “直接导出” does not authorize the host to bypass formal review gates. The correct response is to complete the review, revision, approval, or route audit.
- These flags remain in the CLI only for maintainers running regression tests or debugging the skill implementation inside this repository. They are not available as normal operating instructions for Codex/Claude when acting as a project Skill host.
- `route-audit` should be treated as authoritative evidence: if it reports debug/waiver flags in project manifests, the formal route is blocked until the artifact is regenerated through the reviewed path.

## Main Agent Prose Authority Gate

- Creative body text must be written by the main platform agent that is directly interacting with the user and holding the project-level intent. This includes prose candidates, revised prose, formal scene drafts, chapter bodies, screenplay scenes, pseudo-record entries, and final deliverable text.
- Subagents may assist only with relatively mechanical or bounded work: retrieval summaries, source evidence extraction, continuity tables, schema validation, punctuation/style issue lists, canon risk checklists, word-count inventories, branch option comparison, and review notes.
- Subagents must not ghostwrite, rewrite, expand, polish, or finalize body text. If a subagent returns draft-like prose, the main agent must treat it as reference material only, not paste it as the candidate or final body.
- The main agent may use subagent findings to inform writing, but it must personally compose the final candidate text and accept responsibility for style, character logic, canon, and review readiness.

## Batch Scene Loop Coverage Gate

- A scene-development loop is per scene. Running the chain once for `scene_0075` does not cover `scene_0076` through `scene_0099`.
- Before bulk drafting, identify the complete scene set from `scenes/*.yaml`, `plot/chapters/`, or the word-budget scene inventory, then track each scene through context, roleplay, branch selection, composition, prose candidate, exact-candidate AgentReview, `promote-candidate`, static/Agent review notes, and `state-evolve`.
- For 100000+ word or multi-volume targets, run or emulate `word-budget` before bulk scene work. If `word_budget.json` reports `needs_expansion`, the platform agent must complete the budgeted outline, scene-inventory expansion, and reviews before treating prose generation as formally ready.
- Run `route-audit --route scene-development` after a batch and before chapter/export. It must show each scene has a prose candidate, passing exact-candidate `scene_review.v1`, Style Lint clean/notes-only, promotion manifest, promoted draft, static `review-scene` clean pass, and state patch. If a revision candidate is used, it must also show a clean anti-evasion revision manifest. Missing gates are work items, not optional notes.
- Run `longform-audit`, `agent-task-status`, and `route-audit --route export-and-release` before final delivery. Custom export scripts do not satisfy official readiness gates.

## First Move

1. Identify the workspace type:
   - **Skill root**: contains this `SKILL.md`, `AGENTS.md`, `agentread.yaml`, `references/`, `templates/`, `schemas/`, and either development `src/` or installed-package `scripts/` helper code.
   - **Work project**: contains `project.yaml`, `canon/`, `characters/`, `plot/`, `style/`, `sources/`, `scenes/`, `drafts/`, `reviews/`, `memory/`.
   - **Style library**: contains `authors/{author_id}/`, `works/`, `profiles/`, `style_skills/`.
2. Read `AGENTS.md` and `agentread.yaml` before changing a work project or this skill.
3. Select the smallest task route in `agentread.yaml`.
4. Apply the mandatory run protocol before doing work:
   - Read `references/agent-run-protocol.md` for every project task.
   - Read `references/cli-run-protocol.md` before any formal route that has deterministic CLI sidecars or provenance gates.
   - If using the CLI, run `python -m literary_engineering_workbench protocol <route>` first and follow its preflight, handoff points, completion gates, and forbidden shortcuts.
5. Load only the needed reference file:
   - `references/project-director-playbook.md` for project-director behavior and user interaction.
   - `references/artifact-contracts.md` before changing file layouts or writing project artifacts.
   - `references/workflows.md` for CLI command recipes.
   - `references/orchestration.md` for LangGraph, Dify, subagents, or external workflow design.
   - `references/punctuation-standard.md` before generating, reviewing, revising, or exporting Chinese prose.
   - `references/file-format-export.md` before exporting final work artifacts to DOCX or other concrete delivery formats.

## Mandatory Run Protocol

Every task must follow the loop in `references/agent-run-protocol.md`: classify workspace, choose a route, read route references, record a reading receipt, inspect project state, plan, execute deterministic helpers only as helpers, let the platform agent handle creative judgment, process `.agent_tasks.md`, validate outputs, decide candidate/revision/promotion status, and finish with an audit summary.

Every formal CLI-backed route must follow `references/cli-run-protocol.md`. The CLI is never the creative authority, but its sidecars and manifests are the formal provenance layer. A command that writes `.agent_tasks.md` has prepared work for the platform agent; it has not completed the creative or review step. Use `agent-task-status` and route-specific `route-audit` when you need a single dashboard of pending sidecars, missing expected artifacts, and incomplete route gates.

Before final response, explicitly account for the relevant completion gates: route selected, references read, reading receipt, project state inspected, task sidecars handled or listed as pending, schema/canon/character/style/punctuation/release checks applied when relevant, and approval boundaries recorded.

## Operating Rules

- Project state is source code; generated prose is an artifact.
- Canon, character facts, and approved plot decisions are hard constraints.
- Retrieval results, roleplay output, model summaries, and style matches are evidence, not canon.
- Source-derived extraction is evidence, not canon. Existing-work imports must write extracted characters, world rules, outlines, timelines, foreshadowing, and style notes to candidate/review locations before any promotion.
- Longform word budgets are generation constraints, not final plot. For 100000+ word or multi-volume targets, build or inspect `plot/word_budget/word_budget.json`, have the platform agent handle the budget expansion and scene-inventory sidecars, and do not bulk-generate while budget status is `needs_expansion` or chapter/scene inventory shortfalls are unresolved.
- Scene loop evidence is per-scene evidence. A batch is incomplete if any scene lacks context, RP, branch selection, composition, candidate, exact-candidate AgentReview, Style Lint clean/notes-only, promotion, promoted draft, static review clean pass, or state patch; `route-audit --route scene-development` is the default ledger for this.
- Draft length, chapter progress, longform progress, and export manifest `draft_chars` must use cleaned deliverable prose only. Do not count workflow notes, review text, canon explanations, prompt manifests, `[AGENT_TASK: ...]`, status/writeback candidates, scene IDs, or file paths as prose length.
- Formal scene generation must not start from `generate-scene`, manual drafting, or provider-backed helpers until the scene has a CLI-generated context packet, `simulate-scene --agent` roleplay simulation with platform-agent reading receipt and CLI provenance, `branch-simulate --agent` branch manifest with CLI provenance, formal `branch_selection.md`, and `compose-scene --agent-tasks` composition with `selection_source=selection`, `ready_for_generation=true`, and `formal_cli_provenance.created_by=compose-scene`. Manual file creation before generation is exploratory/debug-only and cannot satisfy formal route gates unless an attempted CLI failure and CLI-equivalent workaround are recorded.
- LLM-authored JSON is a draft artifact until the tool-layer agent validates schema, checks project constraints, and accepts it as a candidate or asks for approval.
- New characters, world rules, locations, organizations, relationship graphs, outlines, and major plot turns start as candidates.
- Promote candidates only after review and explicit user approval. Do not use debug or unreview instructions to skip review.
- Scene prose candidates must pass a candidate-specific platform Agent scene review before `promote-candidate`: the review JSON must cite the exact candidate path in `source_paths` or `candidate`, satisfy `scene_review.v1`, and have a clean `conclusion=pass`. `pass_with_notes`, warnings, revision actions, style deviations, stale reviews, or missing candidate source paths block formal promotion until revised and re-reviewed.
- Preserve `background_story` as hidden behavioral causality. It should shape choices, avoidance, speech, misreadings, and relationship pressure; do not dump it as exposition unless the scene intentionally reveals it.
- Mounted Style Skills have highest priority for expression-level choices: narrative distance, syntax rhythm, imagery, sensory balance, dialogue density, and psychological presentation. They never override canon, character facts, plot causality, safety/legal boundaries, or explicit user constraints.
- When a Style Skill is mounted, formal platform scene review must include `style_adherence` in `reviews/agent/{scene_id}_scene_review.json`. Clean chapter readiness and formal export require `style_adherence.status=pass`; `pass_with_notes`, missing fields, `not_applicable`, or `revise_required` are blocking until `revise-scene` and re-review resolve them.
- A mountable Style Skill must contain a reliable LLM-facing `prompt.md`: detailed but executable, 500-2500 non-whitespace content characters, with explicit identity/boundary, priority, core mechanism, narrative distance, syntax/rhythm, punctuation, imagery/sensory, psychology/behavior, dialogue/tone, forbidden tendencies, and output self-check blocks. Shorter, longer, or structurally vague prompts must be revised before default mounting.
- Standard Chinese punctuation is a baseline expression constraint under every Style Skill: Chinese prose should use full-width punctuation, `……` for ellipsis, `——` for dashes, horizontal Chinese dialogue quotes `“”` with inner quotes `‘’`, and no unexplained English punctuation or mixed corner/vertical quote style in Chinese sentences.
- Generated prose must pass the Style Lint Gate before promotion, chapter readiness, or formal export. Mechanical “不是……而是……” contrast frames and dash variants such as “不是……——是……” are core banned frames and always blocking; same-function evasive contrast frames such as “并不是……只是……”“倒不是……只是……”“看似……其实……”“表面上……实则……” are also blocking. Other medium-or-higher AI trace findings are blocking; low findings are notes-only and require platform Agent review or a retention reason. Extract any intended correction, irony, or information-reversal function into actions, fact order, information gaps, or direct statements. Risk phrase families such as organ-rotation, generic placeholders, simile dependency, abstract summary language, explanatory psychology labels, template transitions, scenery syncing, symmetric slogan rhythm, omniscient theme explanation, and aphoristic endings use an approximately 2% narrative-unit density gate: isolated hits are review signals, dense hits require revision. Scripts may flag or safely normalize typography, but must not batch-delete negation or perform semantic prose cleanup.
- Revision must pass the anti-evasion protocol. When review notes or Style Lint identify a contrast/AI-trace problem, the writing agent must not replace it with another explicit contrast. If any transition is retained, the revision report must provide burden of proof: original issue, revised sentence, whether it still contains a transition, whether it is a disguised replacement, why action/fact order/information gap cannot replace it, critical counterargument, and final conclusion. Weak explanations such as “增强节奏” or “体现复杂心理” are not sufficient.
- `pass_with_notes` is not a silent pass. The writing agent must apply listed `revision_actions` / warnings / style notes as local edits, usually through `revise-scene`, then re-review before promotion, chapter readiness, export, or writeback.
- Final delivery artifacts must hide engineering markers such as `scene_0001`, `chapter_0001`, scene file paths, context packet paths, canon notes, workflow traces, review state, and writeback candidates. Keep provenance in manifests and workbench files.
- Formal chapter export must rebuild or verify the chapter workspace immediately before packaging. If any scene is non-ready, stale, missing flow gates, missing clean AgentReview, or still carrying `pass_with_notes` notes, block export and complete the missing review/revision path.
- Store each character in a separate `characters/{character_id}.yaml`. Mark major characters with `importance: major`; secondary/cameo characters are loaded into scene context only when listed in `participants`, `referenced_characters`, or `character_refs`.
- Exact author-style imitation is appropriate only for public-domain or authorized corpora. For other authors, abstract higher-level craft features.
- Never store API keys or provider secrets in a work project. If local tools need keys, use the platform secret mechanism, environment variables, or local global config.
- Keep changes auditable: explain what files changed, what remains candidate-only, what needs user approval, and what tests/checks ran.

## Tool-Layer Director Pattern

When the user gives a broad creative direction, act directly as the director:

1. Restate the creative intent briefly.
2. Inspect project state through the relevant route.
3. Decide whether to plan, create candidate assets, revise drafts, audit continuity, learn style, or ask one high-level question.
4. Use subagents only for bounded support passes: character logic checks, worldbuilding consistency, plot inventory, style-risk lists, canon audit, source summaries, schema validation, and word-count tables. Do not use subagents to draft or revise body text.
5. Write outputs into the correct candidate/review/draft locations.
6. Return a concise user-facing summary plus next creative choices.

Do not expose raw schemas, internal file paths, or command chatter unless the user asks for implementation details.

## Common Routes

- New work project: read `references/project-director-playbook.md`, then initialize or propose a work project. Use the CLI `init` only when deterministic scaffolding is useful.
- Existing project direction: inspect `project.yaml`, recent `reviews/`, `workflow/`, `director/`, and relevant canon/character/plot files. Then act as director.
- Existing work import: read `references/workflows.md` and `references/artifact-contracts.md`, use `source-ingest` only to store source chunks and task sidecars, then let the platform agent reverse-extract candidate project files with evidence and confidence.
- Longform planning: read `docs/modules/longform-word-budget.md`, run or emulate `word-budget`, process the platform-agent expansion and scene-inventory sidecars, then keep budgeted outline and scene inventory as candidates until review and approval.
- Style learning: use author-as-project, work-as-subproject, and Style Skill output. Read `references/project-director-playbook.md` and `references/workflows.md`.
- Scene work: build context, simulate character behavior, branch plot options, compose a scene packet, generate candidate prose, review, revise through `revise-scene` when notes exist, then propose state patches.
- Review/audit: run canon, character, plot, style, and release checks before treating text as ready.
- Export/release: confirm chapter readiness, longform audit status, approval records, and requested delivery formats such as DOCX before packaging or release.

## Formal Route CLI

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

Provider flags on formal commands are compatibility fields. In normal Codex/Claude use, the platform's main agent is the creative writing provider and reviewer. Subagents may provide bounded mechanical support, but must not draft, rewrite, polish, or finalize body text. Use local provider paths only when the user explicitly asks for legacy/debug behavior.

Exploratory work may skip CLI. Formal project artifacts may not: run route commands, process sidecars, and preserve prompt/task/manifest provenance before promotion, chapter readiness, export, or release.

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
