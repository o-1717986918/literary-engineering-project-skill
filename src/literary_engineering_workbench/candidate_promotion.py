"""Promote a generated scene candidate into the reviewed draft lane."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class CandidatePromotionResult:
    project_root: Path
    candidate_path: Path
    draft_path: Path
    manifest_path: Path
    report_path: Path
    scene_id: str
    chars: int
    approval_run_id: str


def promote_scene_candidate(
    project_root: Path,
    scene: Path | None = None,
    candidate: Path | None = None,
    output: Path | None = None,
    overwrite: bool = False,
    approval_run_id: str = "",
    selection_note: str = "",
) -> CandidatePromotionResult:
    """Convert a provider candidate into a standard scene draft workspace."""

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    scene_path = root / "scenes" / "scene_0001.yaml" if scene is None else _resolve(root, scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")
    scene_id = scene_path.stem or "scene"
    candidate_path = _resolve_candidate(root, scene_id, candidate)
    candidate_text = _read(candidate_path)
    if not candidate_text:
        raise FileNotFoundError(f"candidate not found or empty: {candidate_path}")

    draft_path = _resolve(root, output, root / "drafts" / "scenes" / f"{scene_id}.md")
    if draft_path.exists() and not overwrite:
        raise FileExistsError(f"draft already exists: {draft_path}. pass overwrite=True to replace it")
    draft_path.parent.mkdir(parents=True, exist_ok=True)

    body = _candidate_body(candidate_text)
    if not body:
        raise ValueError(f"candidate has no usable body: {candidate_path}")
    sections = {
        "new_facts": _candidate_bullets(candidate_text, "新增事实候选"),
        "character_changes": _candidate_bullets(candidate_text, "人物状态变化"),
        "relationship_changes": _candidate_bullets(candidate_text, "关系变化"),
        "foreshadowing_changes": _candidate_bullets(candidate_text, "伏笔变化"),
        "approval_items": _candidate_bullets(candidate_text, "需要人工确认"),
    }
    generated_at = _now()
    draft = _render_draft(
        scene_id=scene_id,
        scene_path=_rel(scene_path, root),
        candidate_path=_rel(candidate_path, root),
        generated_at=generated_at,
        body=body,
        sections=sections,
    )
    draft_path.write_text(draft, encoding="utf-8")

    manifest_path = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    report_path = root / "drafts" / "promotions" / f"{scene_id}_promotion.md"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "literary-engineering-workbench/candidate-promotion/v0.1",
        "promoted_at": generated_at,
        "scene_id": scene_id,
        "scene": _rel(scene_path, root),
        "candidate": _rel(candidate_path, root),
        "draft": _rel(draft_path, root),
        "approval_run_id": approval_run_id,
        "selection_note": selection_note,
        "chars": len(draft),
        "writeback_sections": sections,
        "guardrails": [
            "本命令只把候选稿转入草稿审查通道，不确认 canon。",
            "转正后的草稿仍必须运行 review-scene。",
            "人物、关系和 canon 写回仍必须走单独审批链路。",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(manifest), encoding="utf-8")
    return CandidatePromotionResult(
        project_root=root,
        candidate_path=candidate_path,
        draft_path=draft_path,
        manifest_path=manifest_path,
        report_path=report_path,
        scene_id=scene_id,
        chars=len(draft),
        approval_run_id=approval_run_id,
    )


def _resolve_candidate(root: Path, scene_id: str, candidate: Path | None) -> Path:
    if candidate is not None:
        return _resolve(root, candidate)
    candidates = sorted(
        (root / "drafts" / "candidates").glob(f"{scene_id}-*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"no candidate found for scene: {scene_id}")
    return candidates[0]


def _candidate_body(text: str) -> str:
    body = _section(text, "正文候选", stop_heading="状态变化候选")
    if body:
        return body
    return _section(text, "正文草稿", stop_heading="状态变化")


def _candidate_bullets(text: str, heading: str) -> list[str]:
    section = _section(text, heading, level=3)
    items = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        item = stripped.lstrip("-").strip()
        if item and item not in {"无。", "待真实 provider 补全。"}:
            items.append(item)
    return items or ["无。"]


def _section(text: str, heading: str, level: int = 2, stop_heading: str = "") -> str:
    marks = "#" * level
    if stop_heading:
        pattern = rf"(?ms)^{marks}\s*{re.escape(heading)}\s*\n(.*?)(?=^{marks}\s*{re.escape(stop_heading)}\s*$|\Z)"
    else:
        pattern = rf"(?ms)^{marks}\s*{re.escape(heading)}\s*\n(.*?)(?=^###\s+|^##\s+|\Z)"
    match = re.search(pattern, text)
    if not match:
        return ""
    return match.group(1).strip()


def _render_draft(
    scene_id: str,
    scene_path: str,
    candidate_path: str,
    generated_at: str,
    body: str,
    sections: dict[str, list[str]],
) -> str:
    return f"""# 场景草稿工作台：{scene_id}

生成时间：{generated_at}

来源候选：`{candidate_path}`
场景文件：`{scene_path}`

## 使用规则

- 本文件由模型候选转入草稿通道，不是最终正稿。
- 写作时必须遵守上下文包中的硬 canon、人物状态和风格约束。
- 审查未通过前，不得把正文移动到正稿。
- 新事实、人物状态、关系和伏笔变化只列为候选，等待人工确认。

## 正文草稿

{body.strip()}

## 状态变化

### 新增事实候选

{_md_list(sections["new_facts"])}

### 人物状态变化

{_md_list(sections["character_changes"])}

### 关系变化

{_md_list(sections["relationship_changes"])}

### 伏笔变化

{_md_list(sections["foreshadowing_changes"])}

### 需要人工确认

{_md_list(sections["approval_items"])}

## 自检

- [ ] 未违背硬 canon。
- [ ] 人物行动符合当前 BDI。
- [ ] 背景故事没有被直白交代，只转化为行为和潜台词。
- [ ] 场景有明确冲突和输出状态。
- [ ] 文风约束被执行。
- [ ] 新事实已列入候选而非直接确认为 canon。
"""


def _render_report(manifest: dict[str, object]) -> str:
    lines = [
        f"# Candidate Promotion：{manifest['scene_id']}",
        "",
        f"- 候选：`{manifest['candidate']}`",
        f"- 草稿：`{manifest['draft']}`",
        f"- 时间：{manifest['promoted_at']}",
        f"- 审批 run：`{manifest.get('approval_run_id') or 'n/a'}`",
        "",
        "## 边界",
        "",
        _md_list(list(manifest["guardrails"])),
    ]
    note = str(manifest.get("selection_note") or "").strip()
    if note:
        lines.extend(["", "## 选择说明", "", note])
    return "\n".join(lines) + "\n"


def _md_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- 无。"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _resolve(root: Path, value: Path | None, default: Path | None = None) -> Path:
    if value is None:
        if default is None:
            raise ValueError("default path is required when value is None")
        return default
    return value if value.is_absolute() else root / value


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
