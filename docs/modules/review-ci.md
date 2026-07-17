# 审查 CI

审查维度：

- canon 一致性
- 人物 OOC
- 场景目标是否推进
- 草稿是否为空或只有模板
- 是否存在 blocked 场景
- 是否需要人工确认
- 是否已完成平台 Agent 场景审查 JSON
- 平台 Agent 审查 JSON 是否通过 `scene_review.v1`
- 平台 Agent 审查结论是否为 `pass` 或 `pass_with_notes`
- 发布或导出前应运行 `canon-lint`，把人物、场景、章节、伏笔和未确认事实问题纳入门禁。

结论：

- `pass`
- `pass_with_notes`
- `revise_required`
- `reject`
