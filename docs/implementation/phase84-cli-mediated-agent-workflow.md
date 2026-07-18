# Phase 84：CLI 中介 Agent 工作流内核

版本：`v0.84.1`

## 目标

把正式 `scene-development` 从“平台 Agent 自己按文档记忆串命令”，推进为“CLI 根据持续状态机派发下一项正式任务”。用户仍和平台 Agent 自然对话；但正式产物由 CLI 发任务、平台 Agent 执行、CLI 收提交、校验 expected outputs 并写 completion marker。

## 新增模块

- `src/literary_engineering_workbench/task_registry.py`

核心函数：

- `issue_next_task()`：基于 `workflow_state.py` 派发下一项任务。
- `open_task()`：标记任务已打开，并重写可读任务包。
- `submit_task()`：记录平台 Agent 输出的产物路径。
- `complete_task()`：检查 expected outputs，写 `.agent_completion.json`，刷新 workflow state。
- `advance_workflow()`：刷新 artifact-derived 状态，不允许手动跳状态。
- `build_workflow_events()`：渲染 task event log。

## 新增 CLI

```powershell
python -m literary_engineering_workbench task-next <project> --route scene-development
python -m literary_engineering_workbench task-open <project> --task-id <task-id>
python -m literary_engineering_workbench task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_workbench task-complete <project> --task-id <task-id>
python -m literary_engineering_workbench workflow-advance <project> --route scene-development
python -m literary_engineering_workbench workflow-events <project>
```

## 新增文件契约

- `schemas/agent_task.v1.json`
- `schemas/agent_submission.v1.json`
- `schemas/agent_completion.v1.json`

任务文件写入：

- `workflow/tasks/{task_id}.task.json`
- `workflow/tasks/{task_id}.agent_tasks.md`
- `workflow/tasks/{task_id}.submission.json`
- `workflow/tasks/{task_id}.agent_completion.json`

事件文件写入：

- `workflow/events/task_events.jsonl`
- `workflow/events.md`

## 当前接入范围

第一版只支持 `scene-development`，并将已有 `workflow_state.py` 的当前步骤映射为 task package。覆盖步骤包括：

1. context packet
2. roleplay simulation
3. roleplay sidecar completion
4. branch manifest
5. branch sidecar completion
6. branch selection
7. scene composition
8. composition sidecar completion
9. word-budget contract
10. prose candidate generation provenance
11. generation sidecar completion
12. exact-candidate AgentReview
13. AgentReview sidecar completion
14. candidate promotion
15. promoted draft
16. static review
17. state patch
18. state sidecar completion

## 关键设计选择

### 1. 状态派生，不手动写死

`workflow-advance` 不接受 “advance-to ready” 之类参数。它只重新运行 `workflow_state.py`，根据真实项目文件和 gate 推导状态。这避免 Agent 用状态命令绕过产物。

### 2. 新 task registry 不删除旧 sidecar

当前版本采用双层兼容：

- `workflow/tasks/*.agent_tasks.md` 是统一控制任务包。
- 原命令生成的 sidecar 仍保留在原位置。
- 上层 task 可以要求平台 Agent 处理原 sidecar，并把原 sidecar 的 completion marker 作为 expected output。

后续 Phase 85-87 可以逐步把 Prompt Registry、Context Broker 和完整状态机接入，减少双层感。

### 3. CLI 不是创作权威

CLI 只负责：

- 发任务
- 输出约束
- 记录提交
- 检查文件存在和部分确定性 gate
- 写 completion marker
- 刷新状态

正文、审查、分支判断、角色推演、状态解释仍由主平台 Agent 完成。

## 已修复的相关问题

初始化模板允许 `scene_id: ""`。`workflow_state.py` 过去会把空 scene id 当成有效 id，导致状态路径变成 `branches/`、`_composition.json`、`reviews/agent/_scene_review.json`。本阶段已修正：空 scene id 自动回退到文件名 stem，例如 `scene_0001.yaml` -> `scene_0001`。

## v0.84.1 深度门禁硬化

`task-complete` 已从“expected outputs 存在性检查”升级为“按 `current_state` 调用真实 route gate”。这一步专门修复平台 Agent 手写同名文件、漏读 sidecar、跳过 word budget、跳过 AgentReview 或用 debug-waiver promotion 伪装完成的问题。

当前接入：

- `roleplay-simulation`：检查 `simulate-scene` CLI 来源标记。
- `branch-manifest` / `branch-agent-task`：检查 `branch_manifest.json` 的 `formal_cli_provenance.created_by=branch-simulate` 和 `agent_tasks_requested=true`。
- `branch-selection`：复用 `branch_selection_status()`，必须有 `decision: selected` 与 `selected_branch`。
- `composition-json` / `composition-agent-task`：复用 `ensure_composition_ready_for_generation()`，必须由 `compose-scene` 生成、基于正式 branch selection 且请求 sidecar。
- `scene-word-budget-contract`：复用 `ensure_scene_word_budget_ready()`，并额外检查 scene inventory sidecar/review。
- `candidate-generation-provenance` / `generation-agent-task`：复用 `candidate_generation_gate()`，并对 cleaned body 运行 Style Lint Gate 与场景字数预算 adherence。
- `candidate-review` / `agent-review-task`：复用 `candidate_generation_gate()` 与 `candidate_review_gate()`，要求 exact-candidate clean pass。
- `promotion-manifest` / `promoted-draft`：回查 promotion manifest，拒绝 `allow_unreviewed` / `allow_review_notes`，并重新验证 candidate generation 与 review gate。
- `static-review`：要求 `reviews/{scene_id}-review.md` 结论为 `pass`。
- `state-patch-json` / `state-agent-task`：检查 state patch JSON 可解析、schema 正确、scene_id 匹配且仍处于候选/审查/审批边界。

## 测试

新增：

- `tests/test_task_registry.py`

覆盖：

- `task-next` 能为首个 blocked scene 发 context task。
- `task-open` 标记任务 opened。
- `task-submit` 记录存在的 artifact。
- `task-submit` 拒绝不存在的 artifact。
- `task-complete` 拒绝缺失 expected outputs。
- `task-complete` 写 completion marker 和 event log。
- `task-complete` 拒绝手写 composition 缺 CLI provenance。
- `task-complete` 拒绝候选正文缺 generation provenance。
- `task-complete` 拒绝候选正文 Style Lint blocking。
- `task-complete` 拒绝 `pass_with_notes` AgentReview。
- `task-complete` 拒绝未处理 word-budget sidecar。
- `task-complete` 拒绝非 clean pass 的静态 review。
- `task-complete` 拒绝损坏的 state patch JSON。
- context 完成后 `task-next` 推进到 roleplay-simulation。
- CLI help 暴露新命令。

## 后续

Phase 85 应优先实现 Prompt Registry，让 `prompt_asset_id` 从占位标识升级为可验证、可预览、可版本化的提示词资产。
