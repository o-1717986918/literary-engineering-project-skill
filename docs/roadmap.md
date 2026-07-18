# 路线图

> Project-type Skill override: 本路线图保留原工作台从 Phase 1 到 Phase 63 的实现历史，便于后续 agent 复用 CLI/API/前端/文风实验室等可选组件。当前架构已经切换为“项目型 Skill”：Codex、Claude 等工具层平台负责项目总监、创作总监、模型调用、子 agent 编排和项目文件维护；`director-chat`、`/director/chat`、本地 `provider=auto`、Dify starter 等只作为可选工具或历史集成参考。若本文件与根目录 `SKILL.md`、`AGENTS.md`、`CLAUDE.md`、`agentread.yaml` 或 `references/project-director-playbook.md` 冲突，以后者为准。

## Phase 1：本地项目初始化器

已实现 `init`，生成作品项目结构。

## Phase 2：记忆索引 MVP

已实现 `index`、`search`、`context`。

## Phase 3：文风工程 MVP

已实现 `style-profile`。

## Phase 4：单场景生成闭环

已实现 `draft-scene` 和 `review-scene`。

## Phase 5：角色推演实验室

已实现 `simulate-scene`。

## Phase 6：编排平台蓝图

已实现 `orchestration-plan`。

## Phase 7：章节级流水线

已实现 `chapter-workspace`。

## Phase 8：中长篇扩展

已实现 `longform-audit` 和 `plot/longform_graph.json`。

## Phase 9：视频提示词与多格式导出

已实现 `export-package`。

## Phase 10：Agent 工作流编排 Runner

已实现 `run-workflow`，输出 `workflow_state.json` 和 `workflow_log.md`。

## Phase 11：FastAPI / LangGraph / Dify 实接入

已实现 `serve-api`、`run-langgraph`、`api_server.py`、`langgraph_adapter.py`。

## Phase 12：Dify Workflow DSL 示例

已实现 `dify-dsl`，输出 `docs/integrations/dify/literary-workbench-reviewer.workflow.yml`。`v0.12.1` 起默认输出 import-safe 基础链路，人工审批节点建议导入成功后在 Dify UI 中追加。

## Phase 13：API Token 鉴权

已实现 `serve-api --api-token` 和 `LEW_API_TOKEN`，工作流接口支持 `Authorization: Bearer` 与 `X-LEW-API-Token`。

## Phase 14：工作流持久化基础

已实现稳定 `--run-id`、关联重试 `--resume-run-id`、`workflow/runs/index.jsonl` 和 LangGraph `--thread-id`。

## Phase 15：审批闭环

已实现 `approval-summary`、`workflow/approvals/index.jsonl` 和 revise / reject 后续任务生成。

## Phase 16：创作模型适配层

已实现 `generate-scene`、provider 协议和 `dry-run` 生成候选。

## Phase 17：知识库后端抽象

已实现 `knowledge-build`、`knowledge-search` 和标准库 JSON 知识库后端，检索结果带来源、类型、canon 状态和 scene/chapter/character 元数据。

## Phase 18：文风评测增强

已实现 `style-eval`，支持回译评测、大纲扩写评测和盲评模式的本地指标报告。

## Phase 19：Canon / Plot Lint

已实现 `canon-lint`，输出 `reviews/canon_lint.md` 和 `reviews/canon_lint.json`，检查人物、场景、章节、伏笔、候选事实和 canon 文件状态。

## Phase 20：多分支剧情推演

已实现 `branch-simulate`，输出 `branches/{scene_id}/branch_simulation.md`、`branch_manifest.json` 和 `branch_selection.md`，支持多分支候选、五维评分、风险提示、写回候选和人工选择记录。

## Phase 21：发布链路

已实现 `publish-chapter`，输出 `releases/{chapter_id}/{release_id}/publish_manifest.json`、`release_notes.md`、`rollback.md` 和 `latest.json`，默认要求 canon-lint 无 blocking、章节全部 ready、导出无跳过场景且存在 approve 审批记录。

