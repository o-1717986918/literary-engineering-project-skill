"""Agent-backed LLM-facing style prompt generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .agent_provider import run_agent_task
from .agent_schema import validate_agent_run


@dataclass(frozen=True)
class AgentStylePromptResult:
    profile_dir: Path
    run_dir: Path
    output_path: Path
    json_path: Path
    validation_path: Path
    provider: str
    generated_chars: int


def build_agent_style_prompt(
    profile_dir: Path,
    *,
    provider: str = "auto",
    output: Path | None = None,
    json_output: Path | None = None,
) -> AgentStylePromptResult:
    profile_root = profile_dir.resolve()
    if not profile_root.is_dir():
        raise FileNotFoundError(f"profile dir not found: {profile_root}")
    profile_path = profile_root / "style-profile.md"
    metrics_path = profile_root / "style_metrics.json"
    manifest_path = profile_root / "corpus_manifest.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"style profile not found: {profile_path}")
    if not metrics_path.exists():
        raise FileNotFoundError(f"style metrics not found: {metrics_path}")
    source_paths = [str(profile_path), str(metrics_path)]
    if manifest_path.exists():
        source_paths.append(str(manifest_path))
    dry_payload = _dry_style_prompt(source_paths)
    run_result = run_agent_task(
        profile_root,
        agent_id="style-prompt-builder",
        task="build-llm-facing-style-prompt",
        system_prompt=_system_prompt(),
        user_prompt=_user_prompt(profile_path, metrics_path, manifest_path),
        provider=provider,
        output_dir=profile_root / "agent_runs" / f"style_prompt_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        metadata={"schema_name": "style_prompt.v1", "source_paths": source_paths},
        dry_run_output=dry_payload,
    )
    validation = validate_agent_run(profile_root, run_dir=run_result.run_dir, schema_name="style_prompt.v1")
    parsed = json.loads(run_result.parsed_output_path.read_text(encoding="utf-8"))
    prompt_markdown = str(parsed.get("prompt_markdown", "")).strip()
    output_path = _resolve_output(profile_root, output, "style_prompt.md")
    json_path = _resolve_output(profile_root, json_output, "style_prompt.agent.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt_markdown + "\n", encoding="utf-8")
    parsed["agent_run_dir"] = str(run_result.run_dir)
    parsed["schema_validation"] = str(validation.validation_path)
    parsed["output"] = str(output_path)
    json_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return AgentStylePromptResult(
        profile_dir=profile_root,
        run_dir=run_result.run_dir,
        output_path=output_path,
        json_path=json_path,
        validation_path=validation.validation_path,
        provider=provider,
        generated_chars=len(prompt_markdown),
    )


def _system_prompt() -> str:
    return """You are a literary style prompt engineering agent.

Convert style profile evidence into an LLM-facing style constraint prompt. The output must be JSON using style_prompt.v1, and `prompt_markdown` must be directly usable as a generation prompt."""


def _user_prompt(profile_path: Path, metrics_path: Path, manifest_path: Path) -> str:
    manifest = manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else "missing"
    return f"""## style-profile.md

```markdown
{profile_path.read_text(encoding="utf-8")[:9000]}
```

## style_metrics.json

```json
{metrics_path.read_text(encoding="utf-8")[:6000]}
```

## corpus_manifest.yaml

```yaml
{manifest[:4000]}
```
"""


def _dry_style_prompt(source_paths: list[str]) -> dict[str, object]:
    prompt = """# LLM 文风约束提示词

## 使用身份

你是长篇虚构文本生成 LLM。你必须把风格 profile 转化为叙述距离、句法节奏、意象调度、心理呈现和对白动作的稳定约束。

## 核心约束

- 优先模仿叙事机制，不机械复用原文词句。
- 句法节奏应跟随人物注意力和场景压力变化。
- 背景故事只能作为隐性行为因果，不得直白解释。
- 所有风格选择都必须服从 canon、人物 BDI、场景目标和人工确认边界。

## 禁止倾向

- 不摘抄连续原文。
- 不把风格简化为高频词堆叠。
- 不把候选事实写成已确认事实。

## 输出自检

- 是否保持叙述距离稳定。
- 是否让意象服务主题和人物状态。
- 是否保留人工确认点。
"""
    return {
        "schema": "literary-engineering-workbench/style-prompt-agent/v1",
        "prompt_markdown": prompt,
        "constraints": ["叙述距离", "句法节奏", "意象调度", "心理呈现", "对白动作"],
        "avoid": ["原文摘抄", "高频词机械堆叠", "候选事实冒充 canon"],
        "source_paths": source_paths,
        "evaluation_plan": ["back-translation", "outline-expansion", "blind-review"],
        "risk_notes": ["dry-run prompt is a contract sample; use http-chat for model-authored refinement."],
    }


def _resolve_output(root: Path, value: Path | None, default_name: str) -> Path:
    if value is None:
        return root / default_name
    return value if value.is_absolute() else root / value
