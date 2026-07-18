# Phase 9：视频提示词与多格式导出

命令：`export-package`

输出小说章节、剧本工作稿、长视频提示词包和 `export_manifest.json`。默认只导出 `ready` 场景。

`v0.67.0` 起，最终交付文件使用统一的“清洗后正文”口径：

- 小说、剧本、长视频提示词包不再把 `scene_0001`、`chapter_0001` 这类工程编号暴露为正文标题。
- 正文清洗会移除误混入正文区的 scene 编号、场景文件路径、上下文包、canon 说明、prompt manifest、`[AGENT_TASK: ...]`、状态变化候选和写回候选。
- `export_manifest.json` 仍保留 `scene_id`、草稿路径和审查路径，用于工程追溯；manifest 不是最终正稿。
- `draft_chars` 统计为清洗后可交付正文的去空白字符数，不把工作流程、审查说明或写回候选算作正文字数。

新增 DOCX 交付能力：

```powershell
python -m literary_engineering_workbench export-package work/demo-work --chapter-id chapter_0001 --formats md,docx
python -m literary_engineering_workbench export-docx work/demo-work/exports/chapter_0001/chapter_0001_novel.md --kind novel
```

- `--formats md,docx` 会在保留 Markdown 源导出的同时生成 `{chapter_id}_novel.docx`、`{chapter_id}_screenplay.docx` 和 `{chapter_id}_video_prompt_pack.docx`。
- DOCX 是最终交付文件，不是 canon；正式写回仍以章节工作台、审查和审批记录为准。
- DOCX 生成使用标准库打包 WordprocessingML，不增加第三方运行依赖。
