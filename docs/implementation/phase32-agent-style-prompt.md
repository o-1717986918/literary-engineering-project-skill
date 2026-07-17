# Phase 32：Agent 文风提示词生成

## 目标

将文风学习模块进一步对齐“最终产物是供 LLM 使用的文风约束提示词”。Agent 读取 `style-profile.md`、`style_metrics.json` 和 corpus manifest，输出 `style_prompt.v1` JSON，并把 `prompt_markdown` 写为 `style_prompt.md`。

## 新增能力

- `style_prompt_agent.py`
- `agent-style-prompt`
- `style/{profile}/style_prompt.md`
- `style/{profile}/style_prompt.agent.json`

## 命令

```powershell
$env:PYTHONPATH="src"
python -m literary_engineering_workbench agent-style-prompt work/demo/style/demo-author --provider dry-run
```

## 边界

Agent 生成的文风提示词仍需通过 `style-prompt-eval`、`style-eval`、回译和大纲扩写评估有效性。
