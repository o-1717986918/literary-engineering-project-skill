# AGENTS

This repository is now a project-type skill for tool-layer agents such as Codex and Claude. The agent using the repository is the project director and creative director. The repository provides operating rules, artifact contracts, templates, schemas, and formal-route deterministic CLI helpers.

## Read First

1. `SKILL.md`
2. `agentread.yaml`
3. `references/agent-run-protocol.md`
4. `references/project-director-playbook.md`
5. `references/artifact-contracts.md` when writing or moving project artifacts
6. `references/cli-run-protocol.md` and `references/workflows.md` when a formal route has CLI sidecars, manifests, or provenance gates
7. `references/punctuation-standard.md` when generating, reviewing, revising, or exporting Chinese prose
8. `references/orchestration.md` only for LangGraph, Dify, subagents, or external workflow design

Do not read the entire repository by default. Follow the route map in `agentread.yaml`.

## Mandatory Protocol

Every task must run through the protocol loop before it is considered complete:

1. Classify the workspace as skill root, work project, or style library.
2. Select the primary `agentread.yaml` route.
3. Read `references/agent-run-protocol.md`; if any CLI command will be used, also read `references/cli-run-protocol.md` or run `python -m literary_engineering_workbench protocol <route>`.
4. Record a reading receipt: selected route, references read, project files inspected, missing context, and pending sidecars.
5. Inspect current project state before generating, reviewing, promoting, or exporting.
6. Treat CLI output as preparation or evidence. The supervising platform agent handles creative judgment, JSON drafting/repair, review findings, branch decisions, and promotion recommendations.
7. Do not declare a documented command or task unavailable until you have probed it with `--help`, `protocol <route>`, or the smallest safe command attempt. If it fails, record the exact command and error.
8. Process any `.agent_tasks.md` sidecar by reading it and writing the expected artifact paths; a sidecar is executable work for the current platform agent, not a completed step or an external LLM prompt. After checking the expected artifacts, create the adjacent `.agent_completion.json`; later CLI gates may block without it.
9. For scene batches, build a per-scene ledger. One completed scene loop is not evidence for the rest of the chapter or volume.
10. Do not use debug or bypass flags such as `--allow-unreviewed`, `--allow-review-notes`, `--include-blocked`, or `--allow-unapproved` during formal Skill-host work.
11. Use `agent-task-status` or `route-audit` whenever pending sidecars, expected artifacts, or route gates are unclear.
12. For formal `scene-development`, `longform-planning`, `source-ingest`, and `style-engineering`, use `task-next`, `task-open`, `task-submit`, and `task-complete` as the controlling loop when available; do not choose the next formal step from memory.
13. Apply route completion gates before final response.
14. Report changed files, candidate-only outputs, promoted outputs, checks run, reading receipt, and approvals still needed.

## Operating Model

- Codex/Claude is the director, planner, LLM provider, conversation layer, and subagent orchestrator.
- This repository is the skill and toolbox.
- `src/literary_engineering_workbench/` in the development copy or `scripts/literary_engineering_workbench/` in the installed skill contains deterministic helper code and formal-route provenance generators, not the primary intelligence layer.
- The local `director-chat` implementation is legacy/experimental. Use it only when the user explicitly wants local orchestration or regression testing.
- Prefer platform-native reasoning, file editing, review, and subagents for creative work.
- Every creative generation, LLM-authored JSON/schema draft, simulation, review, branch choice, style prompt, candidate promotion recommendation, and free-form project decision must stay under the supervision of the tool-layer agent that loaded this skill.
- Creative body text is main-agent-only work. The main platform agent interacting with the user must personally compose prose candidates, revised prose, formal scene drafts, chapter bodies, screenplay scenes, pseudo-record entries, and final deliverable text.
- Subagents may support with bounded mechanical work such as retrieval summaries, evidence extraction, schema checks, continuity tables, punctuation/style issue lists, canon risk checklists, word-count inventories, and branch comparison. They must not ghostwrite or finalize body text.
- Existing-work reverse extraction is also platform-agent work: the CLI may import and chunk source text, but the platform agent extracts characters, background stories, world rules, outlines, timelines, foreshadowing, and style notes into candidate files. After an import exists, run `task-next --route source-ingest` until it returns ready; extracted candidates, sidecar completion marker, and clean extraction review are required.
- Longform word-budget planning is also platform-agent work: the CLI may calculate target distribution and inventory gaps, but the platform agent expands the outline, judges pacing/load, and decides readiness. For formal work, run `task-next --route longform-planning` until it returns ready; both budget and scene-inventory sidecars, candidates, completion markers, and clean `pass` reviews are required.
- `agent-task-status` and `route-audit` are dashboard helpers. They do not complete creative work; they reveal unhandled sidecars, missing expected artifacts, and incomplete route gates for the platform agent to resolve or list as pending.
- `task-next`, `task-open`, `task-submit`, and `task-complete` are the Phase 84 CLI-mediated task loop for formal routes such as `scene-development`, `longform-planning`, `source-ingest`, and `style-engineering`. The loop does not write creative content; it tells the platform agent what to do next, records submitted artifacts, validates expected outputs, and refreshes derived workflow state.
- Style engineering is platform-agent work: metrics and profiles are evidence, but the platform agent must write the LLM-facing `style_prompt.md`, satisfy the 500-2500 character quality contract, complete the style prompt sidecar, and obtain at least one accepted style evaluation before formal build/mount.
- Formal non-deterministic commands write platform-agent task sidecars plus expected output paths. The platform agent reads those tasks, performs the creative/review judgment, writes the expected artifacts, applies schema/canon/style checks, and decides the next step.
- `agent-review-scene` is a sidecar generator, not proof that an external model is required. Run it, read the generated task and its deterministic `Style Lint (auto-detected)` evidence, review the exact candidate yourself as platform agent, and write the expected scene review JSON/Markdown before promotion.
- `simulate-scene --agent` is not complete until the platform agent has filled the execution gate reading receipt and used scene/context/character/canon evidence for roleplay, world consequences, branch scoring, canon audit, and writeback candidates.
- A formal scene-development batch must repeat the full chain for every scene: context, RP, branch, branch selection, composition, prose candidate, exact-candidate AgentReview, promotion, promoted draft, and state patch. Do not process one representative scene and bulk-write the rest.
- Local model-backed commands, HTTP providers, and the local `director-chat` implementation are legacy/debug tools. Use them only when the user explicitly asks for that path.

