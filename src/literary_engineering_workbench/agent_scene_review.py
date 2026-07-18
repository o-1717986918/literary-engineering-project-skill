"""LLM/Agent-backed scene review artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .anti_ai_style import lint_ai_style, render_ai_style_lint_block
from .agent_provider import run_agent_task
from .agent_schema import validate_agent_run


@dataclass(frozen=True)
class AgentSceneReviewResult:
    project_root: Path
    scene_id: str
    run_dir: Path
    report_path: Path
    json_path: Path
    validation_path: Path
    conclusion: str


def review_scene_with_agent(
    project_root: Path,
    *,
    scene: Path | None = None,
    draft: Path | None = None,
    provider: str = "auto",
    output: Path | None = None,
    json_output: Path | None = None,
) -> AgentSceneReviewResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    scene_path = _resolve_scene(root, scene)
    scene_id = scene_path.stem
    draft_path = _resolve_draft(root, scene_id, draft)
    context_path = root / "memory" / "context_packets" / f"{scene_id}.md"
    style_prompt_path = _first_existing(_style_source_candidates(root))
    source_paths = [_rel_str(scene_path, root)]
    if draft_path.exists():
        source_paths.append(_rel_str(draft_path, root))
    if context_path.exists():
        source_paths.append(_rel_str(context_path, root))
    if style_prompt_path and style_prompt_path.exists():
        source_paths.append(_rel_str(style_prompt_path, root))

    scene_text = _read(scene_path)
    draft_text = _read(draft_path) if draft_path.exists() else ""
    context_text = _read(context_path) if context_path.exists() else ""
    style_text = _read(style_prompt_path) if style_prompt_path else ""
    dry_payload = _dry_scene_review(scene_id, draft_text, source_paths)
    run_result = run_agent_task(
        root,
        agent_id="scene-reviewer",
        task=f"review-scene:{scene_id}",
        system_prompt=_system_prompt(),
        user_prompt=_user_prompt(scene_text, draft_text, context_text, style_text, source_paths),
        provider=provider,
        metadata={"schema_name": "scene_review.v1", "scene_id": scene_id, "source_paths": source_paths},
        dry_run_output=dry_payload,
    )
    validation = validate_agent_run(root, run_dir=run_result.run_dir, schema_name="scene_review.v1")
    parsed = json.loads(run_result.parsed_output_path.read_text(encoding="utf-8"))
    parsed["agent_run_dir"] = _rel_str(run_result.run_dir, root)
    parsed["schema_validation"] = _rel_str(validation.validation_path, root)

    report_path = _resolve_output(root, output, "reviews", "agent", f"{scene_id}_scene_review.md")
    json_path = _resolve_output(root, json_output, "reviews", "agent", f"{scene_id}_scene_review.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(parsed, validation.status), encoding="utf-8")
    return AgentSceneReviewResult(
        project_root=root,
        scene_id=scene_id,
        run_dir=run_result.run_dir,
        report_path=report_path,
        json_path=json_path,
        validation_path=validation.validation_path,
        conclusion=str(parsed.get("conclusion", "")),
    )


def _system_prompt() -> str:
    return """You are a literary engineering scene review agent.

Review the scene as a workbench artifact, not as final praise. Judge character logic, canon safety, plot movement, mounted style adherence, punctuation rhythm, deterministic Style Lint evidence, and revision actions. Output JSON only using schema scene_review.v1, including a structured style_adherence object."""


def _user_prompt(scene_text: str, draft_text: str, context_text: str, style_text: str, source_paths: list[str]) -> str:
    return f"""Source paths: {source_paths}

{render_ai_style_lint_block(draft_text)}

## Scene YAML

```yaml
{scene_text[:6000]}
```

## Draft

```markdown
{draft_text[:9000] or "Draft missing."}
```

## Context Packet

```markdown
{context_text[:6000] or "Context packet missing."}
```

## Style Prompt / Profile

