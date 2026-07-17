"""Chapter-level workspace assembly."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .review_ci import review_scene_draft
from .scene_draft import build_scene_draft, extract_draft_body


@dataclass(frozen=True)
class SceneChapterRecord:
    scene_id: str
    scene_path: str
    chapter_id: str
    location: str
    participants: tuple[str, ...]
    scene_goal: str
    context_path: str
    simulation_path: str
    draft_path: str
    review_path: str
    review_conclusion: str
    draft_chars: int
    status: str
    writeback_candidates: tuple[str, ...]


@dataclass(frozen=True)
class ChapterWorkspaceResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    chapter_id: str
    scene_count: int
    ready_count: int
    blocked_count: int


def build_chapter_workspace(
    project_root: Path,
    chapter_id: str = "chapter_0001",
    scenes: Iterable[Path] | None = None,
    build_missing: bool = False,
    review_drafts: bool = False,
    output: Path | None = None,
    json_output: Path | None = None,
) -> ChapterWorkspaceResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    selected_scenes = _select_scene_paths(root, chapter_id, scenes)
    if not selected_scenes:
        raise FileNotFoundError(f"no scene files found for chapter: {chapter_id}")

    records = []
    for scene_path in selected_scenes:
        records.append(
            _build_scene_record(
                root,
                scene_path,
                requested_chapter_id=chapter_id,
                build_missing=build_missing,
                review_drafts=review_drafts,
            )
        )

    markdown_path = _resolve_output(root, output, "drafts", "chapters", f"{chapter_id}.md")
    json_path = _resolve_output(root, json_output, "plot", "chapters", f"{chapter_id}.json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema": "literary-engineering-workbench/chapter-workspace/v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chapter_id": chapter_id,
        "project_root": str(root),
        "scenes": [asdict(record) for record in records],
        "summary": _chapter_summary(records),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_chapter_markdown(root, chapter_id, records, json_path), encoding="utf-8")

    blocked = [record for record in records if record.status in {"blocked", "needs_draft", "needs_review"}]
    ready = [record for record in records if record.status == "ready"]
    return ChapterWorkspaceResult(
        project_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
        chapter_id=chapter_id,
        scene_count=len(records),
        ready_count=len(ready),
        blocked_count=len(blocked),
    )


def _select_scene_paths(root: Path, chapter_id: str, scenes: Iterable[Path] | None) -> list[Path]:
    if scenes:
        selected = []
        for item in scenes:
            path = item if item.is_absolute() else root / item
            if not path.exists():
                raise FileNotFoundError(f"scene file not found: {path}")
            selected.append(path.resolve())
        return selected

    scene_dir = root / "scenes"
    if not scene_dir.exists():
        return []

    candidates = sorted(path.resolve() for path in scene_dir.glob("*.yaml") if not path.name.startswith("_"))
    matching = [path for path in candidates if _scene_chapter_id(_read(path)) == chapter_id]
    return matching or candidates


def _build_scene_record(
    root: Path,
    scene_path: Path,
    requested_chapter_id: str,
    build_missing: bool,
    review_drafts: bool,
) -> SceneChapterRecord:
    scene_text = _read(scene_path)
    scene_id = _scalar(scene_text, "scene_id") or scene_path.stem
    chapter_id = _scene_chapter_id(scene_text) or requested_chapter_id

    context_path = root / "memory" / "context_packets" / f"{scene_id}.md"
    draft_path = root / "drafts" / "scenes" / f"{scene_id}.md"
    review_path = root / "reviews" / f"{scene_id}-review.md"
    simulation_path = root / "branches" / scene_id / "roleplay_simulation.md"

    if build_missing and not draft_path.exists():
        build_scene_draft(root, scene=_relative(scene_path, root), rebuild_context=not context_path.exists())

    if review_drafts and draft_path.exists():
        review_scene_draft(root, draft_path, output=review_path)

    draft_text = _read(draft_path)
    review_text = _read(review_path)
    body = extract_draft_body(draft_text) if draft_text else ""
    conclusion = _review_conclusion(review_text)
    status = _scene_status(draft_path, review_path, body, conclusion)

    return SceneChapterRecord(
        scene_id=scene_id,
        scene_path=_rel_str(scene_path, root),
        chapter_id=chapter_id,
        location=_scalar(scene_text, "location"),
        participants=tuple(_list_after(scene_text, "participants")),
        scene_goal=_scalar(scene_text, "scene_goal"),
        context_path=_existing_rel(context_path, root),
        simulation_path=_existing_rel(simulation_path, root),
        draft_path=_existing_rel(draft_path, root),
        review_path=_existing_rel(review_path, root),
        review_conclusion=conclusion,
        draft_chars=len(body),
        status=status,
        writeback_candidates=tuple(_writeback_candidates(draft_text)),
    )


def _render_chapter_markdown(root: Path, chapter_id: str, records: list[SceneChapterRecord], json_path: Path) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    summary = _chapter_summary(records)
    lines = [
        f"# 章节工作台：{chapter_id}",
        "",
        f"生成时间：{generated_at}",
        f"状态文件：`{_rel_str(json_path, root)}`",
        "",
        "## 使用规则",
        "",
        "- 本文件是章节级工程工作台，不是最终正稿。",
        "- 只有场景审查通过后，场景正文才可进入章节装配区。",
        "- 跨场景新增事实、人物变化和伏笔变化必须进入写回候选，等待人工确认。",
        "- Dify 或其他前台工具可以展示本文件，但不得绕过后端直接写回 canon。",
        "",
        "## 章节状态",
        "",
        f"- 场景数：{summary['scene_count']}",
        f"- 可装配：{summary['ready_count']}",
        f"- 阻塞/待处理：{summary['blocked_count']}",
        f"- 总正文字符数：{summary['draft_chars']}",
        "",
        "## 场景清单",
        "",
        "| 场景 | 地点 | 参与者 | 目标 | 正文字符 | 审查 | 状态 |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for record in records:
        lines.append(
            "| {scene_id} | {location} | {participants} | {scene_goal} | {draft_chars} | {review} | {status} |".format(
                scene_id=record.scene_id,
                location=record.location or "未填写",
                participants="、".join(record.participants) or "未填写",
                scene_goal=record.scene_goal or "未填写",
                draft_chars=record.draft_chars,
                review=record.review_conclusion or "missing",
                status=record.status,
            )
        )

    lines.extend([
        "",
        "## 产物矩阵",
        "",
        "| 场景 | Context | Simulation | Draft | Review |",
        "| --- | --- | --- | --- | --- |",
    ])
    for record in records:
        lines.append(
            f"| {record.scene_id} | `{record.context_path or 'missing'}` | `{record.simulation_path or 'missing'}` | `{record.draft_path or 'missing'}` | `{record.review_path or 'missing'}` |"
        )

    lines.extend([
        "",
        "## 连续性检查",
        "",
    ])
    lines.extend(_continuity_lines(records))

    lines.extend([
        "",
        "## 章节正文装配区",
        "",
    ])
    for record in records:
        lines.extend(_draft_excerpt_lines(root, record))

    lines.extend([
        "",
        "## 写回候选汇总",
        "",
    ])
    has_candidates = False
    for record in records:
        if not record.writeback_candidates:
            continue
        has_candidates = True
        lines.append(f"### {record.scene_id}")
        lines.append("")
        for item in record.writeback_candidates:
            lines.append(f"- {item}")
        lines.append("")
    if not has_candidates:
        lines.append("- 暂无可汇总写回候选。")

    lines.extend([
        "",
        "## 人工确认",
        "",
        "- [ ] 本章所有 `blocked` 场景已修订。",
        "- [ ] 所有新 canon 候选已进入候选区，而非直接确认为事实。",
        "- [ ] 人物状态变化在相邻场景之间连续。",
        "- [ ] 伏笔设置和回收没有互相冲突。",
        "- [ ] 章节导出前已完成最终审查。",
    ])

    return "\n".join(lines) + "\n"


def _draft_excerpt_lines(root: Path, record: SceneChapterRecord) -> list[str]:
    lines = [f"### {record.scene_id}", ""]
    if record.status != "ready":
        lines.append(f"- 当前状态：{record.status}，暂不装配正文。")
        lines.append("")
        return lines
    draft_path = root / record.draft_path if record.draft_path else Path()
    body = extract_draft_body(_read(draft_path)) if draft_path.exists() else ""
    if not body:
        lines.append("- 审查通过记录存在，但未读取到正文。")
    else:
        lines.append(body)
    lines.append("")
    return lines


def _continuity_lines(records: list[SceneChapterRecord]) -> list[str]:
    lines = []
    if not records:
        return ["- 未发现章节场景。"]
    for prev, current in zip(records, records[1:]):
        lines.append(f"- `{prev.scene_id}` -> `{current.scene_id}`：检查人物状态、地点移动、时间推进和伏笔承接。")
    if len(records) == 1:
        lines.append("- 本章当前只有一个场景，连续性检查需要在新增场景后执行。")
    blocked = [record.scene_id for record in records if record.status != "ready"]
    if blocked:
        lines.append("- 阻塞场景：" + "、".join(blocked))
    else:
        lines.append("- 所有场景均可进入章节装配。")
    return lines


def _chapter_summary(records: list[SceneChapterRecord]) -> dict[str, int]:
    return {
        "scene_count": len(records),
        "ready_count": sum(1 for record in records if record.status == "ready"),
        "blocked_count": sum(1 for record in records if record.status != "ready"),
        "draft_chars": sum(record.draft_chars for record in records),
    }


def _scene_status(draft_path: Path, review_path: Path, body: str, conclusion: str) -> str:
    if not draft_path.exists() or not body:
        return "needs_draft"
    if not review_path.exists() or not conclusion:
        return "needs_review"
    if conclusion in {"pass", "pass_with_notes"}:
        return "ready"
    return "blocked"


def _review_conclusion(text: str) -> str:
    match = re.search(r"(?m)^-\s*结论：\s*(\S+)\s*$", text)
    return match.group(1).strip() if match else ""


def _writeback_candidates(draft_text: str) -> list[str]:
    candidates = []
    for heading in ["### 新增事实候选", "### 人物状态变化", "### 关系变化", "### 伏笔变化", "### 需要人工确认"]:
        section = _section_after_heading(draft_text, heading)
        for line in section.splitlines():
            stripped = line.strip()
            if stripped.startswith("-") and stripped.strip("- ").strip():
                candidates.append(f"{heading.replace('### ', '')}：{stripped.strip('- ').strip()}")
    return candidates


def _section_after_heading(text: str, heading: str) -> str:
    idx = text.find(heading)
    if idx < 0:
        return ""
    next_idx = text.find("\n### ", idx + 1)
    if next_idx < 0:
        next_idx = text.find("\n## ", idx + 1)
    return text[idx: next_idx if next_idx >= 0 else len(text)]


def _scene_chapter_id(scene_text: str) -> str:
    return _scalar(scene_text, "chapter_id")


def _scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    if not match:
        return ""
    value = match.group(1).strip()
    return value.strip("\"'")


def _list_after(text: str, key: str) -> list[str]:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    if not match:
        return []
    inline = match.group(1).strip()
    if inline.startswith("[") and inline.endswith("]"):
        return [item.strip().strip("\"'") for item in inline.strip("[]").split(",") if item.strip()]

    lines = text[match.end() :].splitlines()
    values = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-"):
            values.append(stripped.strip("- ").strip("\"'"))
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", stripped):
            break
    return values


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output


def _relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _existing_rel(path: Path, root: Path) -> str:
    return _rel_str(path, root) if path.exists() else ""
