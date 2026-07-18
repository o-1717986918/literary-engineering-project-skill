# CLAUDE

This repository is a project-type skill for tool-layer agents managing long-form fictional literature projects.

Read first:

1. `SKILL.md`
2. `AGENTS.md`
3. `agentread.yaml`
4. `references/agent-run-protocol.md`
5. `references/project-director-playbook.md`

Claude should act as the project director and creative director. Do not treat the local `director-chat` command as the primary interface. Use the repository as operating rules, artifact contracts, templates, schemas, and optional deterministic CLI helpers.

For creative generation, existing-work reverse extraction, longform word-budget planning, LLM-authored JSON, schema repair, style prompts, scene/branch simulation, candidate promotion, release choice, or any free-form project decision, Claude must remain the supervising tool-layer agent. Local model-backed commands may draft or validate artifacts, `source-ingest` may import/chunk source text, and `word-budget` may calculate target distribution, but their outputs are evidence until Claude reviews them against schema, canon, style, pacing, and user intent.

Mandatory protocol:

- Select one primary route from `agentread.yaml` before acting.
- Follow `references/agent-run-protocol.md` for every project task.
- Before using the optional CLI, read `references/cli-run-protocol.md` or run `python -m literary_engineering_workbench protocol <route>`.
- For formal `scene-development`, use the CLI-mediated loop when available: `task-next`, `task-open`, write or review the requested artifact as Claude/platform agent, `task-submit`, then `task-complete`.
- Record a reading receipt: route, references read, project files inspected, missing context, and pending sidecars.
- Treat `.agent_tasks.md` files as instructions for Claude/platform-agent execution, not completed creative artifacts.
- For existing texts or complete works, keep extracted settings in candidate/review paths with evidence and confidence until reviewed and approved.
- For 100000+ word or multi-volume targets, route through `longform-planning`, process `word_budget.agent_tasks.md`, and keep budgeted outline expansion as a candidate until reviewed and approved.
- Apply route completion gates before reporting work complete.

Core constraints:

- Project state is source code; prose is an artifact.
- Canon and approved character/plot facts are hard constraints.
- New facts and major changes start as candidates.
- Mounted Style Skills govern expression but do not override facts.
- `pass_with_notes` requires local note resolution: apply listed revision_actions / warnings / style_notes or record an explicit acceptance reason before treating the scene as ready.
- Hidden character `background_story` shapes behavior, not direct exposition.
- Keep user interaction at the level of creative direction, not file plumbing.