```markdown
{style_text[:5000] or "Style prompt/profile missing."}
```
"""


def _dry_scene_review(scene_id: str, draft_text: str, source_paths: list[str]) -> dict[str, object]:
    has_body = bool(draft_text.strip()) and "<!-- 在这里写入场景正文。 -->" not in draft_text
    lint_issues = lint_ai_style(draft_text) if has_body else []
    blocking_lint = [issue for issue in lint_issues if issue.severity not in {"low"}]
    conclusion = "revise_required" if not has_body or blocking_lint else "pass_with_notes"
    warnings = [] if has_body else ["场景草稿缺少可审查正文，需先补正文或提升生成候选。"]
    warnings.extend(f"Style lint: {issue.rule} - {issue.message}" for issue in blocking_lint)
    style_source = _style_source_label(source_paths)
    style_status = "pass_with_notes" if style_source and has_body else ("revise_required" if style_source else "not_applicable")
    style_revision_actions = (
        ["真实平台审查需确认挂载文风已经影响叙述距离、句法节奏、意象系统、对白语气和标点停顿。"] if style_source else []
    )
    lint_revision_actions = [
        f"按确定性 Style Lint 逐句复核 `{issue.sample}`，修订 {issue.rule}，不得用脚本直接删改造成语义反转。"
        for issue in blocking_lint
        if issue.sample
    ]
    return {
        "schema": "literary-engineering-workbench/scene-review-agent/v1",
        "scene_id": scene_id,
        "conclusion": conclusion,
        "summary": "dry-run scene reviewer preserved the review contract and source trace.",
        "blocking_issues": [],
        "warnings": warnings,
        "revision_actions": ["保留人工确认点；不要把候选事实直接写入 canon。"] + lint_revision_actions,
        "character_logic": [
            {
                "character": "all",
                "assessment": "检查人物 BDI、背景故事隐性动因和当前状态是否共同支持行动。",
            }
        ],
        "canon_risks": [],
        "style_notes": [
            "后续真实模型审查应核对 style_prompt.md 是否影响句法、叙述距离和意象调度。",
            *[f"确定性 Style Lint 检出 {issue.rule}: {issue.sample}" for issue in lint_issues],
        ],
        "style_adherence": {
            "status": style_status,
            "style_profile": style_source or "n/a",
            "evidence": ["dry-run 仅保持审查契约；真实平台 agent 需要引用正文证据。"] if style_source else [],
            "deviations": [],
            "revision_actions": style_revision_actions,
        },
        "source_paths": source_paths,
        "agent_confidence": "dry-run",
        "next_gate": "schema_validation_then_human_review",
    }


def _render_report(payload: dict[str, object], validation_status: str) -> str:
    lines = [
        f"# Agent 场景审查：{payload.get('scene_id', '')}",
        "",
        f"- 结论：`{payload.get('conclusion', '')}`",
        f"- Schema：`{validation_status}`",
        f"- Agent Run：`{payload.get('agent_run_dir', '')}`",
        "",
        "## 摘要",
        "",
        str(payload.get("summary", "")),
        "",
        "## 修订动作",
        "",
    ]
    for item in payload.get("revision_actions", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## 风险", ""])
    for item in payload.get("blocking_issues", []) or []:
        lines.append(f"- BLOCKING: {item}")
    for item in payload.get("warnings", []) or []:
        lines.append(f"- WARNING: {item}")
    return "\n".join(lines) + "\n"


def _resolve_scene(root: Path, scene: Path | None) -> Path:
    path = root / "scenes" / "scene_0001.yaml" if scene is None else (scene if scene.is_absolute() else root / scene)
    if not path.exists():
        raise FileNotFoundError(f"scene file not found: {path}")
    return path.resolve()


def _resolve_draft(root: Path, scene_id: str, draft: Path | None) -> Path:
    if draft is None:
        return root / "drafts" / "scenes" / f"{scene_id}.md"
    return draft if draft.is_absolute() else root / draft


def _resolve_output(root: Path, value: Path | None, *default_parts: str) -> Path:
    if value is None:
        return root.joinpath(*default_parts)
    return value if value.is_absolute() else root / value


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _style_source_candidates(root: Path) -> list[Path]:
    candidates = [
        root / "style" / "active_style_skill.json",
        root / "style" / "style_prompt.md",
        root / "style" / "demo-author" / "style_prompt.md",
        root / "style" / "style-profile.md",
    ]
    active = root / "style" / "active_style_skill.json"
    if active.exists():
        try:
            payload = json.loads(active.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        for key in ("prompt", "style_skill", "mount_path"):
            value = str(payload.get(key) or "").strip()
            if not value:
                continue
            path = root / value
            if path.is_dir():
                candidates.extend([path / "prompt.md", path / "style_skill.json", path / "style-profile.md"])
            else:
                candidates.append(path)
    return candidates


def _style_source_label(source_paths: list[str]) -> str:
    for value in source_paths:
        normalized = value.replace("\\", "/")
        if normalized.startswith("style/") and (
            "active_style_skill.json" in normalized
            or "style_prompt.md" in normalized
            or "prompt.md" in normalized
            or "style-profile.md" in normalized
        ):
            return normalized
    return ""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
