"""Build LLM-facing style constraint prompts from a style profile."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

from .model_config import MODEL_PROVIDER_CHOICES, get_model_settings, resolve_model_provider
from .punctuation_standard import PUNCTUATION_STANDARD_PROMPT


STYLE_PROMPT_PROVIDERS = MODEL_PROVIDER_CHOICES


@dataclass(frozen=True)
class StylePromptResult:
    profile_dir: Path
    output_path: Path
    manifest_path: Path
    provider: str
    generated_chars: int


def build_style_prompt(
    profile_dir: Path,
    provider: str = "auto",
    output: Path | None = None,
    manifest_output: Path | None = None,
) -> StylePromptResult:
    """Generate an LLM-facing style constraint prompt from compiled style assets."""

    profile_root = profile_dir.resolve()
    if not profile_root.is_dir():
        raise FileNotFoundError(f"profile dir not found: {profile_root}")
    resolved_provider = resolve_model_provider(provider, purpose="style prompt generation")

    profile_path = profile_root / "style-profile.md"
    metrics_path = profile_root / "style_metrics.json"
    manifest_path = profile_root / "corpus_manifest.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"style profile not found: {profile_path}")
    if not metrics_path.exists():
        raise FileNotFoundError(f"style metrics not found: {metrics_path}")

    messages = _messages(profile_path, metrics_path, manifest_path)
    body = _generate(resolved_provider, messages)
    rendered = _render_style_prompt(resolved_provider, body)
    output_path = _resolve(profile_root, output, profile_root / "style_prompt.md")
    prompt_manifest_path = _resolve(profile_root, manifest_output, profile_root / "style_prompt.prompt.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    prompt_manifest = {
        "schema": "literary-engineering-workbench/style-prompt/v0.1",
        "generated_at": _now(),
        "provider": resolved_provider,
        "requested_provider": provider,
        "model": _model_label(resolved_provider),
        "profile_dir": str(profile_root),
        "style_profile": str(profile_path),
        "style_metrics": str(metrics_path),
        "corpus_manifest": str(manifest_path) if manifest_path.exists() else "",
        "output": str(output_path),
        "messages": messages,
        "guardrails": [
            "本文件是供 LLM 使用的文风约束提示词，不是原文摘抄。",
            "文风标点节奏必须建立在标准中文标点约束之上。",
            "精确模仿仅限公版或授权语料；其他语料只抽象叙事机制。",
            "后续回译、扩写和盲评应审查本提示词是否让 LLM 稳定复现目标风格机制。",
        ],
    }
    prompt_manifest_path.write_text(json.dumps(prompt_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return StylePromptResult(
        profile_dir=profile_root,
        output_path=output_path,
        manifest_path=prompt_manifest_path,
        provider=resolved_provider,
        generated_chars=len(rendered),
    )


def _messages(profile_path: Path, metrics_path: Path, manifest_path: Path) -> list[dict[str, str]]:
    profile_text = _read(profile_path)
    metrics_text = _read(metrics_path)
    manifest_text = _read(manifest_path) if manifest_path.exists() else "未找到 corpus_manifest.yaml。"
    system = """你是文学工程工作台的文风约束提示词编译器。

你的输出不是评论文章，也不是风格报告，而是“供另一个 LLM 写作时直接使用的文风约束提示词”。

要求：

- 把 profile 和 metrics 转译成可执行的写作约束。
- 约束必须覆盖叙述距离、句法节奏、标点节奏、感官意象、心理描写、对白比例、禁忌倾向和自检规则。
- 标点部分必须区分“风格节奏”和“基础规范”：可以学习密度、停顿和句式，但不得输出中英标点混用、错误省略号、错误破折号、密集碎句、长逗号链、破折号滥用或机械转折词堆叠。
- 不要把作者风格简化为“句号很多”“破折号很多”“但是/然而很多”。必须说明句号、逗号、分号、破折号和转折词分别服务什么叙事功能。
- 不摘抄原文，不制造不可验证的作者论断。
- 精确复现只适用于公版或授权语料；否则写成高层技法约束。
- 输出 Markdown，只输出提示词正文，不解释生成过程。
"""
    user = f"""请根据以下风格 profile、统计指标和语料 manifest，生成一份可直接注入 LLM 的文风约束提示词。

输出必须包含：

## 使用身份
## 核心风格机制
## 句法与节奏约束
## 叙述距离与心理呈现
## 意象和感官调度
## 对白与动作约束
## 标点规范边界
## 禁止倾向
## 输出自检

### 标准中文标点约束

{PUNCTUATION_STANDARD_PROMPT}

### style-profile.md

{profile_text}

### style_metrics.json

```json
{metrics_text}
```

### corpus_manifest.yaml

```yaml
{manifest_text}
```
"""
    return [{"role": "system", "content": system.strip()}, {"role": "user", "content": user.strip()}]


def _generate(provider: str, messages: list[dict[str, str]]) -> str:
    if provider == "dry-run":
        return _dry_run_prompt(messages)
    if provider == "http-chat":
        return _http_chat(messages)
    raise ValueError(f"unknown style prompt provider: {provider}")


def _dry_run_prompt(messages: list[dict[str, str]]) -> str:
    user = messages[-1]["content"]
    excerpt = " ".join(user.split())[:1400]
    return f"""## 使用身份

