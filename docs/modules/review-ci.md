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

## pass_with_notes 小修闭环

`pass_with_notes` 不是静默通过。它表示没有阻塞问题，但仍存在应该由 writing agent 局部处理的 notes。

要求：

- Agent Review JSON 中的 `revision_actions` / `warnings` / `style_notes` 必须具体、可执行。
- 下一轮 `generate-scene` 的 prompt manifest 会把这些 notes 注入 `generation_standards.review_notes`。
- 写作 agent 必须执行局部小修，或在“需要人工确认”中逐条说明无法执行/接受豁免的理由。
- 章节 ready、导出和写回前，应确认 notes 已处理或已有明确接受记录。
