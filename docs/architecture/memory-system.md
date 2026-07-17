# 记忆系统

短期实现：

- `memory/index.json`：标准库轻量索引。
- `memory/context_packets/{scene_id}.md`：场景上下文包。
- 检索结果只作为软记忆，不能自动成为 canon。

后续升级：

- LlamaIndex 负责 ingestion、chunking、hybrid retrieval。
- Qdrant 负责向量检索。
- SQLite/PostgreSQL 负责结构化事实、审批和任务状态。
- Neo4j 负责人物关系、因果链、伏笔和场景图谱。

每次检索要保留来源路径和摘要，方便审查。
