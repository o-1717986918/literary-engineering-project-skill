"""Task contracts for the tool-layer platform agent.

These helpers do not call a local model, dry-run provider, or HTTP endpoint.
They write explicit task sidecars for the Codex/Claude layer that loaded this
skill, then downstream gates validate the artifacts that platform agent writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from .agent_tasks import write_agent_tasks
from .asset_workshop import ASSET_CANDIDATE_DIRS, ASSET_SCHEMA_NAMES, ASSET_TYPES


@dataclass(frozen=True)
class PlatformAgentTaskResult:
    task_path: Path
    expected_report_path: Path
    expected_json_path: Path


def write_platform_scene_review_task(
    root: Path,
    *,
    scene_path: Path,
    draft_path: Path,
    report_path: Path | None = None,
    json_path: Path | None = None,
) -> PlatformAgentTaskResult:
    scene_id = scene_path.stem
    report = report_path or root / "reviews" / "agent" / f"{scene_id}_scene_review.md"
    json_output = json_path or root / "reviews" / "agent" / f"{scene_id}_scene_review.json"
    context_path = root / "memory" / "context_packets" / f"{scene_id}.md"
    style_candidates = [
        root / "style" / "style_prompt.md",
        root / "style" / "demo-author" / "style_prompt.md",
        root / "style" / "style-profile.md",
    ]
    source_paths = [scene_path, draft_path]
    if context_path.exists():
        source_paths.append(context_path)
    source_paths.extend(path for path in style_candidates if path.exists())
    task_path = json_output.with_suffix(".agent_tasks.md")
    write_agent_tasks(
        task_path,
        title=f"formal scene review {scene_id}",
        root=root,
        source_paths=source_paths,
        notes=[
            "这是正式发布门禁任务：由装载本 Skill 的平台 agent 完成。",
            "不要调用本地 dry-run、http-chat、外部 agent 服务或隐藏 provider。",
            f"完成后写入 JSON：{_rel(json_output, root)}",
            f"完成后写入 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "读取审查材料",
                """读取 scene.yaml、draft markdown、context packet 和已挂载 style prompt/profile。确认本场景的 canon 约束、人物 BDI、hidden background_story、场景目标、输出状态和用户约束。""",
            ),
            (
                "进行语义审查",
                """以平台 agent 的文学判断审查人物行为逻辑、背景故事隐性因果、canon 风险、剧情推进、文风执行、套路化/同质化风险和需要修订的动作。""",
            ),
            (
                "写入正式 JSON",
                f"""创建或覆盖 `{_rel(json_output, root)}`，JSON 必须符合 `scene_review.v1`：
{{
  "schema": "literary-engineering-workbench/scene-review-agent/v1",
  "scene_id": "{scene_id}",
  "conclusion": "pass | pass_with_notes | revise_required | reject",
  "summary": "...",
  "blocking_issues": [],
  "warnings": [],
  "revision_actions": [],
  "character_logic": [],
  "canon_risks": [],
  "style_notes": [],
  "source_paths": []
}}
`conclusion` 只有 `pass` 或 `pass_with_notes` 才能进入 ready；新增事实仍保持候选。""",
            ),
            (
                "写入正式 Markdown 报告",
                f"""创建或覆盖 `{_rel(report, root)}`，说明结论、阻塞问题、修订动作、人物逻辑、canon 风险和风格备注。不要写入 `[AGENT_TASK: ...]`。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, json_output)


