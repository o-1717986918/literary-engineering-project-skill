# Literary Engineering Project Skill

这是从 `literary-engineering-workbench` 复制出来的新路线：把原本庞大的内置创作总监系统，转化为供 Codex、Claude 等工具层平台使用的大型项目型 Skill。

## 新定位

- Codex / Claude：项目总监、创作总监、真实 LLM provider、子 agent 编排者。
- 本项目：工程规范、文件结构、artifact contract、文风机制、模板、schema、可选 CLI 工具箱。
- 本地 `director-chat`：保留为实验/回归工具，不再是主入口。
- 前端 / FastAPI / LangGraph / Dify：可选适配层，不是核心能力。

## 使用入口

工具层 agent 先读：

1. `SKILL.md`
2. `AGENTS.md`
3. `agentread.yaml`
4. `references/project-director-playbook.md`

然后按任务选择性读取：

- `references/artifact-contracts.md`
- `references/workflows.md`
- `references/orchestration.md`
- `docs/` 下对应模块文档

## 可选 CLI

在这个复制后的开发目录中：

```powershell
$env:PYTHONPATH = "src"
python -m literary_engineering_workbench --help
```

运行测试：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## 核心原则

1. 项目状态是源代码，文本是产物。
2. 平台 agent 担任总监，不把本地内置 agent loop 当成必需层。
3. 新设定、新人物、新剧情、新状态默认先进入候选区。
4. canon、人物事实、剧情因果和明确用户约束高于风格。
5. Style Skill 是表达层最高优先级，但不覆盖事实。
6. 审查和人工确认是正式合并边界。
7. API Key 和 provider 密钥不进入作品项目目录。
