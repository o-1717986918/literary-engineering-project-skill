from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from .context_packet import build_context_packet


@dataclass(frozen=True)
class DraftSceneResult:
    project_root: Path
    draft_path: Path
    context_path: Path
    scene_id: str


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _scene_id(scene_path: Path) -> str:
    return scene_path.stem or "scene"


def _extract_context_summary(context_text: str, max_chars: int = 1800) -> str:
    sections = []
    for heading in ["## 当前场景", "## 硬约束：Canon 与时间线", "## 人物状态", "## 风格约束"]:
        idx = context_text.find(heading)
        if idx < 0:
            continue
        next_idx = context_text.find("\n## ", idx + 1)
        section = context_text[idx: next_idx if next_idx >= 0 else len(context_text)].strip()
        sections.append(section)
    summary = "\n\n".join(sections)
    if len(summary) > max_chars:
        return summary[:max_chars] + "\n..."
    return summary or context_text[:max_chars]


def build_scene_draft(
    project_root: Path,
    scene: Path | None = None,
    context: Path | None = None,
    query: str = "",
    rebuild_context: bool = False,
    output: Path | None = None,
) -> DraftSceneResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    scene_path = root / "scenes" / "scene_0001.yaml" if scene is None else (scene if scene.is_absolute() else root / scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")

    sid = _scene_id(scene_path)
    context_path = context if context and context.is_absolute() else (
        root / context if context else root / "memory" / "context_packets" / f"{sid}.md"
    )
    if rebuild_context or not context_path.exists():
        context_result = build_context_packet(root, scene=scene_path, query=query, rebuild_index=True, output=context_path)
        context_path = context_result.output_path

    context_text = _read(context_path)
    if not context_text:
        raise FileNotFoundError(f"context packet not found or empty: {context_path}")

    draft_path = output if output and output.is_absolute() else (
        root / output if output else root / "drafts" / "scenes" / f"{sid}.md"
    )
    draft_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# 场景草稿工作台：{sid}

生成时间：{datetime.now(timezone.utc).isoformat()}

上下文包：`{context_path.relative_to(root).as_posix()}`
场景文件：`{scene_path.relative_to(root).as_posix()}`

## 使用规则

- 本文件是草稿工作台，不是最终正稿。
- 写作时必须遵守上下文包中的硬 canon、人物状态和风格约束。
- 写完正文后必须补全“状态变化”和“写回候选”。
- 审查未通过前，不得把正文移动到正稿。

## 上下文摘要

{_extract_context_summary(context_text)}

## 写作指令

1. 先确认本场景输入状态和目标。
2. 让人物行动来自当前 BDI，不为剧情方便强行转向。
3. 背景故事只作为隐性行为因果，通过选择、回避、误判、语气和关系压力体现，不要在正文中直接说明。
4. 场景必须产生可记录的输出状态。
5. 文风 profile 是约束，不是表面词汇模仿。
6. 中文正文必须使用标准中文标点：全角逗号句号问号感叹号，省略号用“……”，破折号用“——”，避免中英标点混用和连续感叹/疑问符。
7. 新增事实只列为候选，等待人工确认。

## 正文草稿

<!-- 在这里写入场景正文。 -->

## 状态变化

### 新增事实候选

- 

### 人物状态变化

- 

### 关系变化

- 

### 伏笔变化

- 

### 需要人工确认

- 

## 自检

- [ ] 未违背硬 canon。
- [ ] 人物行动符合当前 BDI。
- [ ] 背景故事没有被直白交代，只转化为行为和潜台词。
- [ ] 场景有明确冲突和输出状态。
- [ ] 文风约束被执行。
- [ ] 标点符合标准中文标点约束，没有中英标点混用、错误省略号或错误破折号。
- [ ] 新事实已列入候选而非直接确认为 canon。
"""
    draft_path.write_text(content, encoding="utf-8")
    return DraftSceneResult(project_root=root, draft_path=draft_path, context_path=context_path, scene_id=sid)


def extract_draft_body(text: str) -> str:
    match = re.search(r"## 正文草稿\s*(.*?)(?=\n## 状态变化|\Z)", text, re.S)
    if not match:
        return ""
    body = re.sub(r"<!--.*?-->", "", match.group(1), flags=re.S).strip()
    return body