def write_platform_scene_generation_task(
    root: Path,
    *,
    scene_path: Path,
    context_path: Path,
    composition_path: Path | None = None,
    prompt_manifest_path: Path | None = None,
    candidate_path: Path | None = None,
    manifest_path: Path | None = None,
) -> PlatformAgentTaskResult:
    scene_id = scene_path.stem
    candidate = candidate_path or root / "drafts" / "candidates" / f"{scene_id}-platform-agent.md"
    manifest = manifest_path or candidate.with_suffix(".json")
    source_paths = [scene_path, context_path]
    if composition_path and composition_path.exists():
        source_paths.append(composition_path)
    if prompt_manifest_path and prompt_manifest_path.exists():
        source_paths.append(prompt_manifest_path)
    task_path = candidate.with_suffix(".agent_tasks.md")
    write_agent_tasks(
        task_path,
        title=f"platform scene generation {scene_id}",
        root=root,
        source_paths=source_paths,
        notes=[
            "由平台 agent 创作候选正文；不要调用本地 dry-run、http-chat 或外部 agent。",
            "prompt manifest 是给平台 agent 的审计和提示词材料，不是外部 provider 调用记录。",
            f"完成后写入候选 Markdown：{_rel(candidate, root)}",
            f"完成后写入候选 manifest JSON：{_rel(manifest, root)}",
        ],
        tasks=[
            (
                "读取创作材料",
                """读取 scene.yaml、context packet、composition packet、style prompt/profile 和相关 canon/character 文件。确认人物 BDI、hidden background_story、scene goal、output_state 和用户约束。""",
            ),
            (
                "生成候选正文",
                f"""创建或覆盖 `{_rel(candidate, root)}`。正文必须包含 `## 正文候选` 和 `## 状态变化候选`，不得写入 `[AGENT_TASK: ...]`，不得把新增事实写成已确认 canon。背景故事只通过选择、回避、误判、语气或关系压力间接影响行动。""",
            ),
            (
                "生成候选 manifest",
                f"""创建或覆盖 `{_rel(manifest, root)}`，记录 schema、scene_id、candidate、source_paths、generated_by=`platform-agent`、created_at、style_profile/context/composition 引用和待审查事项。""",
            ),
            (
                "后续门禁",
                """候选生成后不得直接 promote。平台 agent 或用户需要审查候选，再进入 promote-candidate、review-scene、平台 Agent 场景审查和 state-evolve。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, candidate, manifest)


def write_platform_asset_creation_task(
    root: Path,
    *,
    asset_type: str,
    brief: str = "",
    target_id: str = "",
    source: Path | None = None,
    candidate_path: Path | None = None,
    report_path: Path | None = None,
) -> PlatformAgentTaskResult:
    normalized = _normalize_asset_type(asset_type)
    schema_name = ASSET_SCHEMA_NAMES[normalized]
    candidate_id = _asset_candidate_id(normalized, target_id or brief)
    candidate = candidate_path or root / ASSET_CANDIDATE_DIRS[normalized] / f"{candidate_id}.json"
    report = report_path or candidate.with_suffix(".md")
    source_paths = [
        root / "project.yaml",
        root / "canon",
        root / "characters",
        root / "plot",
        root / "style",
        Path(__file__).resolve().parents[2] / "schemas" / "agent_outputs" / f"{schema_name}.schema.json",
    ]
    resolved_source = _resolve_optional(root, source)
    if resolved_source:
        source_paths.append(resolved_source)
    task_path = candidate.with_suffix(".agent_tasks.md")
    write_agent_tasks(
        task_path,
        title=f"platform asset creation {normalized}",
        root=root,
        source_paths=source_paths,
        notes=[
            "由平台 agent 创建候选资产；不要调用本地 dry-run、http-chat 或外部 agent。",
            f"资产类型：{normalized}",
            f"目标 schema：{schema_name}",
            f"完成后写入候选 JSON：{_rel(candidate, root)}",
            f"完成后写入候选 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "读取项目约束",
                """读取 project.yaml、canon、characters、plot、style 挂载和对应 schema。确认新增内容只能是候选，不能覆盖正式 canon、characters 或 plot。""",
            ),
            (
                "生成候选资产",
                f"""按 `{schema_name}` 创建或覆盖 `{_rel(candidate, root)}`。必须包含 `schema`、`candidate_id`、`risks`、`source_paths` 和 `promotion_notes`；如为角色相关资产，必须让 background_story 只作为隐性行为因果。创作简述：{brief or "使用项目 premise 与现有材料。"} 目标 ID：{target_id or "n/a"}。""",
            ),
            (
                "写入候选说明",
                f"""创建或覆盖 `{_rel(report, root)}`，说明候选摘要、风险、需要用户确认的事项、后续审查步骤和不得自动晋升的边界。不要写入 `[AGENT_TASK: ...]`。""",
            ),
            (
                "后续门禁",
                """候选资产生成后，平台 agent 需要进行 schema/语义审查，再由用户或审批记录决定是否 promote。不得直接写入正式项目文件。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, candidate)


def write_platform_asset_review_task(
    root: Path,
    *,
    candidate_path: Path,
    report_path: Path | None = None,
    json_path: Path | None = None,
) -> PlatformAgentTaskResult:
    candidate = candidate_path if candidate_path.is_absolute() else root / candidate_path
    candidate_id = candidate.stem
    report = report_path or root / "reviews" / "assets" / f"{candidate_id}_review.md"
    json_output = json_path or report.with_suffix(".json")
    task_path = json_output.with_suffix(".agent_tasks.md")
    source_paths = [
        candidate,
        root / "canon",
        root / "characters",
        root / "plot",
        root / "style",
    ]
    write_agent_tasks(
        task_path,
        title=f"platform asset review {candidate_id}",
        root=root,
        source_paths=source_paths,
        notes=[
            "由平台 agent 审查候选资产；不要调用本地 dry-run、http-chat 或外部 agent。",
            f"完成后写入 JSON：{_rel(json_output, root)}",
            f"完成后写入 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "审查候选资产",
                """读取候选 JSON，对照对应 schema、项目 canon、角色事实、文风挂载和用户约束。检查新增事实是否仍是候选、角色背景故事是否只作为行为因果、世界规则是否引入万能解法、剧情大纲是否破坏既有伏笔。""",
            ),
            (
                "写入审查 JSON",
                f"""创建或覆盖 `{_rel(json_output, root)}`，至少包含 schema、candidate、candidate_id、asset_type、status(pass|failed|revise_required)、blocking_issues、warnings、revision_actions、promotion_risks、reviewed_at。""",
            ),
            (
                "写入审查报告",
                f"""创建或覆盖 `{_rel(report, root)}`，说明是否可进入用户审批、必须修订项和不得自动晋升的原因。不要写入 `[AGENT_TASK: ...]`。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, json_output)


def write_platform_canon_review_task(root: Path) -> PlatformAgentTaskResult:
    report = root / "reviews" / "agent" / "canon_review.md"
    json_output = root / "reviews" / "agent" / "canon_review.json"
    sources = [
        root / "reviews" / "canon_lint.md",
        root / "reviews" / "canon_lint.json",
        root / "canon",
        root / "characters",
        root / "scenes",
        root / "plot",
    ]
    task_path = json_output.with_suffix(".agent_tasks.md")
    write_agent_tasks(
        task_path,
        title="formal canon and continuity review",
        root=root,
        source_paths=sources,
        notes=[
            "由平台 agent 审查 canon、角色、场景、章节和伏笔连续性。",
            "本任务不调用本地 dry-run、http-chat 或外部 agent。",
            f"完成后写入 JSON：{_rel(json_output, root)}",
            f"完成后写入 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "审查 canon lint 与项目状态",
                """读取 canon-lint 输出和项目目录，判断 blocking、warning、未确认事实、时间线风险、角色状态断裂和伏笔债务。""",
            ),
            (
                "写入正式 canon review",
                """按 `canon_review.v1` 写入 JSON，并在 Markdown 报告中给出需要修复、保留候选或请求用户确认的事项。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, json_output)


def write_platform_committee_task(
    root: Path,
    *,
    subject: str,
    source: Path | None = None,
) -> PlatformAgentTaskResult:
    safe_subject = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in subject).strip("-") or "subject"
    report = root / "reviews" / "agent" / f"committee_{safe_subject}.md"
    json_output = root / "reviews" / "agent" / f"committee_{safe_subject}.json"
    source_paths = [source] if source else []
    task_path = json_output.with_suffix(".agent_tasks.md")
    write_agent_tasks(
        task_path,
        title=f"formal review committee {subject}",
        root=root,
        source_paths=source_paths,
        notes=[
            "由平台 agent 扮演多个审稿视角完成综合判断。",
            "不要调用本地 dry-run、http-chat 或外部 agent。",
            f"完成后写入 JSON：{_rel(json_output, root)}",
            f"完成后写入 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "多视角审查",
                """分别从总编辑、人物心理、canon、文风、可读性和反同质化角度审查 source artifact。""",
            ),
            (
                "形成综合建议",
                """按 `committee_review.v1` 写出最终建议、分歧、行动项和少数意见。不要把建议直接晋升为 canon 或发布决定。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, json_output)


def write_platform_json_task(
    root: Path,
    *,
    schema_name: str,
    task: str = "build-json",
    source: Path | None = None,
    target: str = "",
    output_dir: Path | None = None,
) -> PlatformAgentTaskResult:
    safe_schema = _safe_label(schema_name.replace(".", "-"))
    safe_task = _safe_label(task)
    out_dir = output_dir or root / "agents" / "platform_tasks" / f"{safe_task}_{safe_schema}_{_stamp()}"
    json_output = out_dir / "parsed_output.json"
    report = out_dir / "report.md"
    task_path = out_dir / "task.agent_tasks.md"
    sources = [Path(__file__).resolve().parents[2] / "schemas" / "agent_outputs" / f"{schema_name}.schema.json"]
    resolved_source = _resolve_optional(root, source)
    if resolved_source:
        sources.append(resolved_source)
    write_agent_tasks(
        task_path,
        title=f"platform JSON task {task}",
        root=root,
        source_paths=sources,
        notes=[
            "由平台 agent 生成 JSON；不要调用本地 dry-run、http-chat 或外部 agent。",
            f"目标 schema：{schema_name}",
            f"目标对象：{target or 'n/a'}",
            f"完成后写入 JSON：{_rel(json_output, root)}",
            f"完成后写入 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "读取 schema 和材料",
                """读取 schema、source artifact 和 target 说明，确认输出只是候选 JSON，不得直接写入 canon、characters、plot、drafts 或 release。""",
            ),
            (
                "写入 JSON",
                f"""创建或覆盖 `{_rel(json_output, root)}`。JSON 必须符合 `{schema_name}`，并保留 source_paths、risks 或需要确认的字段。""",
            ),
            (
                "写入报告",
                f"""创建或覆盖 `{_rel(report, root)}`，说明生成依据、风险、需要用户确认的事项和后续验证命令。不要写入 `[AGENT_TASK: ...]`。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, json_output)


def write_platform_patch_plan_task(
    root: Path,
    *,
    target: str,
    source: Path | None = None,
    report_path: Path | None = None,
    json_path: Path | None = None,
) -> PlatformAgentTaskResult:
    safe_target = _safe_label(target.replace("/", "-").replace("\\", "-"))
    report = report_path or root / "agents" / "patch_plans" / f"{safe_target}_patch_plan.md"
    json_output = json_path or report.with_suffix(".json")
    task_path = json_output.with_suffix(".agent_tasks.md")
    sources = [root / target]
    resolved_source = _resolve_optional(root, source)
    if resolved_source:
        sources.append(resolved_source)
    sources.append(Path(__file__).resolve().parents[2] / "schemas" / "agent_outputs" / "json_patch_plan.v1.schema.json")
    write_agent_tasks(
        task_path,
        title=f"platform patch plan {target}",
        root=root,
        source_paths=sources,
        notes=[
            "由平台 agent 规划写回补丁；不要调用本地 dry-run、http-chat 或外部 agent。",
            "本任务只生成补丁计划，不直接修改目标文件。",
            f"完成后写入 JSON：{_rel(json_output, root)}",
            f"完成后写入 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "审查写回边界",
                """读取 target、source 和 json_patch_plan.v1 schema。确认哪些改动是候选、哪些需要用户审批、哪些会影响 canon/character/plot 的硬约束。""",
            ),
            (
                "写入补丁计划 JSON",
                f"""创建或覆盖 `{_rel(json_output, root)}`，按 `json_patch_plan.v1` 记录 operation、path、value、reason、risk 和 approval_required。不得直接应用补丁。""",
            ),
            (
                "写入补丁计划报告",
                f"""创建或覆盖 `{_rel(report, root)}`，给出变更摘要、风险和审批建议。不要写入 `[AGENT_TASK: ...]`。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, json_output)


def write_platform_style_prompt_task(
    profile_dir: Path,
    *,
    output: Path | None = None,
    json_path: Path | None = None,
) -> PlatformAgentTaskResult:
    profile = profile_dir.resolve()
    prompt = output if output and output.is_absolute() else profile / (str(output) if output else "style_prompt.md")
    json_output = json_path if json_path and json_path.is_absolute() else profile / (str(json_path) if json_path else "style_prompt.agent.json")
    task_path = prompt.with_suffix(".agent_tasks.md")
    sources = [
        profile / "style-profile.md",
        profile / "style_metrics.json",
        profile / "corpus_manifest.yaml",
        Path(__file__).resolve().parents[2] / "schemas" / "agent_outputs" / "style_prompt.v1.schema.json",
    ]
    write_agent_tasks(
        task_path,
        title="platform style prompt generation",
        root=profile,
        source_paths=sources,
        notes=[
            "由平台 agent 生成供 LLM 使用的文风约束提示词；不要调用本地 dry-run、http-chat 或外部 agent。",
            f"完成后写入提示词 Markdown：{_rel(prompt, profile)}",
            f"完成后写入 JSON：{_rel(json_output, profile)}",
        ],
        tasks=[
            (
                "读取文风证据",
                """读取 style-profile.md、style_metrics.json 和 corpus_manifest.yaml。把证据转译为可执行的 LLM 文风约束，而不是评论文章或统计摘要。""",
            ),
            (
                "写入文风提示词",
                f"""创建或覆盖 `{_rel(prompt, profile)}`。必须包含使用身份、核心风格机制、句法与节奏、叙述距离与心理呈现、意象和感官调度、对白与动作、禁止倾向、输出自检。""",
            ),
            (
                "写入 schema JSON",
                f"""创建或覆盖 `{_rel(json_output, profile)}`，按 `style_prompt.v1` 记录 prompt_markdown、constraints、avoid、source_paths、evaluation_plan 和 risk_notes。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, prompt, json_output)


def write_platform_style_prompt_eval_task(
    profile_dir: Path,
    *,
    reference: Path,
    task_input: Path,
    mode: str,
    style_prompt: Path | None = None,
    output_dir: Path | None = None,
) -> PlatformAgentTaskResult:
    profile = profile_dir.resolve()
    out_dir = output_dir if output_dir and output_dir.is_absolute() else profile / (str(output_dir) if output_dir else f"evaluation_results/{mode}")
    candidate = out_dir / "platform_agent_candidate.md"
    manifest = out_dir / "platform_agent_candidate.prompt.json"
    task_path = candidate.with_suffix(".agent_tasks.md")
    prompt_path = style_prompt if style_prompt and style_prompt.is_absolute() else profile / (str(style_prompt) if style_prompt else "style_prompt.md")
    sources = [prompt_path, reference, task_input, profile / "style-profile.md", profile / "style_metrics.json"]
    write_agent_tasks(
        task_path,
        title=f"platform style prompt evaluation {mode}",
        root=profile,
        source_paths=sources,
        notes=[
            "由平台 agent 根据 style_prompt.md 生成评测候选；不要调用本地 dry-run、http-chat 或外部 agent。",
            f"完成后写入候选文本：{_rel(candidate, profile)}",
            f"完成后写入 prompt manifest：{_rel(manifest, profile)}",
            "候选写入后，可再运行 deterministic style-eval 对候选和 reference 打分。",
        ],
        tasks=[
            (
                "读取评测材料",
                """读取 style_prompt.md、reference、input 和 profile/metrics。确认本次模式是回译、扩写或盲评，不要把参考原文直接复制到候选。""",
            ),
            (
                "生成评测候选",
                f"""创建或覆盖 `{_rel(candidate, profile)}`，用 style_prompt 的约束处理 input，生成用于评估提示词有效性的候选文本。""",
            ),
            (
                "写入 manifest",
                f"""创建或覆盖 `{_rel(manifest, profile)}`，记录 mode、style_prompt、reference、input、candidate、source_paths 和平台 agent 生成说明。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, candidate, manifest)


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _normalize_asset_type(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "background": "background-story",
        "background_story": "background-story",
        "relationships": "relationship",
        "world-rules": "world",
        "chapter": "chapter-plan",
        "scenes": "scene-list",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in ASSET_TYPES:
        raise ValueError(f"unknown asset type: {value}. valid: {', '.join(ASSET_TYPES)}")
    return normalized


def _asset_candidate_id(asset_type: str, seed: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = _slug(seed)[:28] or "candidate"
    return f"{asset_type}-{slug}-platform-agent-{stamp}"


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", str(value).strip()).strip("-")
    return text or "asset"


def _resolve_optional(root: Path, path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.is_absolute() else root / path


def _safe_label(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "-", value.strip()).strip("-") or "task"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
