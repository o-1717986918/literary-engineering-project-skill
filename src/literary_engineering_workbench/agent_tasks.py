"""Tool-layer agent task sidecar helpers."""

from __future__ import annotations

from pathlib import Path

from .punctuation_standard import PUNCTUATION_STANDARD_SHORT_RULE


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
    expanded_sources = list(source_paths)
    punctuation_ref = _punctuation_reference()
    if punctuation_ref and punctuation_ref not in expanded_sources:
        expanded_sources.append(punctuation_ref)
    output_path.write_text(
        render_agent_tasks_document(
            title=title,
            root=root,
            source_paths=expanded_sources,
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
        "它不是外部 LLM prompt，不是 canon，不是正式剧情内容；命令写出本文件只表示“任务已准备好”，不表示任务完成。",
        "当前平台 agent 应读取本文件、执行判断或创作、写入下方要求的目标产物，然后再继续晋升、导出或回复用户。",
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
            "- 先确认本任务所属 route，并读取 `SKILL.md`、`AGENTS.md`、`agentread.yaml`、`references/agent-run-protocol.md` 以及该 route 在 `agentread.yaml` 中列出的文档。",
            "- 在最终报告或目标 Markdown 中写明 reading receipt：route、已读文档、已检查项目状态、仍缺失的上下文。",
            "- 先读取 Source Artifacts，再执行下列任务。",
            "- 不要因为任务名称包含 agent / review / style / JSON 就判断自己不能做；如需 CLI 辅助，先运行 `--help` 或 `protocol <route>`，失败后记录真实错误。",
            "- 若本任务要求写 review JSON、候选正文、修订报告、分支选择或状态补丁，当前平台 agent 应直接完成这些产物；不要等待“外部 agent”。",
            "- 任何新增事实、人物状态变化、分支选择和发布判断都保持候选状态。",
            "- 不要把本文件中的任务标记写入 JSON、prompt manifest、正稿、canon 或发布包。",
            "- 如发现任务与 canon、角色事实、文风挂载或用户约束冲突，先记录冲突并请求确认。",
            f"- {PUNCTUATION_STANDARD_SHORT_RULE}",
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


def _punctuation_reference() -> Path | None:
    path = Path(__file__).resolve().parents[2] / "references" / "punctuation-standard.md"
    return path if path.exists() else None
