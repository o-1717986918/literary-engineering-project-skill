# AGENTS

This repository is a project-type Skill for tool-layer Agents such as Codex and Claude. The host Agent supplies intelligence; the CLI supplies state, task packages, evidence, and gates.

## Read First

1. `SKILL.md`
2. `references/formal-host-operating-constitution.md`
3. `references/agent-run-protocol.md`
4. `references/cli-run-protocol.md` when formal route commands, sidecars, manifests, or provenance gates are involved
5. `references/punctuation-standard.md` when generating, reviewing, revising, or exporting Chinese prose

Detailed project structure and implementation notes live in `references/` and `docs/`. Do not use those documents as a shortcut for freehand formal artifact creation; formal work should come from the current CLI task package.

## Formal Operating Discipline

- Use `task-next <project> --route <route>` to obtain the next formal task when the route is registered.
- Use `task-open` as the executable task package.
- Read the task package prompt asset and listed `source_paths`.
- Write the listed `expected_outputs`.
- Process every `.agent_tasks.md` sidecar and create the adjacent `.agent_completion.json` after checking expected artifacts.
- Submit and complete through `task-submit` and `task-complete`.
- Use `route-audit` as the formal pass/fail ledger before promotion, chapter readiness, export, release, state apply, or canon apply.
- Treat `workflow-state` and `workflow-dashboard` as navigation/read-only summaries only.

Do not choose lower-level commands from memory when the task loop is available. Commands such as `context`, `simulate-scene`, `branch-simulate`, `compose-scene`, `generate-scene`, `agent-review-scene`, `state-evolve`, `canon-evolve`, `chapter-workspace`, and `export-package` are route internals unless the task package or route protocol tells the host Agent to run them.

Bare `lew --help` is the formal operating surface. `help-all` exposes the full internal command map for maintainers/debugging; do not use it as an ordinary shortcut menu for creative project work.

## Non-Deterministic Work

The main host Agent must personally handle:

- body prose, revision, polishing, expansion, and final text;
- creative branch choices and scene judgments;
- style prompt writing and style evaluation judgment;
- semantic AgentReview, canon review, committee review, and release judgment;
- LLM-authored JSON after schema and project-constraint review.

Subagents may only do bounded support work: retrieval summaries, continuity tables, issue lists, schema checks, lint/count evidence, canon risk notes, and similar mechanical assistance. They must not ghostwrite body text or final creative artifacts.

## Forbidden Shortcuts

- Do not handwrite CLI-generated flow artifacts as if they were formal outputs.
- Do not skip sidecars or completion markers.
- Do not use debug/bypass flags during formal Skill-host work: `--allow-unreviewed`, `--allow-review-notes`, `--include-blocked`, `--allow-unapproved`, `--allow-unresolved`, `--allow-missing-composition`, `--allow-unselected-composition`, `--allow-recommended-branch`, or `--allow-missing-branch`.
- Do not set `LEW_MAINTAINER_MODE=1` during ordinary formal project work. It exists only for explicit repository maintenance and regression tests.
- Do not bypass exact-candidate review, Style Lint Gate, word budget, reader experience, narrative rhythm/bridge, new-character registration, promotion, state, canon, export, or release gates.
- Do not apply generated JSON, branch scores, simulation output, state patches, canon patches, or style prompts directly to formal project state without the relevant review/approval/promotion route.
- Do not put workflow traces, scene IDs, source paths, canon notes, review text, writeback candidates, prompt manifests, or `[AGENT_TASK: ...]` in reader-facing delivery.

## Scene Development Discipline

Scene work is per scene. One completed scene loop does not cover the rest of a chapter or volume.

The formal route must carry context trace, roleplay sidecar, branch sidecar and selection, composition, generation task, exact-candidate AgentReview, promotion, promoted draft, static review, state-evolve, and canon-evolve when `canon_change` is true or unknown.

Generation and review must obey mounted style, punctuation standard, cleaned Chinese-content word budget, reader-experience contract, narrative rhythm/scene bridge, scene function, reader effect, narrative distance, anti-evasion rules, new-character registration, and candidate-only writeback.

Canon writeback is not complete merely because a patch exists. If a scene creates durable world facts, inspect `canon-backlog`, obtain approval where required, and run `canon-apply` before export/release readiness.

## Maintenance Mode

When maintaining the Skill repository itself, use `references/`, `docs/`, `templates/`, `schemas/`, `src/`, and `tests/` as developer documentation. After changing prompts, routes, schemas, or code, run the relevant validation commands and summarize changed files and remaining risks.
