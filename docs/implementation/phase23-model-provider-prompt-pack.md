# Phase 23：模型 Provider 与 Prompt Pack

## 状态

已在 `v0.23.0` 实现 `http-chat` provider、场景生成 prompt pack 和 workflow 可选候选生成节点。

## 目标

让真实 LLM 创作接入具备稳定工程边界：

- 提示词从代码字符串升级为项目内可版本化模板。
- 模型调用通过 provider 协议进入 `drafts/candidates/`。
- workflow 只有在开启模型候选或 Agent 审查节点时调用模型。
- API key 通过统一全局配置或环境变量提供，不写入项目文件、manifest 或日志。

## 新增与变更

### Prompt Pack

默认模板：

- `templates/prompts/scene_generation_system.md`
- `templates/prompts/scene_generation_user.md`

初始化作品项目时复制到：

- `prompts/scene_generation_system.md`
- `prompts/scene_generation_user.md`

每次 `generate-scene` 会生成：

```text
drafts/candidates/{scene_id}-{provider}-{timestamp}.prompt.json
```

该文件记录 system/user messages、场景、上下文包、场景创作编排包、文风 profile 和来源清单，便于复盘模型输入。

### Provider

当前 provider：

- `auto`：当前默认值，配置完整时解析为 `http-chat`。
- `dry-run`：本地占位，不需要外部模型。
- `http-chat`：通过标准库 HTTP 调用 chat-completions 兼容接口。

`http-chat` 所需环境变量：

```powershell
$env:LEW_MODEL_API_BASE = "https://your-model-endpoint/v1"
$env:LEW_MODEL_NAME = "your-model-name"
$env:LEW_MODEL_API_KEY = "your-api-key"
```

可选环境变量：

```powershell
$env:LEW_MODEL_TIMEOUT = "60"
$env:LEW_MODEL_TEMPERATURE = "0.7"
$env:LEW_MODEL_MAX_TOKENS = "2500"
```

当前 `auto` 要求存在 API Key；如需离线验证链路，显式使用 `--provider dry-run`。

## 命令

默认真实模型：

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench generate-scene work/demo-work --scene scenes/scene_0001.yaml --rebuild-context
```

离线 dry-run：

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench generate-scene work/demo-work --scene scenes/scene_0001.yaml --provider dry-run --rebuild-context
```

workflow 可选生成候选：

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench run-workflow work/demo-work --mode scene-loop --generate-candidate
```
未配置模型时，追加 `--provider dry-run` 可验证工程链路。

## 输出

`generate-scene` 输出：

- `drafts/candidates/{scene_id}-{provider}-{timestamp}.md`
- `drafts/candidates/{scene_id}-{provider}-{timestamp}.json`
- `drafts/candidates/{scene_id}-{provider}-{timestamp}.prompt.json`
- `drafts/candidates/{scene_id}-{provider}-{timestamp}.agent_tasks.md`（使用 `--agent-tasks` 时）

`run-workflow --generate-candidate` 会把以下路径写入 workflow state：

- `candidate`
- `candidate_manifest`
- `prompt_manifest`
- `candidate_agent_tasks`（使用 `--agent-tasks` 时）

## 边界

- 模型输出是候选，不是正稿。
- 候选不会覆盖 `drafts/scenes/`。
- 候选不会写入 `canon/`、`characters/` 或 `plot/`。
- prompt manifest 记录提示词内容，但不记录 API key，也不写入 `[AGENT_TASK: ...]`。
- 平台 agent 审查候选和 prompt manifest 的任务写入 sidecar `.agent_tasks.md`。
- 外部模型错误会让对应 workflow 节点失败，并要求人工处理。

## 下一步

- 针对不同模型风格增加 provider 配置 profile。
- 为 prompt pack 增加自动压缩和优先级预算。
- 将 `style-eval` 接到候选生成后的可选评测节点。
- 候选稿转草稿已由 Phase 25 的 `promote-candidate` 接管。