## Phase 22：场景创作编排器

已实现 `compose-scene`，输出 `drafts/compositions/{scene_id}_composition.md` 和 `.json`，把上下文、人物 BDI、背景故事隐性动因、多分支选择和场景目标整理为节拍、潜台词、对白意图、感官意象、正文种子和写回候选。

## Phase 23：模型 Provider 与 Prompt Pack

已实现 `http-chat` provider、项目级 `prompts/scene_generation_system.md` / `scene_generation_user.md`、`drafts/candidates/*.prompt.json` prompt manifest，以及 `run-workflow --generate-candidate` 可选生成节点。

## Phase 24：人物状态演化候选 Patch

已实现 `state-evolve`，输出 `characters/state_patches/{scene_id}_state_patch.md` 和 `.json`，从草稿、候选正文或场景编排包中提取人物状态变化与关系变化，生成待人工确认的候选 patch。

## Phase 25：候选转正与人物状态审批写回

已实现 `promote-candidate`，把 `drafts/candidates/` 模型候选转入 `drafts/scenes/` 草稿审查通道，并输出 `drafts/promotions/{scene_id}_promotion.md` / `.json`。已实现 `state-apply`，在 approve 审批记录存在后把人物状态 patch 受控写回 `characters/*.yaml`。

## Phase 26：LLM 文风约束提示词与有效性评测

已实现 `style-prompt`，把风格 profile 和 metrics 转为供 LLM 使用的 `style_prompt.md`。已实现 `style-prompt-eval`，用 `style_prompt.md + provider` 生成回译/扩写候选，并调用 `style-eval` 审查提示词有效性。`generate-scene` 现在优先注入 `style_prompt.md`。

## Phase 27：Agent Provider 基础层

已实现 `agent-run` 和 `agent_provider.py`，通用 Agent 任务会写出 `input.prompt.json`、`raw_output.md`、`parsed_output.json` 和 `validation_report.md`。当前支持 `dry-run` 与 `http-chat`，为后续 LLM 审查、JSON 生成、提示词生成和修复循环提供统一执行入口。

## Phase 28：Agent JSON Schema 与修复循环

已实现 `agent-validate`、`agent-repair`、`agent_schema.py` 和 `schemas/agent_outputs/*.schema.json`。

## Phase 29：Agent 场景审查

已实现 `agent-review-scene`，输出 `reviews/agent/{scene_id}_scene_review.md` 和 `.json`。

## Phase 30：Agent Canon / Continuity 审查

已实现 `agent-canon-review`，基于 `canon-lint` 和项目状态输出 Agent canon 审查报告。

## Phase 31：Agent JSON 草案与受控 Patch Plan

已实现 `agent-build-json` 和 `agent-plan-patch`，默认不允许直接写 `canon/`。

## Phase 32：Agent 文风提示词生成

已实现 `agent-style-prompt`，输出 schema-gated `style_prompt.md` 和 `style_prompt.agent.json`。

## Phase 33：多 Agent 审稿委员会

已实现 `agent-committee`，每个审稿角色独立留痕，再由 summary agent 输出委员会结论。

## Phase 34：Agent Workflow / LangGraph / Dify / API 联动

已实现 `run-workflow --agent-review`、`run-langgraph --agent-review`、API `/agent/run` / `/agent/runs/{run_id}`，并在 Dify DSL 中增加 `agent_review` 参数。

## Phase 35：Demo 与回归链路

已实现 `demo-project` 和相关回归测试，可生成自造 demo、Agent 审查产物和 workflow state。

## Phase 36：全局配置与本地前端控制台

已实现统一全局配置文件、`config-show` / `config-init` / `config-set-profile`、FastAPI `/config` 路由、本地静态前端控制台和对话式控制入口。模型 provider、文风提示词、Agent 任务和场景生成现在共享 `model_config.py` 配置层。

