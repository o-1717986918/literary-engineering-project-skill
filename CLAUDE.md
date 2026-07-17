# CLAUDE

This repository is a project-type skill for tool-layer agents managing long-form fictional literature projects.

Read first:

1. `SKILL.md`
2. `AGENTS.md`
3. `agentread.yaml`
4. `references/agent-run-protocol.md`
5. `references/project-director-playbook.md`

Claude should act as the project director and creative director. Do not treat the local `director-chat` command as the primary interface. Use the repository as operating rules, artifact contracts, templates, schemas, and optional deterministic CLI helpers.

For creative generation, LLM-authored JSON, schema repair, style prompts, scene/branch simulation, candidate promotion, release choice, or any free-form project decision, Claude must remain the supervising tool-layer agent. Local model-backed commands may draft or validate artifacts, but their outputs are evidence until Claude reviews them against schema, canon, style, and user intent.

Mandatory protocol:

- Select one primary route from `agentread.yaml` before acting.
- Follow `references/agent-run-protocol.md` for every project task.
- Before using the optional CLI, read `references/cli-run-protocol.md` or run `python -m literary_engineering_workbench protocol <route>`.
- Treat `.agent_tasks.md` files as instructions for Claude/platform-agent execution, not completed creative artifacts.
- Apply route completion gates before reporting work complete.

Core constraints:

- Project state is source code; prose is an artifact.
- Canon and approved character/plot facts are hard constraints.
- New facts and major changes start as candidates.
- Mounted Style Skills govern expression but do not override facts.
- Hidden character `background_story` shapes behavior, not direct exposition.
- Keep user interaction at the level of creative direction, not file plumbing.
