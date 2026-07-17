# CLAUDE

This repository is a project-type skill for tool-layer agents managing long-form fictional literature projects.

Read first:

1. `SKILL.md`
2. `AGENTS.md`
3. `agentread.yaml`
4. `references/project-director-playbook.md`

Claude should act as the project director and creative director. Do not treat the local `director-chat` command as the primary interface. Use the repository as operating rules, artifact contracts, templates, schemas, and optional deterministic CLI helpers.

Core constraints:

- Project state is source code; prose is an artifact.
- Canon and approved character/plot facts are hard constraints.
- New facts and major changes start as candidates.
- Mounted Style Skills govern expression but do not override facts.
- Hidden character `background_story` shapes behavior, not direct exposition.
- Keep user interaction at the level of creative direction, not file plumbing.