## Phase 37-45：Agent 设定创作层

已实现候选资产 schema、Agent 角色/背景故事/关系网创作、世界观/地点/组织创作、大纲/章节/场景列表创作、候选审查与晋升、`project-seeding` 等 workflow modes、FastAPI `/asset/*`、前端“设定工坊”、设定创作提示词模板和 demo 回归。

## Phase 46：顶层创作总监 Agent

已实现 `director-chat`、`director-status`、`director_agent.py`、`director_decision.v1`、`/director/chat`、`/director/status` 和前端“创作总监”入口。用户只给创作大方向，总监 Agent 负责二级路由、委派设定/场景工作流、记录决策和关联审查产物。

## Phase 54：Codex 式创作总监

已在 `v0.54.0` 实现 Codex 式创作总监第一版：前端对话不再强制已有项目路径，`/director/chat` 可从一句创作方向自动创建完整文学工程项目，并在后台记录 `director_tools` 隐藏工具计划、自然对话回复和 bootstrap 记录。

## Phase 55：创作总监对话记忆

已在 `v0.55.0` 实现创作总监短期对话记忆：每轮 `/director/chat` 会写入 `director/conversation/turns.jsonl`，`director-status` 返回 `recent_conversation`，下一轮总监提示词会注入最近对话。用户说“继续”“按刚才方向”或引用前文选择时，总监可复用上一轮偏好、未决问题和创作方向，而不是要求用户重复上下文。

## Phase 56：创作总监工具调用循环

已在 `v0.56.0` 实现有限 agent loop：`director_tools` 不再只是隐藏计划，而是由创作总监按“决策、执行、观察、再决策”的方式连续使用。每轮会写入 `director/runs/{run_id}/tool_loop.json`，记录工具调用、观察结果、再决策 Agent 运行和最终停止原因。默认最多 4 步，`auto_execute=false` 时只记录 planned 调用不执行写入。

## Phase 57-63：前端收束与文风学习 Style Skill

已在 `v0.63.0` 完成产品面重构：前端只保留创作总监、文风学习、全局配置。新增 `style_lab.py` 和 `/style-lab/*` API，以作家为文风项目、作品为子项目，支持作品文本导入、profile 编译、LLM 文风约束提示词生成、Style Skill 构建、提示词有效性评测和挂载到创作项目。挂载后 `style/active_style_skill.json` 成为创作项目 active style，`prompt_pack.py` 会优先注入 `style/mounted/{style_id}/prompt.md`，创作总监状态也会读取 `active_style_skill`，使文风成为表达层最高优先级约束。

## Phase 64：已有作品反推与源文本导入

已在 `v0.64.0` 实现 `source-ingest` / `extract-existing-work`：把用户提供的已有文本、完整作品、旧稿、剧本或伪记录材料导入 `sources/imports/{work_id}/`，生成 raw、chunks、`source_manifest.json`、`source_ingest.md` 和 `extract_project_files.agent_tasks.md`。平台 Agent 读取任务侧车后，反推项目简报、人物/背景故事、世界观、剧情大纲、时间线、伏笔和文风说明候选，分别写入 `sources/imports/{work_id}/extracted/`、`characters/candidates/extracted/`、`canon/candidates/extracted/`、`plot/candidates/extracted/`、`style/candidates/` 和 `reviews/source_ingest/`。源作品提取结果带证据引用和置信度，未经审查与用户批准不得晋升为正式项目资产。

## Phase 65：长篇字数预算与剧情库存门禁

已在 `v0.65.0` 实现 `word-budget` / `longform-budget` 和 `longform-planning` route：把目标字数、卷数、类型和时间跨度拆成卷、章、场景、平均字数与叙事负载预算，输出 `plot/word_budget/word_budget.md`、`word_budget.json` 和 `word_budget.agent_tasks.md`。平台 Agent 根据任务侧车写出 `plot/candidates/outlines/word_budget_expansion.md` 和 `reviews/word_budget/word_budget_review.md`，在正式生成前检查剧情库存是否足以支撑目标规模。`prompt_pack.py` 会把预算标准注入场景生成 prompt manifest；`longform-audit` 会报告预算缺失、needs_expansion 和场景库存不足。

