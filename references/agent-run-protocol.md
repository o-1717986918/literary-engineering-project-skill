# Agent Run Protocol

Use this protocol whenever a tool-layer agent runs a literary engineering task through this skill. It is the non-optional operating loop that prevents skipped context, skipped review, and accidental promotion of generated material.

## Mandatory Loop

1. Classify the workspace.
   - Skill root: contains `SKILL.md`, `AGENTS.md`, `agentread.yaml`, `references/`, `templates/`, `schemas/`, and `src/` or `scripts/`.
   - Work project: contains `project.yaml`, `canon/`, `characters/`, `plot/`, `style/`, `scenes/`, `drafts/`, `reviews/`, `memory/`.
   - Style library: contains `authors/`, `works/`, `profiles/`, or `style_skills/`.
2. Select exactly one primary route from `agentread.yaml`. Add a secondary route only when the task truly crosses boundaries, such as style learning plus scene drafting.
3. Read the route references before changing artifacts. Do not read the whole repository by default.
4. Inspect current project state before planning: `project.yaml`, relevant canon/character/plot/style files, latest reviews, workflow runs, and approval records.
5. State a short plan to yourself or in the working trace: objective, route, artifacts to inspect, artifacts to create, review gates, and user approval boundary.
6. Execute deterministic preparation with CLI only when useful: initialize, index, search, build context, lint, compose, export, or generate platform-agent task sidecars.
7. Perform every non-deterministic creative or judgment step as the supervising platform agent. This includes prose, JSON drafting, schema repair, roleplay, branch choice, review findings, style prompts, and promotion recommendations.
8. When a command writes `.agent_tasks.md`, read it, fill the expected Markdown/JSON/prose artifact yourself, then inspect the produced artifact. Do not report the task file as completed work by itself.
9. Validate produced artifacts before acceptance:
   - JSON: schema validation or explicit schema review.
   - Canon and continuity: canon lint or platform-agent canon review.
   - Character logic: BDI, hidden `background_story`, relationship pressure, and OOC risk.
   - Style: mounted Style Skill and style prompt priority.
   - Chinese prose: `references/punctuation-standard.md`.
   - Release/export: readiness, approval, and target format checks.
10. Decide the artifact status: revise, keep as candidate, ask user, approve internally for experiment, or promote after explicit user approval.
11. Finish with an audit summary: files changed, candidate-only files, promoted files, checks run, blocked items, and next high-level creative choices.

## Platform Agent Responsibilities

- Maintain conversation-level creative intent and project memory.
- Choose the route and avoid operational questions when the next action is clear.
- Keep generated work separate from canon until reviewed and approved.
- Use subagents for independent passes when useful: character logic, world constraints, plot alternatives, style review, canon audit, or prose revision.
- Resolve disagreements between CLI reports, simulations, and generated candidates through project constraints and user intent.

## Non-Deterministic Work Gate

The following must never be delegated to local dry-run, HTTP helper, or CLI output as final authority:

- New prose, revision, synopsis, outline, scene, or script text.
- Character profiles, hidden background stories, relationship graphs, world rules, locations, and organizations.
- Style prompts, style effectiveness judgments, back-translation judgments, and mount decisions.
- JSON creation or repair when the JSON encodes creative judgment.
- Roleplay, branch simulation, consequence simulation, character-state evolution, and scene composition decisions.
- Scene review, canon review, committee review, candidate promotion recommendation, chapter readiness, and release choice.

Local tools may prepare inputs and task files for those actions, but the supervising platform agent must make the judgment and write or approve the artifact.

## Completion Gate

Before final response, check:

- Route selected from `agentread.yaml`.
- Required references read for that route.
- Project state inspected.
- All `.agent_tasks.md` outputs handled or explicitly listed as pending.
- Generated JSON/prose/reviews are marked candidate, reviewed, approved, or pending.
- Canon, character, style, punctuation, and release/export gates applied when relevant.
- User approval requirement is recorded for promotions or final release.
- Final response separates completed work from pending decisions.

## Forbidden Shortcuts

- Do not accept generated JSON because it parses.
- Do not accept branch scores, simulation scores, local director choices, or model ratings as final decisions.
- Do not promote candidates without review and approval unless the user explicitly requested an internal experiment.
- Do not skip punctuation review for Chinese prose because a Style Skill is mounted.
- Do not expose raw schemas, internal command chatter, or file paths to the user unless useful for the task or requested.
- Do not write API keys or provider secrets into work projects.
