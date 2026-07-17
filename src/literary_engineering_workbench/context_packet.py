from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from .memory_index import build_memory_index, search_memory


@dataclass(frozen=True)
class ContextPacketResult:
    project_root: Path
    output_path: Path
    retrieval_count: int


def _read(path: Path, missing: str = "") -> str:
    if not path.exists():
        return missing
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _first_existing(root: Path, candidates: list[str]) -> str:
    parts = []
    for rel in candidates:
        text = _read(root / rel)
        if text:
            parts.append(f"### {rel}\n\n{text}")
    return "\n\n".join(parts) if parts else "无。"


def _extract_scene_id(scene_path: Path) -> str:
    stem = scene_path.stem
    return stem or "scene"


def _query_from_scene(scene_text: str, extra_query: str) -> str:
    keys = []
    for key in [
        "scene_goal",
        "external",
        "internal",
        "location",
        "participants",
        "style_constraints",
    ]:
        pattern = rf"(?m)^\s*{re.escape(key)}:\s*(.+?)\s*$"
        match = re.search(pattern, scene_text)
        if match and match.group(1).strip() not in {"", "[]"}:
            keys.append(match.group(1).strip())
    if extra_query:
        keys.append(extra_query)
    keys.append(scene_text[:1200])
    return "\n".join(keys)


def _character_section(root: Path) -> str:
    chars_dir = root / "characters"
    if not chars_dir.exists():
        return "无人物档案。"
    files = [p for p in sorted(chars_dir.glob("*.yaml")) if not p.name.startswith("_")]
    if not files:
        template = _read(chars_dir / "_template.yaml")
        return "尚无正式人物档案。以下是人物模板，生成前应先补齐主要人物：\n\n```yaml\n" + template + "\n```"
    sections = []
    for path in files:
        sections.append(f"### {path.name}\n\n```yaml\n{_read(path)}\n```")
    return "\n\n".join(sections)


def _retrieval_section(hits) -> str:
    if not hits:
        return "未检索到相关软记忆。"
    sections = []
    for i, hit in enumerate(hits, 1):
        text = hit.text
        if len(text) > 900:
            text = text[:900] + "\n..."
        sections.append(
            f"### {i}. {hit.source} (score={hit.score:.1f}, kind={hit.kind})\n\n{text}"
        )
    return "\n\n".join(sections)


def build_context_packet(
    project_root: Path,
    scene: Path | None = None,
    query: str = "",
    top_k: int = 8,
    rebuild_index: bool = False,
    output: Path | None = None,
) -> ContextPacketResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    scene_path = (root / "scenes" / "scene_0001.yaml") if scene is None else (scene if scene.is_absolute() else root / scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")

    index_path = root / "memory" / "index.json"
    if rebuild_index or not index_path.exists():
        build_memory_index(root)

    scene_text = _read(scene_path)
    retrieval_query = _query_from_scene(scene_text, query)
    hits = search_memory(root, retrieval_query, top_k=top_k)

    scene_id = _extract_scene_id(scene_path)
    output_path = output or root / "memory" / "context_packets" / f"{scene_id}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# 场景上下文包：{scene_id}

生成时间：{datetime.now(timezone.utc).isoformat()}

## 使用规则

- 本文件是写作前工作记忆，不是正稿。
- Canon、人物档案和时间线是硬约束。
- “软记忆检索”只提供参考，不得覆盖硬事实。
- `background_story` 是人物的隐性行为因果，只能影响选择、回避、误判和语气，不应在正文中直白说明。
- 写作完成后必须输出写回计划。

## 项目配置

```yaml
{_read(root / "project.yaml")}
```

## 当前场景

来源：`{scene_path.relative_to(root).as_posix()}`

```yaml
{scene_text}
```

## 硬约束：Canon 与时间线

{_first_existing(root, [
    "canon/world_rules.yaml",
    "canon/timeline.yaml",
    "canon/facts.json",
    "canon/forbidden_changes.yaml",
])}

## 人物状态

{_character_section(root)}

## 剧情状态

{_first_existing(root, [
    "plot/outline.md",
    "plot/foreshadowing.csv",
    "plot/conflict_matrix.md",
])}

## 风格约束

{_first_existing(root, [
    "style/style-profile.md",
])}

## 软记忆检索

查询依据：当前场景字段 + 用户补充 query。

{_retrieval_section(hits)}

## 写作任务

请基于以上上下文生成或推演当前场景。生成时必须：

1. 不违背硬 canon。
2. 人物行动符合 BDI 和当前信息差。
3. 人物背景故事只能作为隐性动因，不得变成解释性设定段落。
4. 场景输出必须包含状态变化。
5. 风格遵守 profile，而不是只模仿表面词汇。
6. 若需要新增事实，写入候选，不直接确认为 canon。

## 写回清单

生成完成后输出：

- 新增事实候选。
- 人物状态变化。
- 关系变化。
- 伏笔变化。
- 需要进入软记忆索引的正文片段。
- 需要人工确认的重大变更。
"""

    output_path.write_text(content, encoding="utf-8")
    return ContextPacketResult(project_root=root, output_path=output_path, retrieval_count=len(hits))
