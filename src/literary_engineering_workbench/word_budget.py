"""Long-form word budget and narrative inventory planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .agent_tasks import write_agent_tasks


GENRE_PRESETS = {
    "general": {
        "label": "通用长篇",
        "aliases": {"general", "novel", "通用", "小说", "长篇"},
        "chapter_words": 4000,
        "scene_words": 1400,
        "scenes_per_chapter_min": 2,
        "scenes_per_chapter_max": 4,
        "mainline_ratio": 0.42,
        "relationship_ratio": 0.20,
        "world_info_ratio": 0.13,
        "consequence_ratio": 0.15,
        "breath_ratio": 0.10,
    },
    "mystery": {
        "label": "悬疑/推理",
        "aliases": {"mystery", "suspense", "thriller", "悬疑", "推理", "惊悚"},
        "chapter_words": 3800,
        "scene_words": 1250,
        "scenes_per_chapter_min": 3,
        "scenes_per_chapter_max": 5,
        "mainline_ratio": 0.38,
        "relationship_ratio": 0.17,
        "world_info_ratio": 0.18,
        "consequence_ratio": 0.17,
        "breath_ratio": 0.10,
    },
    "speculative": {
        "label": "科幻/奇幻/玄幻",
        "aliases": {"speculative", "fantasy", "sci-fi", "science-fiction", "科幻", "奇幻", "玄幻"},
        "chapter_words": 4200,
        "scene_words": 1500,
        "scenes_per_chapter_min": 2,
        "scenes_per_chapter_max": 4,
        "mainline_ratio": 0.36,
        "relationship_ratio": 0.16,
        "world_info_ratio": 0.24,
        "consequence_ratio": 0.14,
        "breath_ratio": 0.10,
    },
    "urban": {
        "label": "都市/职场/现实",
        "aliases": {"urban", "workplace", "realist", "都市", "职场", "现实"},
        "chapter_words": 3600,
        "scene_words": 1200,
        "scenes_per_chapter_min": 3,
        "scenes_per_chapter_max": 5,
        "mainline_ratio": 0.34,
        "relationship_ratio": 0.26,
        "world_info_ratio": 0.12,
        "consequence_ratio": 0.18,
        "breath_ratio": 0.10,
    },
    "literary": {
        "label": "文学向",
        "aliases": {"literary", "literature", "文学", "严肃文学"},
        "chapter_words": 4500,
        "scene_words": 1600,
        "scenes_per_chapter_min": 2,
        "scenes_per_chapter_max": 4,
        "mainline_ratio": 0.30,
        "relationship_ratio": 0.24,
        "world_info_ratio": 0.10,
        "consequence_ratio": 0.20,
        "breath_ratio": 0.16,
    },
}


@dataclass(frozen=True)
class WordBudgetResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    agent_tasks_path: Path
    target_words: int
    volume_count: int
    chapter_count: int
    scene_count: int
    status: str
    issue_count: int


def build_word_budget(
    project_root: Path,
    *,
    target_words: int = 0,
    volumes: int = 0,
    genre: str = "",
    time_span: str = "",
    outline: Path | None = None,
    output: Path | None = None,
    json_output: Path | None = None,
    agent_tasks_output: Path | None = None,
) -> WordBudgetResult:
    root = project_root.resolve()
    if not (root / "project.yaml").exists():
        raise FileNotFoundError(f"work project not found: {root}")
    project_text = _read(root / "project.yaml")
    resolved_target = int(target_words or _project_int(project_text, "target_length") or 100000)
    if resolved_target <= 0:
        raise ValueError("target words must be positive")
    volume_count = max(int(volumes or _infer_volumes(project_text, resolved_target)), 1)
    preset_key, preset = _preset_for(genre or _project_genre(project_text))
    volume_words = _distribute_words(resolved_target, volume_count)
    volume_budgets = [_volume_budget(index + 1, words, preset) for index, words in enumerate(volume_words)]
    totals = {
        "target_words": resolved_target,
        "volume_count": volume_count,
        "chapter_count": sum(item["chapter_count"] for item in volume_budgets),
        "scene_count": sum(item["scene_count"] for item in volume_budgets),
        "avg_chapter_words": round(resolved_target / max(sum(item["chapter_count"] for item in volume_budgets), 1)),
        "avg_scene_words": round(resolved_target / max(sum(item["scene_count"] for item in volume_budgets), 1)),
    }
    outline_path = _resolve(root, outline) if outline else root / "plot" / "outline.md"
    inventory = _outline_inventory(root, outline_path)
    issues = _budget_issues(totals, inventory)
    candidate_outputs = {
        "budgeted_outline_candidate": "plot/candidates/outlines/word_budget_expansion.md",
        "budget_review": "reviews/word_budget/word_budget_review.md",
    }
    status = "pass" if not [issue for issue in issues if issue["severity"] in {"high", "medium"}] else "needs_expansion"

    markdown_path = _resolve_output(root, output, "plot", "word_budget", "word_budget.md")
    json_path = _resolve_output(root, json_output, "plot", "word_budget", "word_budget.json")
    task_path = _resolve_output(root, agent_tasks_output, "plot", "word_budget", "word_budget.agent_tasks.md")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.parent.mkdir(parents=True, exist_ok=True)
    (root / "reviews" / "word_budget").mkdir(parents=True, exist_ok=True)
    (root / "plot" / "candidates" / "outlines").mkdir(parents=True, exist_ok=True)

    payload = {
        "schema": "literary-engineering-workbench/word-budget/v1",
        "generated_at": _now(),
        "project_root": str(root),
        "target": {
            "target_words": resolved_target,
            "volumes": volume_count,
            "genre": preset_key,
            "genre_label": preset["label"],
            "time_span": time_span,
        },
        "preset": {key: value for key, value in preset.items() if key != "aliases"},
        "totals": totals,
        "volume_budgets": volume_budgets,
        "outline_inventory": inventory,
        "issues": issues,
        "status": status,
        "candidate_outputs": candidate_outputs,
        "standard_chain": {
            "must_run_before": ["agent-create-outline", "outline-lab", "scene-development", "generate-scene"],
            "platform_agent_required_for": [
                "budgeted outline expansion",
                "volume/chapter/scene creative allocation",
                "narrative-load review",
                "approval before promotion",
            ],
        },
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(root, payload, json_path), encoding="utf-8")
    _write_agent_tasks(root, markdown_path, json_path, outline_path, task_path, payload)

    return WordBudgetResult(
        project_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
        agent_tasks_path=task_path,
        target_words=resolved_target,
        volume_count=volume_count,
        chapter_count=totals["chapter_count"],
        scene_count=totals["scene_count"],
        status=status,
        issue_count=len(issues),
    )


def load_word_budget_summary(root: Path) -> dict[str, object]:
    path = root / "plot" / "word_budget" / "word_budget.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        "path": _rel(path, root),
        "status": payload.get("status", ""),
        "target": payload.get("target", {}),
        "totals": payload.get("totals", {}),
        "issues": payload.get("issues", []),
    }


def render_word_budget_generation_standard(root: Path) -> str:
    summary = load_word_budget_summary(root)
    if not summary:
        return """# 长篇字数预算标准

