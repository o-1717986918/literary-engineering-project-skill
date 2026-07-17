# Phase 9：视频提示词与多格式导出

命令：`export-package`

输出小说章节、剧本工作稿、长视频提示词包和 `export_manifest.json`。默认只导出 `ready` 场景。

新增 DOCX 交付能力：

```powershell
python -m literary_engineering_workbench export-package work/demo-work --chapter-id chapter_0001 --formats md,docx
python -m literary_engineering_workbench export-docx work/demo-work/exports/chapter_0001/chapter_0001_novel.md --kind novel
```

- `--formats md,docx` 会在保留 Markdown 源导出的同时生成 `{chapter_id}_novel.docx`、`{chapter_id}_screenplay.docx` 和 `{chapter_id}_video_prompt_pack.docx`。
- DOCX 是最终交付文件，不是 canon；正式写回仍以章节工作台、审查和审批记录为准。
- DOCX 生成使用标准库打包 WordprocessingML，不增加第三方运行依赖。
