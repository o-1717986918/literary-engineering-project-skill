"""Detect and describe common AI-ish prose habits in generated fiction."""

from __future__ import annotations

from dataclasses import dataclass
import re


ANTI_AI_STYLE_PROMPT = """## 降低 AI 腔与模板化痕迹

- 避免机械对照句式。不要高频使用“不是……而是……”“并非……而是……”“与其说……不如说……”。只有在人物认知确实发生二分判断时才使用，并且同一场景最多保留一次。
- 避免抽象总结代替具体叙事。少用“某种意义、答案、真相、命运、存在、本身、这一刻、仿佛、像是”等把场景拔高成泛哲理的表达；优先写动作、物件、空间、视线和信息差。
- 避免解释性心理标签。不要反复写“他知道/她明白/他意识到”，应把认知变化转化为选择、停顿、误判、回避、语气和动作。
- 避免模板化转折和收束。少用“然而、于是、然后、突然、最终、此刻”串接段落；让转折来自因果、场景物理变化、人物目标冲突或已埋线索的回响。
- 避免对称排比腔。不要用连续的“不是 A，而是 B；不是 C，而是 D”或抽象名词排比制造庄重感。文学节奏应来自观察顺序、句长变化和情绪压力。
- 避免全知解释腔。不要把主题、人物动机、世界观意义直接说透；优先保留可被读者推断的缝隙。
- 避免结尾金句化。场景收束应落在动作结果、关系变化、信息揭示或悬念上，不用空泛判断句替代戏剧变化。"""

ANTI_AI_STYLE_SHORT_RULE = (
    "降低 AI 腔：限制“不是……而是……”等机械对照，避免抽象总结、解释性心理标签、"
    "模板化转折、对称排比、全知说教和结尾金句化。"
)


@dataclass(frozen=True)
class AIStyleIssue:
    rule: str
    severity: str
    message: str
    sample: str = ""


def lint_ai_style(text: str) -> list[AIStyleIssue]:
    clean = _strip_markdown(text)
    issues: list[AIStyleIssue] = []
    issues.extend(_contrast_frame_issues(clean))
    issues.extend(_abstract_summary_issues(clean))
    issues.extend(_explanatory_mind_issues(clean))
    issues.extend(_slogan_ending_issues(clean))
    return issues


def _contrast_frame_issues(text: str) -> list[AIStyleIssue]:
    patterns = [
        r"不是[^。！？!?；;\n]{1,40}?而是",
        r"不是[^。！？!?；;\n]{1,40}?是",
        r"并非[^。！？!?；;\n]{1,40}?而是",
        r"与其说[^。！？!?；;\n]{1,40}?不如说",
    ]
    hits: list[str] = []
    for pattern in patterns:
        hits.extend(re.findall(pattern, text))
    if len(hits) < 2:
        return []
    return [
        AIStyleIssue(
            "mechanical-contrast-frame",
            "medium",
            "机械对照句式密度过高，容易形成 AI 腔；请减少“不是……而是……”等二分解释句。",
            _sample(text, hits[0]),
        )
    ]


def _abstract_summary_issues(text: str) -> list[AIStyleIssue]:
    terms = [
        "某种意义",
        "某种",
        "一种",
        "答案",
        "真相",
        "命运",
        "存在",
        "本身",
        "这一刻",
        "此刻",
        "仿佛",
        "像是",
    ]
    hits = [term for term in terms for _ in range(text.count(term))]
    if len(hits) < 8:
        return []
    return [
        AIStyleIssue(
            "abstract-summary-density",
            "medium",
            "抽象总结和氛围词密度偏高，可能用概念替代了具体叙事。",
            _first_present_sample(text, terms),
        )
    ]


def _explanatory_mind_issues(text: str) -> list[AIStyleIssue]:
    patterns = [
        r"[他她它](?:知道|明白|意识到|发现|觉得)",
        r"[他她它]突然(?:知道|明白|意识到|发现|觉得)",
        r"[他她它]终于(?:知道|明白|意识到|发现|觉得)",
    ]
    hits: list[str] = []
    for pattern in patterns:
        hits.extend(re.findall(pattern, text))
    if len(hits) < 4:
        return []
    return [
        AIStyleIssue(
            "explanatory-psychology-overuse",
            "medium",
            "解释性心理标签过多；请用选择、动作、停顿、回避和对白潜台词呈现认知变化。",
            _sample(text, hits[0]),
        )
    ]


def _slogan_ending_issues(text: str) -> list[AIStyleIssue]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    if not paragraphs:
        return []
    tail = paragraphs[-1]
    if len(tail) > 90:
        return []
    if re.search(r"(这就是|那就是|终于明白|真正的|唯一的|不是.+而是|答案|真相|命运|意义)", tail):
        return [
            AIStyleIssue(
                "slogan-like-ending",
                "low",
                "场景结尾有金句化或主题直说倾向；优先落在动作结果、关系变化、信息揭示或悬念上。",
                tail[:80],
            )
        ]
    return []


def _strip_markdown(text: str) -> str:
    lines = []
    in_fence = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^#{1,6}\s+", line):
            continue
        if line.startswith("- ["):
            continue
        lines.append(raw_line)
    return "\n".join(lines)


def _sample(text: str, hit: str) -> str:
    idx = text.find(hit)
    if idx < 0:
        return hit[:80]
    start = max(0, idx - 24)
    end = min(len(text), idx + len(hit) + 36)
    return text[start:end].strip()


def _first_present_sample(text: str, terms: list[str]) -> str:
    positions = [(text.find(term), term) for term in terms if text.find(term) >= 0]
    if not positions:
        return ""
    _, term = min(positions)
    return _sample(text, term)
