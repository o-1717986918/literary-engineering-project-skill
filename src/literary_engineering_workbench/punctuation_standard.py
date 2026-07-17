"""Standard Chinese punctuation guardrails and lightweight linting."""

from __future__ import annotations

from dataclasses import dataclass
import re


PUNCTUATION_STANDARD_TITLE = "标准中文标点约束"

PUNCTUATION_STANDARD_PROMPT = """标准中文标点约束：

- 中文叙事、对白、报告和说明默认使用全角中文标点：，。；：？！、（）《》“”‘’。
- 中文正文中不要混用英文逗号、句号、冒号、分号、问号、感叹号或英文引号；英文缩写、URL、文件路径、代码、schema 字段和小数除外。
- 省略号统一使用“……”，不要使用“...”或连续句点；破折号统一使用“——”，不要用“--”或单个“—”表达停顿。
- 疑问号、感叹号通常只使用一个；避免“！！！”“？？？”“?!”等网感化连续标点，除非用户明确要求实验性文本或角色文本确有格式依据。
- 引号使用中文弯引号；完整引语的句末标点放在引号内，提示语和对白之间使用中文冒号、逗号或句号。
- 不要在中文标点前留空格，不要连续堆叠逗号、句号、顿号、冒号或分号。
- Markdown、JSON、YAML、代码块、文件路径、命令、URL、模型名和英文术语保留其必要 ASCII 符号，不做机械替换。
- 文风学习可以调整标点节奏和密度，但不能突破以上基础规范；如确需保留非标准标点，必须在审查或“需要人工确认”中说明理由。"""

PUNCTUATION_STANDARD_SHORT_RULE = (
    "中文用户可见文本必须遵守标准中文标点约束：中文正文用全角标点，省略号用“……”，"
    "破折号用“——”，避免英文标点混入中文句子、连续感叹/疑问符和中文标点前空格；"
    "代码、路径、URL、JSON/YAML/schema 字段除外。"
)


@dataclass(frozen=True)
class PunctuationIssue:
    rule: str
    severity: str
    message: str
    sample: str


CHINESE_RANGE = r"\u3400-\u4dbf\u4e00-\u9fff"


def lint_punctuation(text: str) -> list[PunctuationIssue]:
    """Return punctuation issues for Chinese prose-like text.

    This linter is intentionally conservative and skips fenced code blocks so
    Markdown contracts, JSON examples, paths, and commands are not normalized by
    accident. It is a gate for prose quality, not a full typography engine.
    """

    clean = _strip_fenced_code(text)
    checks: list[tuple[str, str, str, re.Pattern[str]]] = [
        (
            "ascii-punctuation-in-chinese",
            "medium",
            "中文句子中混入英文标点，应改为全角中文标点，除非是路径、URL、代码或英文术语。",
            re.compile(rf"(?<=[{CHINESE_RANGE}])[,.!?;:]|[,.!?;:](?=[{CHINESE_RANGE}])"),
        ),
        (
            "ascii-ellipsis",
            "medium",
            "省略号应使用“……”，不要使用“...”或连续英文句点。",
            re.compile(r"\.\.\.+"),
        ),
        (
            "ascii-dash",
            "low",
            "中文停顿破折号应使用“——”，不要使用“--”或单个“—”。",
            re.compile(rf"(?<=[{CHINESE_RANGE}])--(?=[{CHINESE_RANGE}])|(?<!—)—(?!—)"),
        ),
        (
            "western-quotes-in-chinese",
            "low",
            "中文引语应优先使用“”或‘’，不要在中文正文中混用英文直引号。",
            re.compile(rf"(?<=[{CHINESE_RANGE}])[\"']|[\"'](?=[{CHINESE_RANGE}])"),
        ),
        (
            "punctuation-spacing",
            "low",
            "中文标点前不应留空格。",
            re.compile(r"[ \t]+[，。！？；：、）】》”’]"),
        ),
        (
            "repeated-terminal-punctuation",
            "medium",
            "避免连续堆叠疑问号、感叹号或中英混合疑问/感叹标点。",
            re.compile(r"[!?！？]{2,}"),
        ),
        (
            "repeated-punctuation",
            "medium",
            "避免连续堆叠逗号、句号、顿号、冒号或分号。",
            re.compile(r"[，。；：、]{2,}"),
        ),
    ]
    issues: list[PunctuationIssue] = []
    for rule, severity, message, pattern in checks:
        match = pattern.search(clean)
        if match:
            issues.append(PunctuationIssue(rule, severity, message, _sample(clean, match.start(), match.end())))
    return issues


def render_punctuation_standard_for_prompt() -> str:
    return PUNCTUATION_STANDARD_PROMPT


def _strip_fenced_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)


def _sample(text: str, start: int, end: int, radius: int = 24) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    sample = text[left:right].replace("\n", " ").strip()
    if left:
        sample = "..." + sample
    if right < len(text):
        sample += "..."
    return sample
