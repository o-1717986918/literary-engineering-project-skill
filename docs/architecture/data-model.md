# 数据模型

核心对象：

- WorkProject：作品项目根目录。
- CanonFact：事实、规则、适用范围、来源和确认状态。
- CharacterProfile：目标、信念、情绪、秘密、关系、语言习惯。
- Scene：场景目标、冲突、出场人物、输入事实、输出变化。
- Draft：草稿文本和上下文来源。
- CandidatePromotion：模型候选转入草稿审查通道的选择记录。
- ReviewReport：审查结论、问题、修订建议。
- CharacterStatePatch：待审批的人物状态演化候选。
- CharacterStateApply：审批后人物状态写回记录。
- WorkflowRun：节点事件、状态、产物、人工确认需求。
- Release：通过 canon、章节 ready、导出和审批门禁后的发布版本。

写回原则：新事实先进入候选区或审查报告，人工确认后才能成为 canon。