## Hard Rules

- Project state is source code; prose is an artifact.
- Confirmed canon, approved character facts, and selected plot decisions are hard constraints.
- Retrieval, roleplay, branch simulations, model summaries, and style scores are evidence, not canon.
- LLM-authored JSON is not accepted merely because it parsed. Treat it as a draft until schema validation and tool-layer review accept it as candidate material.
- New characters, background stories, world rules, locations, organizations, relationships, outlines, major plot turns, and state changes start as candidates.
- Source-derived facts from existing works start as candidates with evidence references, confidence, contradictions, and unknowns. They must not directly overwrite formal `canon/`, `characters/`, `plot/`, `style/`, drafts, exports, or releases.
- For 100000+ word or multi-volume targets, create or inspect `plot/word_budget/word_budget.json` before bulk generation. If budget status is `needs_expansion`, process `word_budget.agent_tasks.md`, process `scene_inventory_expansion.agent_tasks.md`, and review the budgeted outline plus scene inventory candidates first. Each formal scene needs a budgetable `chapter_id`; `word_count_target`, `word_count_min`, and `word_count_max` in `scene.yaml` become generation/review constraints, and only cleaned deliverable prose counts.
- Count only cleaned deliverable prose as draft/chapter/longform/export length. Exclude workflow notes, review text, canon explanations, prompt manifests, `[AGENT_TASK: ...]`, status/writeback candidates, scene IDs, and internal paths.
- Formal scene generation must be gated by CLI-generated context, `simulate-scene --agent` roleplay with reading receipt and CLI provenance, `branch-simulate --agent` branch manifest with CLI provenance, formal `branch_selection.md`, and `compose-scene --agent-tasks` composition with `selection_source=selection`, `ready_for_generation=true`, and `formal_cli_provenance.created_by=compose-scene`. Manual file creation before generation is exploratory/debug-only and cannot satisfy formal route gates unless an attempted CLI failure and CLI-equivalent workaround are recorded. Do not start `generate-scene`, manual drafting, state writeback, or export from a scene that skipped this chain.
- `route-audit --route scene-development` is the per-scene completion ledger. For each `scenes/*.yaml`, missing prose candidate, exact-candidate AgentReview, Style Lint clean/notes-only, promotion manifest, promoted draft, static `review-scene` clean pass, revision anti-evasion manifest when applicable, or `state-evolve` patch is a blocking work item before chapter/export readiness.
- Promote candidates only after review and explicit user approval.
- `promote-candidate` is a formal gate, not a shortcut into review. Before promotion, the exact prose candidate must be cited in a passing `reviews/agent/{scene_id}_scene_review.json`; stale scene reviews, missing source paths, `pass_with_notes`, warnings, revision actions, or style deviations require `revise-scene` and re-review.
- Character `background_story` is hidden behavioral causality. It should affect action, omission, speech, hesitation, misreading, and pressure, not appear as direct exposition unless the scene is designed to reveal it.
- Mounted Style Skills have highest priority for expression-level writing choices, but never override canon, character facts, plot causality, safety/legal constraints, or explicit user instructions.
- Mounted Style Skills require a formal `style_adherence` review in `reviews/agent/{scene_id}_scene_review.json`. When a style is mounted, clean chapter readiness and formal export require `style_adherence.status=pass`; `pass_with_notes`, missing, `not_applicable`, or `revise_required` is blocking until revised or explicitly waived.
- Mountable Style Skills require a reliable LLM-facing `prompt.md` with 500-2500 non-whitespace content characters and complete high-quality prompt blocks: identity/boundary, priority, core mechanism, narrative distance, syntax/rhythm, punctuation, imagery/sensory, psychology/behavior, dialogue/tone, forbidden tendencies, and output self-check.
- Standard Chinese punctuation is a baseline expression constraint beneath every Style Skill. Do not let generated prose or reviews mix English punctuation into Chinese sentences or mix horizontal quotes `“”` with corner/vertical quotes such as `「」『』` unless the project explicitly records a format reason.
- Reduce AI-like prose habits during drafting and review, then satisfy the Style Lint Gate before promotion, chapter readiness, or formal export. Mechanical “不是……而是……” frames and dash variants such as “不是……——是……” are core banned frames and always blocking; same-function evasive contrast frames such as “并不是……只是……”“倒不是……只是……”“看似……其实……”“表面上……实则……” are also blocking. Other medium-or-higher AI trace findings are blocking; low findings are notes-only and require platform Agent review or a retention reason. Extract any intended correction, irony, or information-reversal function into actions, fact order, information gaps, or direct statements. Risk phrase families such as organ-rotation, generic placeholders, simile dependency, abstract summary language, explanatory psychology labels, template transitions, scenery syncing, symmetric slogan rhythm, omniscient theme explanation, and aphoristic endings use an approximately 2% narrative-unit density gate: isolated hits are review signals, dense hits require revision. Never let scripts batch-delete negation or perform semantic prose cleanup; platform agents must review those edits sentence by sentence.
- Revision must pass the anti-evasion protocol. Do not resolve a banned contrast by using another explicit contrast frame. When retaining a transition, write a burden-of-proof table in the revision report: original issue, revised sentence, whether a transition remains, disguised-replacement risk, why actions/fact order/information gaps cannot replace it, critical counterargument, and final conclusion. Weak justifications such as “增强节奏” or “体现复杂心理” do not pass.
- `pass_with_notes` requires a notes-resolution step. The writing agent must apply local revision_actions / warnings / style_notes through `revise-scene` and re-review before promotion, chapter readiness, export, or writeback.
- Final delivery exports must not expose engineering identifiers or process traces such as `scene_0001`, `chapter_0001`, scene/context paths, canon notes, review states, or writeback candidates. Keep those in manifests, reviews, and workbench files.
- Formal export must rebuild or verify the chapter workspace immediately before packaging. Do not export partial chapters: any non-ready scene, stale chapter state, unresolved review note, missing flow gate, or missing clean AgentReview blocks `export-package`.
- If an official gate blocks generation, promotion, chapter readiness, or export, do not replace it with an ad hoc script, debug flag, or unreview instruction and call the output final. Resolve the missing sidecar/review/readiness gate and run `revise-scene` when needed.
- Formal Skill hosts must not use debug/bypass flags: `--allow-unreviewed`, `--allow-review-notes`, `--include-blocked`, `--allow-unapproved`, `--allow-unresolved`, `--allow-missing-composition`, `--allow-unselected-composition`, `--allow-recommended-branch`, or `--allow-missing-branch`. These exist only for maintainers testing the skill implementation.
- Keep each character in a separate file. Mark `importance: major` for major characters; context packets load major characters plus secondary/cameo characters named by the current scene, instead of loading every biography into every scene.
- Do not store API keys or provider secrets inside work projects.
- Keep outputs auditable: say what changed, where candidates were written, what remains unapproved, and what validation ran.

