"""Detect and describe common AI-ish prose habits in generated fiction."""

from __future__ import annotations

from dataclasses import dataclass
import re


ANTI_AI_STYLE_PROMPT = """## 降低 AI 腔与模板化痕迹

- 默认禁用机械对照句式。未经用户或已挂载 Style Skill 明确授权，不使用“不是……而是……”“并非……而是……”“与其说……不如说……”，也不使用“不是……——是……”“不是……。是……”“不是……，是……”等用破折号、句号或逗号替代“而是”的变体。
- 若 Style Skill 明确把否定-纠偏结构列为核心修辞，只能在人物认知二分、叙述者纠正读者预期、信息反转或讽刺顿挫确有需要时使用；同一场景原则上最多一次，并且必须让结构承担叙事功能，而不是用来制造“文学感”。
- 避免抽象总结代替具体叙事。少用“某种意义、答案、真相、命运、存在、本身、这一刻、仿佛、像是”等把场景拔高成泛哲理的表达；优先写动作、物件、空间、视线和信息差。
- 避免解释性心理标签。不要反复写“他知道/她明白/他意识到”，应把认知变化转化为选择、停顿、误判、回避、语气和动作。
- 避免模板化转折和收束。少用“然而、于是、然后、突然、最终、此刻”串接段落；让转折来自因果、场景物理变化、人物目标冲突或已埋线索的回响。
- 避免对称排比腔。不要用连续的“不是 A，而是 B；不是 C，而是 D”或抽象名词排比制造庄重感。文学节奏应来自观察顺序、句长变化和情绪压力。
- 避免全知解释腔。不要把主题、人物动机、世界观意义直接说透；优先保留可被读者推断的缝隙。
- 避免结尾金句化。场景收束应落在动作结果、关系变化、信息揭示或悬念上，不用空泛判断句替代戏剧变化。
- 禁止用正则或批量脚本对正文做语义级“去 AI 腔”改写。脚本只能提示风险或做安全排版规范化；删除“不是”、改写“不是 A——是 B”、替换心理判断等操作必须由平台 agent 逐句语义复核。"""

ANTI_AI_STYLE_SHORT_RULE = (
    "降低 AI 腔：默认禁用机械“不是……而是……”及“不是……——是……”等变体，"
    "除非 Style Skill 或用户明确授权其作为功能性修辞；避免抽象总结、解释性心理标签、"
    "模板化转折、对称排比、全知说教和结尾金句化。不得用脚本批量删除否定或做语义改写。"
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
        r"不是[^。！？!?；;\n]{1,50}?而是",
        r"不是[^。！？!?；;\n]{1,50}?——\s*是",
        r"不是[^。！？!?；;\n]{1,50}?[，,]\s*是",
        r"不是[^。！？!?；;\n]{1,50}?。\s*是",
        r"并非[^。！？!?；;\n]{1,50}?而是",
        r"并非[^。！？!?；;\n]{1,50}?——\s*是",
        r"与其说[^。！？!?；;\n]{1,40}?不如说",
    ]
    hits: list[str] = []
    for pattern in patterns:
        hits.extend(match.group(0) for match in re.finditer(pattern, text))
    hits = list(dict.fromkeys(hits))
    if not hits:
        return []
    severity = "medium" if len(hits) >= 2 else "low"
    message = (
        "机械对照/否定纠偏句式密度过高，容易形成 AI 腔；请先判断每处是否承担信息纠偏、讽刺顿挫或人物认知二分功能，"
        "再由写作 agent 局部修订。不得用脚本直接删除“不是”或批量替换破折号。"
        if severity == "medium"
        else "发现一次可能的机械对照/否定纠偏句式。若它承担人物认知、信息反转或已授权文风功能，可保留；否则请改为动作、信息差或句法重心推进。不得用脚本直接删改。"
    )
    return [
        AIStyleIssue(
            "mechanical-contrast-frame",
            severity,
            message,
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
