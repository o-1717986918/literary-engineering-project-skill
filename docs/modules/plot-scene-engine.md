# 剧情与场景引擎

场景是工程单元，必须说明：

- 场景目标
- 冲突和阻碍
- 出场人物
- 输入 canon
- 输出变化
- 伏笔和后续债务

场景推演可以产生多条分支。使用 `branch-simulate` 生成结构化分支候选、五维评分和人工选择记录，但分支进入正稿前必须经过人物合理性、世界观一致性和剧情推进价值评估。

选定或采用推荐分支后，使用 `compose-scene` 生成场景创作编排包。该产物把场景目标、人物 BDI、背景故事隐性动因、分支行动链和风格约束整理为节拍、潜台词、对白意图、感官意象和正文种子。`compose-scene` 不是正稿生成器，输出仍需进入 `generate-scene`、人工扩写、`review-scene` 和 canon 审查链路。

`generate-scene` 使用 prompt pack 调用 provider，默认 `auto`，配置完整时连接真实 `http-chat` 模型；离线调试时显式使用 `--provider dry-run`。模型候选只进入 `drafts/candidates/`，并同步写入 `.prompt.json` 记录输入提示词和来源。