## Phase 66：流程阅读回执、Review Notes 小修闭环与生成硬约束摘要

已在 `v0.66.0` 强化标准链路：`.agent_tasks.md`、agent-run protocol 和 CLI protocol 要求平台 agent 记录 reading receipt；`pass_with_notes` 不再是静默通过，下一轮生成会读取 `reviews/agent/{scene_id}_scene_review.json` 并注入 `generation_standards.review_notes`；prompt manifest 新增 `generation_standards.hard_constraints`，把 canon、场景编排、人物逻辑、文风、字数预算、AgentReview notes、标点和输出边界整理成生成前硬约束摘要，提高草稿/候选正文质量。

## Phase 67：最终正文口径、字数统计与 RP 门禁

已在 `v0.67.0` 统一最终正文口径：新增共享草稿正文清洗模块，导出、章节统计、长篇审计和 export manifest 均只统计清洗后可交付正文；最终小说、剧本和视频提示词包不再暴露 `scene_0001` / `chapter_0001` 等工程编号；`simulate-scene --agent` 增加平台 Agent 执行门禁和读取回执，防止 RP 推演跳过 scene/context/角色/canon 资料。

## Phase 68：平台 Agent 总控、场景修订闭环与场景库存绑定

已在 `v0.68.0` 实现 `agent-task-status` / `route-audit`，为工作项目输出 `workflow/agent_task_status.*` 和 `workflow/route_audit.*`，统一扫描 sidecar 未处理、预期产物缺失和 route gate 未完成。新增 `revise-scene`，将草稿、AgentReview notes、文风、canon、标点规范和字数预算汇总为平台 Agent 修订任务，输出修订候选与修订报告。`word-budget` 进一步生成分章预算、场景库存绑定、实际清洗正文字数、缺失场景列表和 `scene_inventory_expansion.agent_tasks.md`，使长篇目标字数与具体章节/场景库存强绑定。

## Phase 69：引号统一与 DOCX 版式规划补强

已在 `v0.69.0` 明确横排文学正文引号标准：直接引语统一“”，内层引语统一‘’，`review-scene` 会报告「」『』等角引号混用，最终导出会对角引号做安全归一化。DOCX 能力吸收 `office-academic-skill` 的可编辑文档、样式、字体、真实列表、表格和质量检查思想：`export-docx` / `export-package --formats md,docx` 会生成 `.layout.json` 与 `.inspection.json`，并把简单 Markdown 表格转换为原生 Word 表格。未迁移学术证据链、PPT、tracked changes、comments 和完整 XSD 校验，避免把学术 Office 工作流污染文学交付主线。

## Phase 70：正式场景推演与分支门禁

已在 `v0.70.0` 强化场景开发标准链路：`route-audit --route scene-development` 会阻塞缺失 context、`simulate-scene --agent` 读取回执、未处理 `[AGENT_TASK: ...]`、缺失 branch manifest、缺失正式 `branch_selection.md` 和未 ready 的 `selection_source=selection` composition。`generate-scene` 和 prompt pack 默认要求 ready composition；fallback、recommended-only 或未正式选择的 composition 只能作为内部实验，不能直接晋升、写回或导出。

## Phase 71：挂载文风正式验收门禁

已在 `v0.71.0` 把文风挂载从“生成前最高优先级约束”扩展为“生成后正式审查门禁”。`scene_review.v1` 新增必填 `style_adherence`，平台 Agent 必须审查挂载 Style Skill 是否真正影响叙述距离、句法节奏、意象/感官路由、心理呈现、对白语气、标点停顿和 AI 腔规避。`route-audit --route scene-development` 在存在 `style/active_style_skill.json` 时会阻塞缺失、`not_applicable` 或 `revise_required` 的文风执行审查，使文风学习、挂载、生成、审查和修订形成闭环。

