# Phase 10：Agent 工作流编排 Runner

命令：`run-workflow`

模式：

- `scene-loop`
- `chapter-publish`
- `full-cycle`

输出：

- `workflow/runs/{run_id}/workflow_state.json`
- `workflow/runs/{run_id}/workflow_log.md`

Runner 保留已有草稿，默认不覆盖人工写作成果。

`scene-loop` 当前节点顺序：

1. `retrieve_memory`
2. `build_context_packet`
3. `character_simulation`
4. `branch_simulation`
5. `scene_composition`
6. `generate_candidate`（可选）
7. `promote_candidate`（可选）
8. `draft_workspace`
9. `review_ci`
10. `state_evolution_patch`

其中 `branch_simulation` 产出 `branch_manifest.json` / `branch_selection.md`，`scene_composition` 产出 `drafts/compositions/{scene_id}_composition.md` / `.json`，用于把剧情分支和人物隐性动因整理为正文生成前的创作编排包。

`v0.23.0` 起，可通过 `--generate-candidate --provider auto|dry-run|http-chat` 在 `scene_composition` 后追加 `generate_candidate` 节点。`v0.48.0` 起 provider 默认 `auto`，配置完整时连接真实 LLM；离线调试需显式使用 `--provider dry-run`。

`v0.24.0` 起，若草稿存在，`review_ci` 后会追加 `state_evolution_patch` 节点，输出 `characters/state_patches/{scene_id}_state_patch.md` / `.json`。该节点只生成候选 patch，不写回人物档案。

`v0.25.0` 起，可通过 `--promote-candidate` 在生成候选后追加 `promote_candidate` 节点，把最新或刚生成的候选稿转成 `drafts/scenes/{scene_id}.md`，然后继续进入审查和人物状态 patch。人物状态写回仍由 `state-apply` 在审批后单独执行。
