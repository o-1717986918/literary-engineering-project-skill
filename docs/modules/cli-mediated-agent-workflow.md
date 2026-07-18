# CLI 中介 Agent 工作流

本模块是 Phase 84 的核心目标：让平台 Agent 保持自由创作能力，但让正式项目产物统一经过 CLI 持续状态机中介。

一句话原则：

> 用户自然对话不受限制；正式产物必须 CLI-mediated。

## 1. 为什么需要它

过去的正式场景链路依赖平台 Agent 自觉读取文档、运行命令、处理 sidecar、写 completion marker。实践中容易出现以下问题：

1. Agent 认为 CLI 是可选步骤，直接手写同名文件。
2. `.agent_tasks.md` 被当成“过程文件”跳过。
3. RP、branch、compose、review、promote、state-evolve 在批量场景中被省略。
4. `word_budget`、Style Lint、AgentReview notes 等约束生成了但没有进入下游链路。
5. review 或 export gate 阻塞时，Agent 倾向于用临时脚本或 debug flag 绕过。

CLI 中介工作流的目标不是让 CLI 写小说，而是让 CLI 负责发任务、管状态、收提交、做确定性校验和留下审计。

## 2. 职责边界

平台 Agent 负责：

1. 与用户自然沟通创作方向、审美判断和重大取舍。
2. 阅读 CLI 输出的任务包。
3. 写正文、修订、review、分支选择、状态判断和创意 JSON 草案。
4. 对创作判断负责。

CLI 负责：

1. 根据 `workflow-state` 派发下一项正式任务。
2. 输出给平台 Agent 的提示词包、必读文件、硬约束、预期产物和禁止捷径。
3. 接收平台 Agent 产物提交记录。
4. 检查 expected outputs、schema、provenance、Style Lint、word target、review gate 等确定性条件。
5. 写 completion marker、event log 和状态账本。

CLI 不负责：

1. 不替平台 Agent 写正文。
2. 不替平台 Agent 判断人物、剧情、文风和审稿结论。
3. 不把本地模型、dry-run 或 HTTP provider 输出作为正式创作权威。
4. 不允许手动推进状态绕过真实产物。

## 3. 最小命令闭环

当前支持 `scene-development`、`longform-planning` 与 `source-ingest` 三条正式路线。`scene-development` 是逐场景样板；`longform-planning` 用来确保长篇字数预算、预算化大纲和分场景库存不会被生成环节跳过；`source-ingest` 用来确保已有作品导入后的反推设定、候选资产和 review 不会被跳过。

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench task-next <project> --route scene-development
python -m literary_engineering_workbench task-open <project> --task-id <task-id>
# 平台 Agent 按 task 中的 Command / Hard Constraints 完成产物
python -m literary_engineering_workbench task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_workbench task-complete <project> --task-id <task-id>
python -m literary_engineering_workbench workflow-advance <project> --route scene-development
python -m literary_engineering_workbench workflow-events <project>
```

长篇规划路线使用同一套控制面：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench task-next <project> --route longform-planning
python -m literary_engineering_workbench task-open <project> --task-id <task-id>
# 平台 Agent 按 task 执行 word-budget、预算化大纲、预算 review、场景库存候选和库存 review
python -m literary_engineering_workbench task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_workbench task-complete <project> --task-id <task-id>
python -m literary_engineering_workbench workflow-advance <project> --route longform-planning
```