你是一个遵守文学工程约束的长篇虚构文本生成 LLM。你必须依据本文风约束提示词生成候选正文，而不是复述语料、解释理论或确认 canon。

## 核心风格机制

- 先维持 profile 中的叙述距离、句法节奏和感官倾向，再处理局部词汇。
- 文风相似来自叙事机制、节奏、意象组织和心理呈现，不来自机械复用高频词。
- 所有风格选择必须服务当前项目 canon、人物 BDI、场景目标和冲突压力。

## 句法与节奏约束

- 句长、段长和标点节奏应参考 style_metrics，但不能机械复刻标点表面频率。
- 标点节奏必须建立在标准中文标点和文学节奏之上：中文正文使用全角标点，省略号用“……”，破折号用“——”，不要混用英文标点、连续堆叠感叹/疑问符、密集碎句、长逗号链或破折号滥用。
- 句号用于语义、镜头或心理落点；逗号用于未完成的动作、感知、心理和因果关系；分号用于并列层级；破折号只用于打断、插入、骤变或强解释性补充。
- 转折优先由动作、意象、视线变化、信息差和因果推进完成，少用“但是、然而、于是、然后、突然”式机械接榫。
- 长短句交替必须配合人物注意力变化、场景压迫和情绪拐点。
- 不要为了模仿而堆叠复杂句；节奏必须让事件推进更清晰。

## 叙述距离与心理呈现

- 心理描写密度应参考 profile 的 thought_density。
- 人物判断通过迟疑、回避、误判、沉默和动作折返表现，避免说明书式内心剖白。
- 叙述者态度要稳定，不在同一场景中随意从冷静观察跳到夸张评判。

## 意象和感官调度

- 优先使用 profile 中占比最高的感官通道组织场景。
- 意象必须与主题、人物状态和场景空间绑定，不作为孤立装饰。
- 同一意象可重复，但每次重复应带来信息、情绪或关系的变化。

## 对白与动作约束

- 对白比例参考 dialogue_density；对白应带有信息差、遮掩和关系压力。
- 动作描写必须体现人物目标和道德边界。
- 背景故事只作为隐性行为因果，不得直白解释为设定段。

## 禁止倾向

- 不摘抄或改写原文连续片段。
- 不把风格简化为几个高频字词或固定比喻。
- 不为追求文风牺牲 canon、一致性、人物逻辑和场景输出状态。
- 不把候选事实写成已确认事实。

## 输出自检

- 句法节奏是否接近 profile，而不是只换词。
- 感官通道是否稳定服务场景目标。
- 心理描写和对白密度是否与 profile 相容。
- 标点是否符合标准中文标点与文学节奏约束，同时保留了 profile 所需的叙事功能，而不是机械复制标点频率。
- 是否避免复制原文连续表达。
- 是否保留了所有需要人工确认的 canon、人物和伏笔变化。

<!-- dry-run evidence: {excerpt} -->
"""


def _http_chat(messages: list[dict[str, str]]) -> str:
    settings = get_model_settings(default_temperature=0.4, default_max_tokens=2200)
    if not settings.api_base or not settings.model:
        raise RuntimeError(
            "style-prompt http-chat provider requires model config. Set LEW_MODEL_API_BASE and LEW_MODEL_NAME, "
            "or configure the global config file. Set LEW_MODEL_API_KEY, the configured api_key_env, or a saved profile api_key if needed."
        )
    if not settings.api_key:
        raise RuntimeError(
            f"style-prompt http-chat provider requires an API key. Set LEW_MODEL_API_KEY, {settings.api_key_env}, or save api_key in the active profile."
        )
    payload = {
        "model": settings.model,
        "messages": messages,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.api_key}"}
    req = request.Request(_chat_url(settings.api_base), data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=settings.timeout) as response:
            response_text = response.read().decode("utf-8", errors="ignore")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")[:800]
        raise RuntimeError(f"style-prompt provider request failed: HTTP {exc.code}. {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"style-prompt provider request failed: {exc.reason}") from exc
    data = json.loads(response_text)
    return _extract_chat_text(data)


def _render_style_prompt(provider: str, body: str) -> str:
    return f"""# LLM 文风约束提示词

- Provider：`{provider}`
- Generated At：{_now()}

## 使用边界

- 本文件是供 LLM 写作时注入的文风约束提示词。
- 它约束叙事机制、句法节奏、意象系统和心理呈现，不负责确认 canon。
- 回译、扩写和盲评评测应审查“本提示词是否有效”，而不是只审查统计报告。

{body.strip()}
"""


def _chat_url(api_base: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _extract_chat_text(data: dict[str, object]) -> str:
    if isinstance(data.get("output_text"), str):
        return str(data["output_text"])
    if isinstance(data.get("content"), str):
        return str(data["content"])
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return str(message["content"])
            if isinstance(first.get("text"), str):
                return str(first["text"])
    raise RuntimeError("style-prompt provider response did not contain generated text")


def _resolve(root: Path, value: Path | None, default: Path) -> Path:
    if value is None:
        return default
    return value if value.is_absolute() else root / value


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _model_label(provider: str) -> str:
    if provider == "http-chat":
        return get_model_settings().model
    return provider


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
