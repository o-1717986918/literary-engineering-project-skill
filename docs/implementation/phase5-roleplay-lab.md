# Phase 5：角色推演实验室

命令：`simulate-scene`

读取人物 BDI、恐惧、秘密、道德边界和语言习惯，输出角色行动提案、世界后果、导演评分和 canon 审查提示。

`--agent` / `--agent-tasks` 会把空白工作区改成 `[AGENT_TASK: ...]` 指令，供装载 Skill 的平台 agent 补全。默认不启用，旧输出保持不变。
