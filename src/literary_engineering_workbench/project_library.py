"""Packaged project library views for the local frontend."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .display_cleaner import (
    display_counts,
    file_label,
    list_from_yaml_text,
    markdown_to_display_text,
    nested_scalar_from_yaml_text,
    prose_body_for_display,
    read_json_file,
    read_jsonl_tail,
    scalar_from_yaml_text,
    summarize_text,
    truncate_text,
)
from .style_lab import active_project_style


PROJECT_LIBRARY_SCHEMA = "literary-engineering-workbench/project-library/v0.1"


def build_project_library(project_root: Path) -> dict[str, object]:
    """Build a human-facing, read-only project library snapshot."""

    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    overrides = _load_overrides(root)
    sections = {
        "drafts": _draft_items(root, overrides),
        "characters": _character_items(root, overrides),
        "world": _world_items(root, overrides),
        "scenes": _scene_items(root, overrides),
        "branches": _branch_items(root, overrides),
        "style": _style_items(root, overrides),
        "reviews": _review_items(root, overrides),
        "word_budget": _word_budget_items(root, overrides),
    }
    counts = {key: len(value) for key, value in sections.items()}
    project = _project_card(root, overrides)
    return {
        "schema": PROJECT_LIBRARY_SCHEMA,
        "generated_at": _now(),
        "project_root": str(root),
        "project": project,
        "counts": counts,
        "sections": sections,
        "recent_human_choices": read_jsonl_tail(root / "workflow" / "human_choices" / "index.jsonl", 8),
        "recent_user_notes": read_jsonl_tail(root / "workflow" / "user_notes" / "index.jsonl", 8),
        "rules": [
            "This library is display-only. It packages artifacts for users but does not promote candidates or advance routes.",
            "Draft bodies are cleaned with final-delivery rules before display and counting.",
            "Canon, character, prose, and release changes must still use candidate/review/approval or formal CLI routes.",
        ],
    }


def find_project_library_item(project_root: Path, kind: str, item_id: str) -> dict[str, object]:
    library = build_project_library(project_root)
    sections = library.get("sections") if isinstance(library.get("sections"), dict) else {}
    items = sections.get(kind, []) if isinstance(sections, dict) else []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and str(item.get("id") or "") == item_id:
                return {"ok": True, "kind": kind, "item": item, "library_generated_at": library.get("generated_at", "")}
    raise FileNotFoundError(f"library item not found: {kind}/{item_id}")


def _project_card(root: Path, overrides: dict[str, object]) -> dict[str, object]:
    text = _read_text(root / "project.yaml")
    title = nested_scalar_from_yaml_text(text, "project", "title") or scalar_from_yaml_text(text, "title") or root.name
    project_type = nested_scalar_from_yaml_text(text, "project", "type") or "novel"
    target = nested_scalar_from_yaml_text(text, "project", "target_length") or nested_scalar_from_yaml_text(text, "longform_budget", "target_words")
    premise = nested_scalar_from_yaml_text(text, "creative_brief", "premise")
    genre = nested_scalar_from_yaml_text(text, "creative_brief", "genre")
    item = {
        "kind": "project",
        "id": "project",
        "title": title,
        "subtitle": "项目总览",
        "path": "project.yaml" if (root / "project.yaml").exists() else "",
        "status": nested_scalar_from_yaml_text(text, "project", "status") or "unknown",
        "badges": [badge for badge in [project_type, genre, f"目标 {target} 字" if target else ""] if badge],
        "excerpt": premise or "还没有项目简介。",
        "facts": [
            {"label": "作品类型", "value": project_type},
            {"label": "目标长度", "value": target or "未设置"},
            {"label": "语言", "value": nested_scalar_from_yaml_text(text, "project", "language") or "zh-CN"},
        ],
    }
    return _apply_overrides(item, overrides)


def _draft_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for folder, status, label in [
        (root / "drafts" / "scenes", "promoted", "已晋升正文"),
        (root / "drafts" / "candidates", "candidate", "候选正文"),
        (root / "drafts" / "revisions", "revision", "修订候选"),
        (root / "drafts" / "chapters", "chapter", "章节合稿"),
    ]:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md"))[:200]:
            text = _read_text(path)
            body = prose_body_for_display(text, limit=7000)
            scene_id = _scene_id_from_draft(path)
            target = _scene_target(root, scene_id)
            title = _first_heading(text) or _display_scene_name(scene_id)
            counts = display_counts(body, target=target)
            item = {
                "kind": "drafts",
                "id": f"{status}__{path.stem}",
                "title": title,
                "subtitle": label,
                "path": _rel(path, root),
                "status": status,
                "badges": [label, f"{counts['chinese_content_chars']} 字"],
                "excerpt": summarize_text(body, limit=220) or "正文为空或只有工程说明。",
                "body": body,
                "metrics": counts,
                "facts": [
                    {"label": "正文口径", "value": "已过滤工程痕迹"},
                    {"label": "目标字数", "value": target or "未设置"},
                    {"label": "机器字符", "value": counts["machine_nonspace_chars"]},
                ],
            }
            items.append(_apply_overrides(item, overrides))
    return items


def _character_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    folder = root / "characters"
    if not folder.exists():
        return []
    items = []
    for path in sorted(folder.glob("*.yaml"))[:200]:
        if path.name.startswith("_"):
            continue
        text = _read_text(path)
        character_id = scalar_from_yaml_text(text, "character_id") or path.stem
        name = scalar_from_yaml_text(text, "name") or file_label(path)
        importance = scalar_from_yaml_text(text, "importance") or "secondary"
        role = scalar_from_yaml_text(text, "role") or importance
        background = nested_scalar_from_yaml_text(text, "background_story", "summary")
        fear = _first_nested_list_item(text, "psychology", "fear")
        desire = _first_nested_list_item(text, "bdi", "desire")
        item = {
            "kind": "characters",
            "id": character_id,
            "title": name,
            "subtitle": role,
            "path": _rel(path, root),
            "status": "major" if importance == "major" else "supporting",
            "badges": [importance, role],
            "excerpt": background or desire or "还没有可展示的角色背景摘要。",
            "facts": [
                {"label": "重要性", "value": importance},
                {"label": "当前欲望", "value": desire or "未填写"},
                {"label": "主要恐惧", "value": fear or "未填写"},
                {"label": "背景故事", "value": background or "未填写"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items


def _world_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for folder_name, label in [("canon", "世界规则"), ("plot", "情节资料")]:
        folder = root / folder_name
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".md", ".yaml", ".yml", ".json"}:
                continue
            if "candidates" in path.parts or path.name.endswith(".agent_tasks.md"):
                continue
            text = _display_text_for_path(path)
            if not text:
                continue
            item = {
                "kind": "world",
                "id": _safe_item_id(path, root),
                "title": _first_heading(_read_text(path)) or file_label(path),
                "subtitle": label,
                "path": _rel(path, root),
                "status": "formal",
                "badges": [label, path.suffix.lower().lstrip(".")],
                "excerpt": summarize_text(text, limit=220),
                "body": truncate_text(text, 3000),
                "facts": [{"label": "来源", "value": _rel(path, root)}],
            }
            items.append(_apply_overrides(item, overrides))
            if len(items) >= 80:
                return items
    return items


def _scene_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    folder = root / "scenes"
    if not folder.exists():
        return []
    items = []
    for path in sorted(folder.glob("*.yaml"))[:250]:
        text = _read_text(path)
        scene_id = scalar_from_yaml_text(text, "scene_id") or path.stem
        chapter_id = scalar_from_yaml_text(text, "chapter_id") or "未分章"
        goal = scalar_from_yaml_text(text, "scene_goal") or nested_scalar_from_yaml_text(text, "reader_experience", "reader_question")
        participants = list_from_yaml_text(text, "participants")
        target = scalar_from_yaml_text(text, "word_count_target") or "0"
        item = {
            "kind": "scenes",
            "id": scene_id,
            "title": _display_scene_name(scene_id),
            "subtitle": chapter_id,
            "path": _rel(path, root),
            "status": scalar_from_yaml_text(text, "status") or "planned",
            "badges": [chapter_id, f"目标 {target} 字" if target and target != "0" else "未绑定字数"],
            "excerpt": goal or "还没有场景目标。",
            "facts": [
                {"label": "章节", "value": chapter_id},
                {"label": "目标字数", "value": target if target != "0" else "未设置"},
                {"label": "参与者", "value": "、".join(participants) if participants else "未填写"},
                {"label": "读者问题", "value": nested_scalar_from_yaml_text(text, "reader_experience", "reader_question") or "未填写"},
                {"label": "承诺回报", "value": nested_scalar_from_yaml_text(text, "reader_experience", "promised_reward") or "未填写"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items


def _branch_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    folder = root / "branches"
    if not folder.exists():
        return []
    items = []
    for manifest in sorted(folder.glob("*/branch_manifest.json"))[:250]:
        payload = read_json_file(manifest)
        scene_id = str(payload.get("scene_id") or manifest.parent.name)
        selection_path = manifest.parent / "branch_selection.md"
        selection_text = _read_text(selection_path)
        selected = _selected_branch(selection_text)
        options = []
        for branch in payload.get("branches", []) if isinstance(payload.get("branches"), list) else []:
            if not isinstance(branch, dict):
                continue
            branch_id = str(branch.get("branch_id") or branch.get("id") or "")
            title = str(branch.get("title") or branch_id or "未命名分支")
            premise = str(branch.get("premise") or branch.get("summary") or "")
            risks = branch.get("risks") if isinstance(branch.get("risks"), list) else []
            options.append(
                {
                    "id": branch_id,
                    "label": title,
                    "summary": truncate_text(premise, 180),
                    "risk": "；".join(str(item) for item in risks[:3]),
                    "selected": bool(branch_id and branch_id == selected),
                }
            )
        item = {
            "kind": "branches",
            "id": scene_id,
            "title": f"{_display_scene_name(scene_id)}的剧情分支",
            "subtitle": "推演分支",
            "path": _rel(manifest, root),
            "status": "selected" if selected else "waiting_user_choice",
            "badges": [f"{len(options)} 个候选", f"已选 {selected}" if selected else "等待选择"],
            "excerpt": f"推荐分支：{payload.get('recommended_branch') or '未给出'}。正式进入编剧态前必须完成分支选择。",
            "options": options,
            "facts": [
                {"label": "场景", "value": scene_id},
                {"label": "推荐分支", "value": payload.get("recommended_branch") or "未给出"},
                {"label": "当前选择", "value": selected or "未选择"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    return items


def _style_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    active = active_project_style(root)
    items = []
    if active.get("style_id"):
        readiness = active.get("readiness") if isinstance(active.get("readiness"), dict) else {}
        item = {
            "kind": "style",
            "id": str(active.get("style_id")),
            "title": str(active.get("style_id")),
            "subtitle": "当前挂载文风",
            "path": str(active.get("project_style") or "style/active_style_skill.json"),
            "status": "ready" if readiness.get("ready") else "needs_review",
            "badges": ["最高优先级", "可正式生成" if readiness.get("ready") else "需补齐评测"],
            "excerpt": "文风会在表达层先于普通生成约束生效。",
            "facts": [
                {"label": "优先级", "value": active.get("priority") or "highest"},
                {"label": "是否就绪", "value": "是" if readiness.get("ready") else "否"},
                {"label": "挂载文件", "value": active.get("project_style") or "style/active_style_skill.json"},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    for prompt in sorted((root / "style").glob("**/style_prompt.md"))[:80]:
        text = _read_text(prompt)
        item = {
            "kind": "style",
            "id": _safe_item_id(prompt, root),
            "title": _first_heading(text) or file_label(prompt.parent),
            "subtitle": "文风提示词",
            "path": _rel(prompt, root),
            "status": "candidate",
            "badges": ["LLM-facing prompt", f"{len(markdown_to_display_text(text, limit=5000))} 字"],
            "excerpt": summarize_text(text, limit=240),
            "body": markdown_to_display_text(text, limit=2500),
            "facts": [{"label": "提示词文件", "value": _rel(prompt, root)}],
        }
        items.append(_apply_overrides(item, overrides))
    return items


def _review_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    folder = root / "reviews"
    if not folder.exists():
        return []
    paths = [path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".json"}]
    paths = sorted(paths, key=lambda path: path.stat().st_mtime, reverse=True)[:80]
    items = []
    for path in paths:
        text = _display_text_for_path(path)
        status = _review_status(path, text)
        item = {
            "kind": "reviews",
            "id": _safe_item_id(path, root),
            "title": _first_heading(_read_text(path)) or file_label(path),
            "subtitle": "审查证据",
            "path": _rel(path, root),
            "status": status,
            "badges": [status, path.suffix.lower().lstrip(".")],
            "excerpt": summarize_text(text, limit=220),
            "body": truncate_text(text, 3000),
            "facts": [{"label": "审查文件", "value": _rel(path, root)}],
        }
        items.append(_apply_overrides(item, overrides))
    return items


def _word_budget_items(root: Path, overrides: dict[str, object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    budget = root / "plot" / "word_budget" / "word_budget.json"
    if budget.exists():
        payload = read_json_file(budget)
        totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
        body = _display_text_for_path(root / "plot" / "word_budget" / "word_budget.md")
        item = {
            "kind": "word_budget",
            "id": "word_budget",
            "title": "长篇字数预算",
            "subtitle": "目标长度与剧情库存",
            "path": _rel(budget, root),
            "status": str(payload.get("status") or "unknown"),
            "badges": [str(payload.get("status") or "unknown"), f"{totals.get('chapter_count', 0)} 章", f"{totals.get('scene_count', 0)} 场"],
            "excerpt": summarize_text(body, limit=240) or "预算文件存在，但还没有可读报告。",
            "body": truncate_text(body, 3000),
            "facts": [
                {"label": "目标字数", "value": totals.get("target_words") or "未设置"},
                {"label": "章节数", "value": totals.get("chapter_count") or 0},
                {"label": "场景数", "value": totals.get("scene_count") or 0},
            ],
        }
        items.append(_apply_overrides(item, overrides))
    obligations = root / "plot" / "chapter_obligations"
    if obligations.exists():
        for path in sorted(obligations.glob("*.json"))[:80]:
            payload = read_json_file(path)
            if not payload:
                continue
            chapter_id = str(payload.get("chapter_id") or path.stem)
            item = {
                "kind": "word_budget",
                "id": f"chapter__{chapter_id}",
                "title": f"{chapter_id} 章节义务",
                "subtitle": "读者体验契约",
                "path": _rel(path, root),
                "status": str(payload.get("status") or "draft"),
                "badges": [str(payload.get("status") or "draft")],
                "excerpt": truncate_text(str(payload.get("chapter_function") or payload.get("ending_hook") or "章节义务等待平台 Agent 填写。"), 240),
                "facts": [
                    {"label": "章节功能", "value": payload.get("chapter_function") or "未填写"},
                    {"label": "章末钩子", "value": payload.get("ending_hook") or "未填写"},
                    {"label": "库存充分性", "value": payload.get("inventory_sufficiency") or "未填写"},
                ],
            }
            items.append(_apply_overrides(item, overrides))
    return items


def _load_overrides(root: Path) -> dict[str, object]:
    payload = read_json_file(root / "workflow" / "ui_overrides.json")
    items = payload.get("items") if isinstance(payload.get("items"), dict) else {}
    return items


def _apply_overrides(item: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    key = f"{item.get('kind')}:{item.get('id')}"
    record = overrides.get(key) if isinstance(overrides, dict) else None
    if not isinstance(record, dict):
        return item
    fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    if "display_title" in fields:
        item["title"] = str(fields["display_title"])
    if "display_summary" in fields:
        item["excerpt"] = str(fields["display_summary"])
    if "note" in fields:
        item["user_note"] = str(fields["note"])
    if "tags" in fields:
        tags = fields["tags"] if isinstance(fields["tags"], list) else [fields["tags"]]
        item["badges"] = list(item.get("badges", [])) + [str(tag) for tag in tags if str(tag).strip()]
    item["ui_overridden"] = True
    return item


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _display_text_for_path(path: Path) -> str:
    if not path.exists():
        return ""
    if path.suffix.lower() == ".json":
        payload = read_json_file(path)
        return _json_to_display_text(payload)
    return markdown_to_display_text(_read_text(path), limit=5000)


def _json_to_display_text(payload: dict[str, object]) -> str:
    if not payload:
        return ""
    lines = []
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)):
            lines.append(f"{_label(key)}：{value}")
        elif isinstance(value, list):
            shown = "；".join(str(item) for item in value[:5] if not isinstance(item, (dict, list)))
            if shown:
                lines.append(f"{_label(key)}：{shown}")
        elif isinstance(value, dict):
            brief = "；".join(f"{_label(k)}={v}" for k, v in list(value.items())[:4] if isinstance(v, (str, int, float, bool)))
            if brief:
                lines.append(f"{_label(key)}：{brief}")
    return truncate_text("\n".join(lines), 5000)


def _label(value: str) -> str:
    return str(value).replace("_", " ").replace("-", " ")


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""


def _scene_id_from_draft(path: Path) -> str:
    stem = path.stem
    if "-platform-agent" in stem:
        return stem.split("-platform-agent", 1)[0]
    if "_revision" in stem:
        return stem.split("_revision", 1)[0]
    return stem


def _scene_target(root: Path, scene_id: str) -> int:
    scene_path = root / "scenes" / f"{scene_id}.yaml"
    text = _read_text(scene_path)
    value = scalar_from_yaml_text(text, "word_count_target")
    try:
        return int(value or 0)
    except ValueError:
        return 0


def _display_scene_name(scene_id: str) -> str:
    return scene_id.replace("_", " ").replace("-", " ").strip() or "未命名场景"


def _first_nested_list_item(text: str, parent: str, key: str) -> str:
    parent_match = None
    for match in re.finditer(rf"(?m)^(\s*){parent}\s*:\s*$", text):
        parent_match = match
        break
    if not parent_match:
        return ""
    start = parent_match.end()
    block_lines = []
    for line in text[start:].splitlines():
        if line and not line.startswith(" ") and not line.startswith("\t"):
            break
        block_lines.append(line)
    return (list_from_yaml_text("\n".join(block_lines), key, limit=1) or [""])[0]


def _selected_branch(text: str) -> str:
    return scalar_from_yaml_text(text, "selected_branch")


def _review_status(path: Path, text: str) -> str:
    if path.suffix.lower() == ".json":
        payload = read_json_file(path)
        return str(payload.get("conclusion") or payload.get("status") or payload.get("final_recommendation") or "review")
    lowered = text.lower()
    if "conclusion: pass" in lowered or "结论：pass" in lowered or "结论: pass" in lowered:
        return "pass"
    if "pass_with_notes" in lowered:
        return "pass_with_notes"
    if "revise" in lowered or "修订" in text:
        return "revise"
    return "review"


def _safe_item_id(path: Path, root: Path) -> str:
    return _rel(path, root).replace("/", "__").replace("\\", "__").replace(".", "_")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
