"""Tool-layer agent task sidecar helpers."""

from __future__ import annotations

from pathlib import Path


AGENT_TASK_MARKER = "[AGENT_TASK:"


def default_agent_tasks_path(artifact_path: Path) -> Path:
    """Return the sidecar path for platform-agent task instructions."""

    return artifact_path.with_suffix(".agent_tasks.md")


def render_agent_task_block(instruction: str) -> str:
    text = instruction.strip()
    return f"{AGENT_TASK_MARKER} {text}\n]"


def write_agent_tasks(
    output_path: Path,
    *,
    title: str,
    root: Path,
    source_paths: list[Path],
    tasks: list[tuple[str, str]],
    notes: list[str] | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_agent_tasks_document(
            title=title,
            root=root,
            source_paths=source_paths,
            tasks=tasks,
            notes=notes or [],
        ),
        encoding="utf-8",
    )
    return output_path


def render_agent_tasks_document(
    *,
    title: str,
    root: Path,
    source_paths: list[Path],
    tasks: list[tuple[str, str]],
    notes: list[str],
) -> str:
    lines = [
        f"# 平台 Agent 任务说明：{title}",
        "",
        "本文件给装载本 Skill 的 Codex / Claude / 工具层平台 agent 执行。",
        "它不是外部 LLM prompt，不是 canon，不是正式剧情内容；完成后可删除、替换或转化为正式推演/审查记录。",
        "",
        "## Source Artifacts",
        "",
    ]
    if source_paths:
        for path in source_paths:
            lines.append(f"- `{_rel(path, root)}`")
    else:
        lines.append("- 无。")
    lines.extend(
        [
            "",
            "## Execution Rules",
            "",
            "- 先读取 Source Artifacts，再执行下列任务。",
            "- 任何新增事实、人物状态变化、分支选择和发布判断都保持候选状态。",
            "- 不要把本文件中的任务标记写入 JSON、prompt manifest、正稿、canon 或发布包。",
            "- 如发现任务与 canon、角色事实、文风挂载或用户约束冲突，先记录冲突并请求确认。",
        ]
    )
    if notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in notes)
    lines.extend(["", "## Tasks", ""])
    for index, (heading, body) in enumerate(tasks, start=1):
        lines.extend(
            [
                f"### {index}. {heading}",
                "",
                render_agent_task_block(body),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
