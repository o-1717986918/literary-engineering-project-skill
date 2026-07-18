# Longform Word Budget Module

本模块解决长篇生成中常见的“目标 50 万字，实际一卷只有 2 万字”问题。核心判断是：字数不是靠要求场景更啰嗦来完成，而是靠足够的剧情库存、关系压力、信息推进、后果链和场景数量支撑。

## 适用场景

- 用户要求中长篇、50 万字、百万字、多卷、多季、多篇章。
- 大纲只有少量事件，却要求极长正文。
- 章节或场景生成明显压缩成摘要。
- `longform-audit` 发现正文规模与目标差距过大。

## 标准链路

1. 选择 `longform-planning` route。
2. 读取 `references/agent-run-protocol.md`、`references/cli-run-protocol.md`、`references/artifact-contracts.md` 和 `references/workflows.md`。
3. 运行或等价执行预算拆分：

```powershell
python -m literary_engineering_workbench protocol longform-planning
python -m literary_engineering_workbench word-budget "<work-dir>" --target-words 500000 --volumes 5 --genre mystery
```

4. 读取 `plot/word_budget/word_budget.agent_tasks.md`。
5. 平台 agent 写出 `plot/candidates/outlines/word_budget_expansion.md` 和 `reviews/word_budget/word_budget_review.md`。
6. 预算化大纲通过审查与用户批准前，不得覆盖正式 `plot/outline.md`。
7. 后续 `generate-scene` 的 prompt manifest 自动加载 `plot/word_budget/word_budget.json` 中的预算标准。
8. `longform-audit` 检查预算是否存在、是否 needs_expansion、场景库存是否明显不足。

## 文学理论约束

长篇字数由叙事单位累积而来。一个有效叙事单位通常至少完成以下一种功能：

- 推进行动：角色做出不可轻易撤销的选择。
- 改变信息：读者、角色或世界状态获得新信息。
- 制造代价：行动留下损失、债务、误解或新约束。
- 加深关系：人物之间的信任、敌意、依赖或误判发生变化。
- 改变空间/时间：场景切换带来新的风险、资源或规则。
- 建立回收：设置、延宕或兑现伏笔。

如果目标是 50 万字，项目不能只拥有十几个“剧情点”。它需要成百上千个可拆分的场景功能点：主线推进、关系线、世界信息、后果链、喘息段落和伏笔回收要形成网状结构，而不是把每个事件拉长。

## CLI 负责什么

CLI 只做可重复计算：

- 从 `project.yaml` 或参数读取目标字数、类型、卷数。
- 用类型预设拆分卷、章、场景、平均字数和叙事负载比例。
- 扫描 `plot/outline.md` 和 `scenes/*.yaml` 的现有库存。
- 输出预算报告、JSON 和平台 agent 任务侧车。

CLI 不负责判断“这个故事怎样才好看”，也不自动改写正式大纲。

## 平台 Agent 负责什么

平台 agent 必须完成主观和创造性判断：

- 判断类型、时间跨度与目标字数是否匹配。
- 将预算转化为可写的大纲候选和分场景库存。
- 检查是否存在灌水、重复桥段、无后果场景或机械扩写。
- 决定是否建议用户缩短目标、增加卷数、增加人物线、扩大时间跨度或改结构。
- 审查预算化大纲是否能支撑正式生成。

## 关键文件

- `plot/word_budget/word_budget.md`
- `plot/word_budget/word_budget.json`
- `plot/word_budget/word_budget.agent_tasks.md`
- `plot/candidates/outlines/word_budget_expansion.md`
- `reviews/word_budget/word_budget_review.md`

## 生成前门禁

正式场景生成前，平台 agent 应检查：

- 当前目标字数是否超过 100000。
- 是否存在 `plot/word_budget/word_budget.json`。
- 预算状态是否为 `ready` 或已经由平台 agent 说明可继续。
- 场景列表是否能覆盖预算场景数量的主体部分。
- prompt manifest 是否包含“长篇字数预算标准”。

如果预算为 `needs_expansion`，不得直接批量生成正文；先扩充大纲和场景库存。