已有作品导入后的反推路线也使用同一套控制面：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench source-ingest <project> --source <source> --title <title> --work-id <work-id>
python -m literary_engineering_workbench task-next <project> --route source-ingest
python -m literary_engineering_workbench task-open <project> --task-id <task-id>
# 平台 Agent 读取 source chunks 和 extract_project_files.agent_tasks.md，写候选项目文件与 review
python -m literary_engineering_workbench task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_workbench task-complete <project> --task-id <task-id>
```

`task-next` 会写出：

1. `workflow/tasks/{task_id}.task.json`
2. `workflow/tasks/{task_id}.agent_tasks.md`
3. `workflow/events/task_events.jsonl`

`task-submit` 会写出：

1. `workflow/tasks/{task_id}.submission.json`
2. 对应 event log

`task-complete` 会先按 `current_state` 运行真实门禁，再写出：

1. `workflow/tasks/{task_id}.agent_completion.json`
2. 更新后的 `{task_id}.task.json`
3. 刷新的 `workflow/route_state.md` 和 `workflow/route_state.json`
4. 对应 event log

从 `v0.84.1` 起，`task-complete` 不只检查文件是否存在。它会按当前状态验证 CLI provenance、sidecar completion、branch selection、composition readiness、word-budget sidecar/review、candidate generation manifest、Style Lint、exact-candidate AgentReview、promotion waiver、static review 和 state patch JSON。失败时任务会进入 `blocked`，失败信息就是下一步修复任务。

从 `v0.84.2` 起，`task_registry.py` 使用 route registry 分发表、选择器、任务构建器和门禁函数。`longform-planning` 已接入同一生命周期：`word-budget-file`、`budget-agent-task`、`budget-review`、`scene-inventory-agent-task`、`scene-inventory-review`。预算 sidecar 的 completion marker 不能单独放行；预算化大纲候选、分场景库存候选和对应 clean `pass` review 也必须存在。

从 `v0.84.3` 起，`source-ingest` 已接入同一生命周期：`source-manifest`、`extraction-agent-task`、`extraction-review`。已有作品导入只负责源文本、chunk 和 extraction sidecar；反推出的项目简报、人物/背景、世界观、大纲、时间线、伏笔、文风 notes 和 extraction review 必须由平台 Agent 写入候选区。completion marker、候选文件和 clean `pass` review 缺一项都不能 ready。

## 4. Scene-development 样板状态

第一版按 `workflow_state.py` 已有推导状态发任务。典型顺序：

1. `context-packet`
2. `roleplay-simulation`
3. `roleplay-agent-task`
4. `branch-manifest`
5. `branch-agent-task`
6. `branch-selection`
7. `composition-json`
8. `composition-agent-task`
9. `scene-word-budget-contract`
10. `candidate-generation-provenance`
11. `generation-agent-task`
12. `candidate-review`
13. `agent-review-task`
14. `promotion-manifest`
15. `promoted-draft`
16. `static-review`
17. `state-patch-json`
18. `state-agent-task`

状态不是靠 CLI 手写推进，而是由真实项目文件、sidecar completion marker 和现有 gate 推导。`workflow-advance` 只是刷新账本，不允许把未完成状态强行改成完成。

## 4.1 Longform-planning 状态

长篇规划路线顺序：

1. `word-budget-file`
2. `budget-agent-task`
3. `budget-review`
4. `scene-inventory-agent-task`
5. `scene-inventory-review`

对应硬产物：

1. `plot/word_budget/word_budget.md`
2. `plot/word_budget/word_budget.json`
3. `plot/word_budget/word_budget.agent_tasks.md`
4. `plot/word_budget/word_budget.agent_completion.json`
5. `plot/candidates/outlines/word_budget_expansion.md`
6. `reviews/word_budget/word_budget_review.md`，结论必须为 `pass`
7. `plot/word_budget/scene_inventory_expansion.agent_tasks.md`
8. `plot/word_budget/scene_inventory_expansion.agent_completion.json`
9. `plot/candidates/scenes/word_budget_scene_inventory.md`
10. `reviews/word_budget/scene_inventory_review.md`，结论必须为 `pass`

这条路线专门堵住“预算文件生成了但没人读”的漏洞。正式批量场景生成前，平台 Agent 必须完成预算化大纲和场景库存两类判断，不能只靠拉长每个场景满足目标字数。

## 4.2 Source-ingest 状态

已有作品导入路线顺序：

1. `source-manifest`
2. `extraction-agent-task`
3. `extraction-review`

对应硬产物：

1. `sources/imports/{work_id}/source_manifest.json`
2. `sources/imports/{work_id}/source_ingest.md`
3. `sources/imports/{work_id}/extract_project_files.agent_tasks.md`
4. `sources/imports/{work_id}/extract_project_files.agent_completion.json`
5. `sources/imports/{work_id}/extracted/project_brief.md`
6. `characters/candidates/extracted/{work_id}_characters.md`
7. `canon/candidates/extracted/{work_id}_world.md`
8. `plot/candidates/extracted/{work_id}_outline.md`
9. `plot/candidates/extracted/{work_id}_timeline.md`
10. `plot/candidates/extracted/{work_id}_foreshadowing.md`
11. `style/candidates/{work_id}_style_generation_notes.md`
12. `reviews/source_ingest/{work_id}_extraction_review.md`，结论必须为 `pass`

这条路线专门堵住“导入了已有文本但没有真正反推项目文件”的漏洞。所有 source-derived 内容仍是 candidate，必须带 evidence_refs、confidence、unknowns 和 contradiction notes，不得直接覆盖正式 canon / characters / plot / drafts。

## 5. Task 包必须包含什么

每个 `agent-task.v1` 至少包含：

1. `task_id`
2. `route`
3. `scene_id`
4. `current_state`
5. `task_type`
6. `prompt_asset_id`
7. `command`
8. `required_reading`
9. `source_paths`
10. `hard_constraints`
11. `style_constraints`
12. `expected_outputs`
13. `submission_command`
14. `completion_command`
15. `validation_gates`
16. `forbidden_shortcuts`
17. `next_allowed_states`

这些字段是给平台 Agent 的执行边界，不是外部 LLM prompt，也不是 canon。

## 6. 使用纪律

1. 看到 `task-next` 输出后，先 `task-open`。
2. 读取 `workflow/tasks/{task_id}.agent_tasks.md`，不要只看终端摘要。
3. 如果任务要求运行原有命令，例如 `context`、`simulate-scene`、`generate-scene`，先运行该命令并检查输出路径。
4. 如果原有命令又生成 sidecar，先处理原 sidecar，再提交当前 task。
5. 产物写完后必须 `task-submit`。
6. `task-complete` 失败时，失败原因就是下一步工作，不得用 debug flag 绕过。
7. `route-audit` 和 `agent-task-status` 仍然是正式审计工具。

## 7. 与旧 sidecar 的关系

新 task registry 不删除旧 `.agent_tasks.md`。第一版做法是：

1. `workflow/tasks/*.agent_tasks.md` 是上层“统一任务包”。
2. 原命令生成的 sidecar 仍在原位置，例如 `branches/{scene_id}/roleplay_simulation.agent_tasks.md`。
3. 上层 task 会要求平台 Agent 处理原 sidecar，并把原 sidecar 的 `.agent_completion.json` 作为 expected output。
4. 后续阶段可以逐步把旧 sidecar 注册进 task registry，减少双层任务感。

## 8. 验收口径

第一版完成后，至少应满足：

1. `task-next` 能对 demo scene 发出下一项 formal task。
2. `task-open` 能输出完整 Agent 可执行任务包。
3. `task-submit` 拒绝不存在的提交产物。
4. `task-complete` 拒绝 expected outputs 缺失的任务。
5. `task-complete` 拒绝 current_state 对应真实 gate 未通过的任务，例如手写 composition、未完成 word-budget sidecar、Style Lint blocking、`pass_with_notes` review、debug-waiver promotion、非 clean pass static review。
6. `workflow-advance` 只能刷新 artifact-derived 状态，不能手动跳状态。
7. `workflow-events` 能回放 task issued / opened / submitted / completed / blocked。

## 9. 后续扩展

下一阶段应将本模块继续接入：

1. Prompt Registry：让 `prompt_asset_id` 不再只是标识，而是真正可验证的提示词资产。
2. Context Broker：让 `task-open` 输出稳定的 context trace。
3. Reader Experience Contract：让字数和章节义务进入 `task-open` 与 `task-complete`。
4. route-audit：逐步从“文件存在检查”升级为“task registry provenance 检查”。
5. 继续横向接入 `style-engineering`、`character-and-world-assets`、`review-and-audit`、`export-and-release`。