## Phase 72：候选晋升前正式审查门禁

已在 `v0.72.0` 补齐 `generate-scene` 到 `promote-candidate` 之间的漏审查风险。`promote-candidate` 默认要求 `reviews/agent/{scene_id}_scene_review.json` 已经审查 exact candidate：JSON 必须满足 `scene_review.v1`，`source_paths` / `candidate` / `reviewed_candidate` 必须引用正在晋升的候选路径，`conclusion=pass`，且没有 blocking、warnings、revision_actions、style_notes 或 style_adherence 偏差。`--allow-unreviewed` 与 `--allow-review-notes` 只作为内部实验 waiver，并写入 promotion manifest。`route-audit --route scene-development` 会回查已有 promotion manifest，发现候选晋升前审查缺失或过期时输出 blocking gate。

已在 `v0.73.0` 补齐章节 ready 与 DOCX 交付层的两个漏点：最终正文清洗扩展到 `世界状态变化`、状态候选、写回候选等工作台痕迹，`export-docx` 直接处理草稿/候选工作台时也只抽取可交付正文；`chapter-workspace` 与 `longform-audit` 改用共享 `scene_readiness` 强门禁，要求 context、RP 读取回执、branch manifest、正式 branch selection、ready composition、静态 review clean pass、AgentReview clean pass 且引用当前草稿。`export-package` 默认重建章节工作台并阻塞任何非 ready 场景，`--include-blocked` 只用于内部预览。

## Phase 74：生成层反 AI 腔硬约束与语义清洗边界

已在 `v0.74.0` 把“不是……而是……”问题从事后 review 前移到 prompt pack、scene template、style prompt 和 agent-style-prompt 的生成前硬约束，并明确脚本只能做安全排版规范化或风险提示，不得批量删除“不是”、改写“不是 A——是 B”或替换心理判断，避免生成后清理造成语义反转。`v0.75.0` 已进一步收束：机械对照句式不再作为可授权修辞模板，只能抽象其叙事功能。

## Phase 75：朴素叙述约束与 AI 腔密度门禁

已在 `v0.75.0` 将用户提供的“给朋友讲一件事 / 日记标准”融入生成层和审查层。机械“不是……而是……”“并非……而是……”“与其说……不如说……”及“不是……——是……”等变体升级为核心禁区，不再允许平台 Agent 或 Style Skill 把它判断为合理修辞；若源文风存在否定纠偏，只抽象其认知二分、信息反转、讽刺顿挫或叙述者纠偏功能，并改写为动作、事实顺序、信息差或直接陈述。器官轮岗、万能占位、比喻依赖、抽象总结、景物强制同步、模板转折和破折号密集使用改为约 2% 叙事单元密度门禁：孤立风险点进入低级复核，密集出现升级为修订问题。可挂载文风 `prompt.md` 上限提升到 2500 字，以容纳更完整的优秀 prompt 模块和降低 AI 腔规则。

## Phase 47：前端显式 API Key 配置

已实现前端 API Key 密码输入框、`/config` 明文保存与脱敏响应、空 key 保存保留既有密钥、`model_config.py` 从环境变量或保存的 profile key 读取密钥。

## Phase 48：Agent 默认真实 LLM 接入

已实现统一 `provider=auto`，Agent 任务、设定创作、候选审查、创作总监、文风提示词和场景候选生成默认连接真实 `http-chat` 模型；未配置 API Key 时明确报错，只有显式 `dry-run` 才进入离线调试。

下一步：LangGraph 持久化 checkpointer、真实 Dify 导入验证、更细粒度前端审稿台、多候选比较器、源作品提取候选晋升向导、预算化大纲晋升向导和更多模型 profile 模板。
