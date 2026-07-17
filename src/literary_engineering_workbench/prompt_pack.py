"""Prompt pack builder for scene generation providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from string import Formatter
from typing import Any


DEFAULT_CONTEXT_LIMIT = 18000
DEFAULT_COMPOSITION_LIMIT = 14000
DEFAULT_STYLE_LIMIT = 6000

OUTPUT_CONTRACT = """模型输出必须使用以下 Markdown 结构：

## 正文候选

写入场景正文候选。正文必须遵守 canon、人物 BDI、背景故事隐性动因、场景编排包和文风 profile。

## 状态变化候选

### 新增事实候选

- 只列候选，不得声称已进入 canon。

### 人物状态变化

- 只列候选，等待人工确认。

### 关系变化

- 只列候选，等待人工确认。

### 伏笔变化

- 只列候选，等待人工确认。

### 需要人工确认

- 列出所有可能影响 canon、人物重大转折、主线分支或发布边界的事项。
"""


@dataclass(frozen=True)
class PromptPack:
    project_root: Path
    scene_path: Path
    context_path: Path
    composition_path: Path | None
    style_profile_path: Path | None
    system_prompt: str
    user_prompt: str
    sources: list[dict[str, Any]]


def build_scene_prompt_pack(
    project_root: Path,
    scene_path: Path,
    context_path: Path,
    composition: Path | None = None,
) -> PromptPack:
    """Render system/user prompts for a scene generation provider."""

    root = project_root.resolve()
    scene_path = _resolve(root, scene_path)
    context_path = _resolve(root, context_path)
    scene_id = scene_path.stem or "scene"
    default_composition = root / "drafts" / "compositions" / f"{scene_id}_composition.md"
    composition_path = _resolve(root, composition) if composition else default_composition
    if not composition_path.exists():
        composition_path = None
    style_profile_path = _find_style_asset(root)

    values = {
        "scene_id": scene_id,
        "scene_text": _read(scene_path),
        "context_text": _limit(_read(context_path), DEFAULT_CONTEXT_LIMIT),
        "composition_text": _limit(_read(composition_path), DEFAULT_COMPOSITION_LIMIT) if composition_path else "未找到场景创作编排包。若需要更稳的正文候选，请先运行 compose-scene。",
        "style_profile": _render_style_constraint(root, style_profile_path),
        "output_contract": OUTPUT_CONTRACT.strip(),
        "generated_at": _now(),
    }
    system_template = _load_template(root, "scene_generation_system.md")
    user_template = _load_template(root, "scene_generation_user.md")
    system_prompt = _render_template(system_template, values)
    user_prompt = _render_template(user_template, values)
    sources = _sources(root, scene_path, context_path, composition_path, style_profile_path)
    return PromptPack(
        project_root=root,
        scene_path=scene_path,
        context_path=context_path,
        composition_path=composition_path,
        style_profile_path=style_profile_path,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        sources=sources,
    )


def write_prompt_manifest(pack: PromptPack, output: Path, provider: str, model: str = "") -> Path:
    """Write a reproducible prompt manifest next to a generated candidate."""

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/prompt-pack/v0.1",
        "generated_at": _now(),
        "provider": provider,
        "model": model,
        "scene": _rel(pack.scene_path, pack.project_root),
        "context": _rel(pack.context_path, pack.project_root),
        "composition": _rel(pack.composition_path, pack.project_root) if pack.composition_path else "",
        "style_profile": _rel(pack.style_profile_path, pack.project_root) if pack.style_profile_path else "",
        "sources": pack.sources,
        "messages": [
            {"role": "system", "content": pack.system_prompt},
            {"role": "user", "content": pack.user_prompt},
        ],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def _load_template(root: Path, name: str) -> str:
    project_template = root / "prompts" / name
    if project_template.exists():
        return _read(project_template)
    bundled = _bundle_root() / "templates" / "prompts" / name
    if bundled.exists():
        return _read(bundled)
    raise FileNotFoundError(f"prompt template not found: prompts/{name}")


def _render_template(template: str, values: dict[str, str]) -> str:
    required = {field for _, field, _, _ in Formatter().parse(template) if field}
    missing = [field for field in sorted(required) if field not in values]
    if missing:
        raise KeyError(f"missing prompt variables: {', '.join(missing)}")
    return template.format_map(values).strip() + "\n"


def _sources(
    root: Path,
    scene_path: Path,
    context_path: Path,
    composition_path: Path | None,
    style_profile_path: Path | None,
) -> list[dict[str, Any]]:
    paths = [scene_path, context_path]
    if composition_path:
        paths.append(composition_path)
    if style_profile_path:
        paths.append(style_profile_path)
    return [
        {
            "path": _rel(path, root),
            "chars": len(_read(path)),
        }
        for path in paths
    ]


def _find_style_asset(root: Path) -> Path | None:
    mounted = _find_mounted_style_skill(root)
    if mounted:
        return mounted
    style_root = root / "style"
    candidates = [style_root / "style_prompt.md"]
    if style_root.exists():
        candidates.extend(sorted(style_root.glob("*/style_prompt.md"), key=lambda path: path.stat().st_mtime, reverse=True))
    candidates.append(style_root / "style-profile.md")
    if style_root.exists():
        candidates.extend(sorted(style_root.glob("*/style-profile.md"), key=lambda path: path.stat().st_mtime, reverse=True))
    for path in candidates:
        if path.exists():
            return path
    return None


def _find_mounted_style_skill(root: Path) -> Path | None:
    active = root / "style" / "active_style_skill.json"
    if not active.exists():
        return None
    try:
        payload = json.loads(active.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        return None
    path = root / prompt
    return path if path.exists() else None


def _render_style_constraint(root: Path, style_path: Path | None) -> str:
    if style_path is None:
        return "未找到挂载的 style skill 或 style/style-profile.md。若项目要求文风门禁，应先在文风学习页挂载 active style skill。"
    text = _limit(_read(style_path), DEFAULT_STYLE_LIMIT)
    active = root / "style" / "active_style_skill.json"
    if active.exists():
        try:
            payload = json.loads(active.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        return f"""# 已挂载文风 Style Skill（最高优先级）

- Style ID: `{payload.get("style_id", "")}`
- Priority: `{payload.get("priority", "highest")}`
- Mount: `{payload.get("mount_path", "")}`

硬规则：

- 本 Style Skill 在表达层拥有最高优先级：叙述距离、句法节奏、意象系统、心理呈现、对白密度和段落推进必须先服从它。
- 它不覆盖 canon、人物事实、剧情因果、用户明确约束和安全边界。
- 如文风要求与 canon/人物逻辑冲突，保留 canon/人物逻辑，并在“需要人工确认”中说明文风冲突。

## Style Skill Prompt

{text}
"""
    return text


def _bundle_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _limit(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[内容因提示词长度限制被截断。]"


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
