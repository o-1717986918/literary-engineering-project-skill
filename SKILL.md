---
name: literary-engineering-project-skill
description: Project-type skill for Codex, Claude, and similar tool-layer agents to manage long-form fictional literature through a CLI-mediated workflow state machine. Use for novels, scripts, pseudo-record works, web fiction, long-video prompt projects, author style learning, style mounting, source-work reverse extraction, longform word-budget planning, scene development, prose generation, review, canon/character candidate management, DOCX/export packaging, and formal route sidecars. The platform agent supplies creative judgment and writing; the skill supplies operating constitution, task packages, schemas, prompts, and deterministic helper commands.
---

# Literary Engineering Project Skill

Use this skill when a tool-layer Agent is developing a long-form literary project as an engineering workspace. The host Agent is the director, writer, reviewer, and decision maker. The local CLI is the state machine and provenance layer.

## Host Constitution

For formal project work, do not treat the repository as a map for freehand editing. Treat it as a state machine.

1. Read `AGENTS.md` and `references/formal-host-operating-constitution.md`.
2. Choose the relevant formal route.
3. Use `task-next <project> --route <route>` to obtain the next task.
4. Use `task-open <project> --task-id <id>` as the executable package.
5. Read only the task package, its prompt asset, and the listed `source_paths` unless the package allows more.
6. Write only the task package `expected_outputs` as formal artifacts.
7. Use `task-submit` and `task-complete`; do not call a task complete by narration.
8. Use `route-audit` as the formal pass/fail ledger before promotion, chapter readiness, export, release, or writeback.

`workflow-state` and `workflow-dashboard` are navigation/read-only summaries. They do not replace `task-next`, `task-open`, `task-submit`, `task-complete`, or `route-audit`.

Bare `lew --help` intentionally shows the formal state-machine surface. `help-all` is for maintainers/debugging only; do not use it as a menu for ordinary creative work.

## Hard Bans

- Do not handwrite CLI-generated flow artifacts and pretend they are formal.
- Do not skip `.agent_tasks.md`; a sidecar is executable work for the current host Agent, not proof that a step is done.
- Do not use debug or bypass flags such as `--allow-unreviewed`, `--allow-review-notes`, `--include-blocked`, `--allow-unapproved`, `--allow-unresolved`, `--allow-missing-composition`, `--allow-unselected-composition`, `--allow-recommended-branch`, or `--allow-missing-branch` during formal Skill-host work.
- Do not set `LEW_MAINTAINER_MODE=1` during ordinary formal project work. That variable exists only for explicit repository maintenance and regression tests.
- Do not let subagents write, revise, polish, expand, or finalize body prose. Subagents may only gather evidence, summarize, lint, count, check schema, or produce bounded support notes.
- Do not bypass review, promotion, approval, export, release, state, or canon gates.
- Do not write workflow notes, canon notes, review traces, scene IDs, prompt manifests, or `[AGENT_TASK: ...]` into reader-facing prose or final delivery.
- Do not store API keys or provider secrets in work projects.

## What The Host Agent Does

The host Agent supplies all non-deterministic intelligence:

- creative direction and user conversation;
- body prose and revisions;
- branch choice and scene judgment;
- author-style prompt writing and evaluation;
- LLM-authored JSON after schema and semantic review;
- AgentReview, canon review, committee review, and release judgment;
- deciding whether an output remains candidate-only, needs revision, needs user approval, or can be promoted through the formal route.

The CLI supplies task order, dynamic prompt packages, source/target paths, provenance, deterministic lint/count/schema evidence, and route gates.

## Formal Scene Minimum

For scene development, the host Agent should not start from manual drafting. The task loop will lead through context, roleplay, branch choice, composition, generation, exact-candidate AgentReview, promotion, static review, state evolution, and canon writeback when required.

Generation must obey mounted style, punctuation rules, word budget, reader-experience contract, narrative rhythm/scene bridge, anti-AI-style constraints, new-character registration, and candidate-only writeback boundaries. Exact details are delivered by the current task package and prompt manifest.

## Canon And Rhythm

Durable world facts require canon writeback classification:

- `canon_change=true`: run `canon-evolve` and write candidate patch artifacts.
- `canon_change=false`: write `no_canon_change_reason`.
- `canon_change="unknown"`: run `canon-evolve`; do not silently skip.

Canon patches remain candidates until approved and applied through `canon-apply`. Use `canon-backlog` to inspect unapplied canon work before export/release.

Every formal composition/generation/review should carry narrative rhythm and scene bridge: scene function, incoming pressure, scene turn, reader effect, narrative distance, what to slow down, what to pass quickly, promise/payoff handling, texture variety, and outgoing hook. This prevents flat, average-speed scene summaries.

## Developer Notes

For ordinary creative project work, let the CLI task package reveal the needed files and constraints. For maintaining this skill itself, use the detailed material in `references/`, `docs/`, `templates/`, `schemas/`, `src/`, and `tests/`.
