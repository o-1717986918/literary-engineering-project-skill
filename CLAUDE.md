# CLAUDE

This repository is a project-type skill for tool-layer agents managing long-form fictional literature projects.

Read first:

1. `SKILL.md`
2. `AGENTS.md`
3. `agentread.yaml`
4. `references/project-director-playbook.md`

Claude should act as the project director and creative director. Do not treat the local `director-chat` command as the primary interface. Use the repository as operating rules, artifact contracts, templates, schemas, and optional deterministic CLI helpers.

For creative generation, LLM-authored JSON, schema repair, style prompts, scene/branch simulation, candidate promotion, release choice, or any free-form project decision, Claude must remain the supervising tool-layer agent. Local model-backed commands may draft or validate artifacts, but their outputs are evidence until Claude reviews them against schema, canon, style, and user intent.

Core constraints:

- Project state is source code; prose is an artifact.
- Canon and approved character/plot facts are hard constraints.
- New facts and major changes start as candidates.
- Mounted Style Skills govern expression but do not override facts.
- Hidden character `background_story` shapes behavior, not direct exposition.
- Keep user interaction at the level of creative direction, not file plumbing.