当前项目尚未生成 `plot/word_budget/word_budget.json`。若目标是中长篇或百万字级项目，进入正式大纲、章节或场景生成前应先运行 `word-budget`，把总字数拆成卷、章、场景和叙事负载。"""
    target = summary.get("target", {})
    totals = summary.get("totals", {})
    return f"""# 长篇字数预算标准

已加载 `{summary.get("path", "")}`。生成和扩写必须遵守以下预算，不得把大纲压缩成剧情摘要：

- 目标字数：{target.get("target_words", 0)}
- 卷数：{target.get("volumes", 0)}
- 类型：{target.get("genre_label", target.get("genre", ""))}
- 目标章节数：{totals.get("chapter_count", 0)}
- 目标场景数：{totals.get("scene_count", 0)}
- 平均章字数：{totals.get("avg_chapter_words", 0)}
- 平均场景字数：{totals.get("avg_scene_words", 0)}

场景生成前必须确认当前场景承担明确叙事负载：主线行动、关系压力、世界/信息释放、行动后果或节奏调节。若当前大纲没有足够场景库存，先补候选场景，不要用长段总结、空泛抒情或重复心理解释灌字数。"""


def _write_agent_tasks(root: Path, markdown_path: Path, json_path: Path, outline_path: Path, task_path: Path, payload: dict) -> None:
    candidate = payload["candidate_outputs"]["budgeted_outline_candidate"]
    review = payload["candidate_outputs"]["budget_review"]
    source_paths = [markdown_path, json_path, root / "project.yaml"]
    if outline_path.exists():
        source_paths.append(outline_path)
    write_agent_tasks(
        task_path,
        title="longform word budget and narrative inventory review",
        root=root,
        source_paths=source_paths,
        notes=[
            "这是长篇字数预算与剧情库存门禁任务。",
            "CLI 只负责计算预算、统计现有大纲库存和生成诊断；卷章场景创意分配必须由平台 agent 完成。",
            "预算不等于灌字数。补足字数必须通过因果链、场景功能、人物状态、信息释放和行动后果增加剧情库存。",
            "候选大纲未经审查和用户批准，不得覆盖 plot/outline.md 或正式 scene 文件。",
        ],
        tasks=[
            (
                "审查预算与类型映射",
                """读取 word_budget.json / word_budget.md，确认目标字数、卷数、类型、时间跨度、章节数、场景数和平均场景字数是否适合该作品。若类型或时间跨度导致节奏不合理，提出修正预算而不是直接缩水。""",
            ),
            (
                "补足剧情库存候选",
                f"""创建或覆盖 `{candidate}`。按卷 -> 章 -> 场景列出可支撑目标字数的候选结构。每章必须包含目标字数、2-5个场景、每个场景的功能、目标字数、主线/副线/人物线/世界信息/后果负载、详略等级和承接的前后因果。不得只写概括性梗概。""",
            ),
            (
                "建立字数-剧情量映射",
                """为每卷写出剧情库存说明：核心事件数、调查/行动链数、人物关系变化数、信息释放点、失败/代价点、伏笔设置和回收点。若某卷目标约10万字，场景库存通常应达到60-90个；不足时必须标注 underbuilt。""",
            ),
            (
                "写入预算审查报告",
                f"""创建或覆盖 `{review}`。报告结论使用 pass / pass_with_notes / revise_required / reject，说明当前大纲是否足以支撑目标字数、哪里欠剧情库存、哪些卷需要扩展、哪些内容需要用户确认。不要写入 `[AGENT_TASK: ...]`。""",
            ),
        ],
    )


def _volume_budget(index: int, words: int, preset: dict[str, object]) -> dict[str, object]:
    chapter_count = max(round(words / int(preset["chapter_words"])), 1)
    scene_count = max(round(words / int(preset["scene_words"])), chapter_count * int(preset["scenes_per_chapter_min"]))
    min_scenes = chapter_count * int(preset["scenes_per_chapter_min"])
    max_scenes = chapter_count * int(preset["scenes_per_chapter_max"])
    scene_count = min(max(scene_count, min_scenes), max_scenes)
    ratios = {
        "mainline": float(preset["mainline_ratio"]),
        "relationship": float(preset["relationship_ratio"]),
        "world_or_information": float(preset["world_info_ratio"]),
        "consequence": float(preset["consequence_ratio"]),
        "breath_or_transition": float(preset["breath_ratio"]),
    }
    scene_load = {key: max(round(scene_count * ratio), 1) for key, ratio in ratios.items()}
    return {
        "volume_id": f"volume_{index:02d}",
        "target_words": words,
        "chapter_count": chapter_count,
        "scene_count": scene_count,
        "avg_chapter_words": round(words / chapter_count),
        "avg_scene_words": round(words / scene_count),
        "scene_load": scene_load,
        "required_turning_points": [
            "opening_hook",
            "first_commitment",
            "midpoint_reversal",
            "cost_or_failure",
            "volume_crisis",
            "payoff_and_next_hook",
        ],
    }


def _budget_issues(totals: dict[str, int], inventory: dict[str, int | str]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    planned_chapters = int(inventory.get("planned_chapter_count", 0))
    planned_scenes = int(inventory.get("planned_scene_count", 0))
    required_chapters = totals["chapter_count"]
    required_scenes = totals["scene_count"]
    if planned_chapters and planned_chapters < required_chapters * 0.75:
        issues.append(
            {
                "severity": "medium",
                "category": "chapter_inventory",
                "message": f"现有章节库存约 {planned_chapters}，低于预算章节 {required_chapters} 的 75%。",
                "recommendation": "扩展卷章结构，增加可承载场景的章节，不要用章节摘要替代场景。",
            }
        )
    elif not planned_chapters:
        issues.append(
            {
                "severity": "medium",
                "category": "chapter_inventory",
                "message": f"未检测到明确章节库存，预算需要约 {required_chapters} 章。",
                "recommendation": "先生成预算化章节候选，再进入场景开发。",
            }
        )
    if planned_scenes and planned_scenes < required_scenes * 0.75:
        issues.append(
            {
                "severity": "high",
                "category": "scene_inventory",
                "message": f"现有场景库存约 {planned_scenes}，低于预算场景 {required_scenes} 的 75%。",
                "recommendation": "按主线、关系线、信息释放、行动后果和节奏调节补足场景库存。",
            }
        )
    elif not planned_scenes:
        issues.append(
            {
                "severity": "high",
                "category": "scene_inventory",
                "message": f"未检测到明确场景库存，预算需要约 {required_scenes} 个场景。",
                "recommendation": "先拆出卷-章-场景级候选，不要直接生成正文。",
            }
        )
    return issues


def _outline_inventory(root: Path, outline_path: Path) -> dict[str, int | str]:
    text = _read(outline_path)
    scene_files = [path for path in (root / "scenes").glob("*.yaml") if not path.name.startswith("_")] if (root / "scenes").exists() else []
    volume_count = len(re.findall(r"(?im)^(?:#{1,6}\s*)?(?:第[一二三四五六七八九十百\d]+卷|volume\s+\d+|卷\s*[一二三四五六七八九十百\d]+)", text))
    chapter_count = len(re.findall(r"(?im)^(?:#{1,6}\s*)?(?:第[一二三四五六七八九十百\d]+章|chapter\s+\d+|chapter_\d+)", text))
    scene_markers = len(re.findall(r"(?im)^(?:#{1,6}\s*)?(?:场景\s*[一二三四五六七八九十百\d]+|scene[_\s-]?\d+)", text))
    return {
        "outline_path": _rel(outline_path, root) if outline_path.exists() else "",
        "planned_volume_count": volume_count,
        "planned_chapter_count": chapter_count,
        "outline_scene_markers": scene_markers,
        "scene_file_count": len(scene_files),
        "planned_scene_count": max(scene_markers, len(scene_files)),
    }


def _render_markdown(root: Path, payload: dict, json_path: Path) -> str:
    target = payload["target"]
    totals = payload["totals"]
    inventory = payload["outline_inventory"]
    lines = [
        "# 长篇字数预算与剧情库存报告",
        "",
        f"- JSON：`{_rel(json_path, root)}`",
        f"- 状态：`{payload['status']}`",
        f"- 目标字数：{target['target_words']}",
        f"- 卷数：{target['volumes']}",
        f"- 类型：{target['genre_label']}",
        f"- 时间跨度：{target.get('time_span') or '未指定'}",
        f"- 预算章节：{totals['chapter_count']}",
        f"- 预算场景：{totals['scene_count']}",
        f"- 平均章字数：{totals['avg_chapter_words']}",
        f"- 平均场景字数：{totals['avg_scene_words']}",
        "",
        "## 卷级预算",
        "",
        "| 卷 | 目标字数 | 章节 | 场景 | 章均字数 | 场景均字数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in payload["volume_budgets"]:
        lines.append(
            f"| {item['volume_id']} | {item['target_words']} | {item['chapter_count']} | {item['scene_count']} | {item['avg_chapter_words']} | {item['avg_scene_words']} |"
        )
    lines.extend(
        [
            "",
            "## 现有大纲库存",
            "",
            f"- 大纲：`{inventory.get('outline_path') or 'missing'}`",
            f"- 已规划卷：{inventory['planned_volume_count']}",
            f"- 已规划章：{inventory['planned_chapter_count']}",
            f"- 大纲场景标记：{inventory['outline_scene_markers']}",
            f"- scene 文件：{inventory['scene_file_count']}",
            f"- 估算场景库存：{inventory['planned_scene_count']}",
            "",
            "## 风险",
            "",
        ]
    )
    if payload["issues"]:
        for issue in payload["issues"]:
            lines.append(f"- **{issue['severity']} / {issue['category']}**：{issue['message']} 建议：{issue['recommendation']}")
    else:
        lines.append("- 未发现明显字数-剧情库存风险。")
    lines.extend(
        [
            "",
            "## 标准链路",
            "",
            "1. 先用本预算确认卷、章、场景和叙事负载。",
            "2. 平台 Agent 根据 `word_budget.agent_tasks.md` 生成预算化大纲候选。",
            "3. 预算化大纲通过审查和用户批准前，不得覆盖正式 `plot/outline.md`。",
            "4. 场景生成必须读取预算标准，避免把长篇目标压缩成短篇摘要。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _preset_for(genre: str) -> tuple[str, dict[str, object]]:
    normalized = str(genre or "").strip().lower()
    for key, preset in GENRE_PRESETS.items():
        if normalized in preset["aliases"]:
            return key, preset
    return "general", GENRE_PRESETS["general"]


def _distribute_words(target_words: int, volumes: int) -> list[int]:
    if volumes <= 1:
        return [target_words]
    weights = [0.9 + 0.2 * (index / max(volumes - 1, 1)) for index in range(volumes)]
    total = sum(weights)
    values = [round(target_words * weight / total) for weight in weights]
    drift = target_words - sum(values)
    values[-1] += drift
    return values


def _infer_volumes(project_text: str, target_words: int) -> int:
    match = re.search(r"(?m)^[ \t]*volumes:[ \t]*(\d+)", project_text)
    if match:
        value = int(match.group(1))
        if value > 0:
            return value
    if target_words >= 400000:
        return 5
    if target_words >= 250000:
        return 3
    return 1


def _project_int(project_text: str, key: str) -> int:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(\d+)", project_text)
    return int(match.group(1)) if match else 0


def _project_genre(project_text: str) -> str:
    match = re.search(r"(?m)^[ \t]*genre:[ \t]*(.*?)\s*$", project_text)
    return match.group(1).strip().strip("\"'") if match else ""


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
