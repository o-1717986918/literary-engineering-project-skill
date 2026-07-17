# Phase 29：Agent 场景审查

## 目标

> Current project-type skill override: `agent-review-scene` writes a platform-agent task sidecar and expected review paths. It does not call local `dry-run`, `http-chat`, or external agent services.

把单场景审查扩展为 LLM/Agent 语义审查。Agent 会读取 scene YAML、草稿、上下文包和文风提示词，输出符合 `scene_review.v1` 的结构化审查结果。

## 新增能力

- `agent_scene_review.py`
- `agent-review-scene`
- `reviews/agent/{scene_id}_scene_review.md`
- `reviews/agent/{scene_id}_scene_review.json`

## 命令

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench agent-review-scene work/demo --scene scenes/scene_0001.yaml
```

## 审查维度

- 人物行为是否符合 BDI、背景故事、当前状态和关系。
- 场景目标是否被推进。
- 是否存在 canon 风险或未确认事实。
- 文风提示词是否在句法、叙述距离和意象调度上生效。

## 边界

Agent 场景审查与 `review-scene` 并行存在。它不能替代人工审批，也不能直接发布或写 canon。