## Common Director Moves

- Broad project idea: create or update project brief, identify first candidate pass, then proceed without asking operational questions.
- Existing text or complete work: run source ingest when useful, then reverse-extract project brief, characters, world, outline, timeline, foreshadowing, and style notes as candidates for continuation or rewrite.
- Longform scope problem: run or emulate `word-budget`, expand/review narrative and scene inventory, then run `route-audit --route longform-planning` before writing chapters in bulk.
- Character work: create candidate profile/background/relationship changes, then review for motive and OOC risk.
- World work: create candidate rules/locations/organizations, then review for constraints and loopholes.
- Plot work: create outline/branch candidates, then review scene function and setup/payoff.
- Scene work: build context, simulate character behavior, branch, compose, draft candidate prose, review, revise when notes exist, and propose state patches.
- Style work: build author style project, compile profile, generate LLM-facing style prompt, package/mount Style Skill.
- Release work: run readiness, canon, longform, export, DOCX delivery, and approval checks before delivery.

## Formal Route CLI

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

Informal discussion, outline brainstorming, and throwaway snippets may skip CLI. Formal artifacts that may be promoted, counted, exported, or written back must preserve CLI sidecar/manifest provenance where this skill provides a route command.

Print a route runbook before a CLI-backed task:

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench protocol scene-development
python -m literary_engineering_workbench task-next <project> --route scene-development
python -m literary_engineering_workbench task-next <project> --route longform-planning
python -m literary_engineering_workbench task-next <project> --route source-ingest
python -m literary_engineering_workbench task-next <project> --route style-engineering
python -m literary_engineering_workbench task-open <project> --task-id <task-id>
python -m literary_engineering_workbench task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_workbench task-complete <project> --task-id <task-id>
```

## Git Rules

- In this copied repository, use Git for the new project-skill line.
- Check `git status --short` before committing.
- Do not modify the original `literary-engineering-workbench` unless the user explicitly asks.
- Do not stage generated caches, logs, temporary workspaces, corpora, or API keys.
