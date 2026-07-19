import json
import tempfile
from pathlib import Path

from literary_engineering_workbench.agent_tasks import write_agent_completion_marker
from literary_engineering_workbench.context_packet import build_context_packet
from literary_engineering_workbench.init_project import InitOptions, init_work_project
from literary_engineering_workbench.review_ci import review_scene_draft
from literary_engineering_workbench.scene_draft import build_scene_draft


class TempProjectMixin:
    def make_project(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name) / "work"
        init_work_project(
            InitOptions(
                target=root,
                title="测试作品",
                premise="一个用于测试文学工程工作流的故事。",
                genre="工程测试",
            )
        )
        self.addCleanup(tmp.cleanup)
        return root


def add_character(project_root: Path, name: str = "林舟") -> Path:
    path = project_root / "characters" / "linzhou.yaml"
    path.write_text(
        f"""character_id: linzhou
name: {name}
role: 主角
bdi:
  belief:
    - 城市的停电不是偶然。
  desire:
    - 找到被隐藏的档案。
  intention:
    - 在不惊动看守的情况下进入旧楼。
psychology:
  fear:
    - 牵连同伴。
  secret:
    - 他曾经读过一页残缺档案。
  moral_line: 不伤害无辜者。
background_story:
  summary: 他少年时因一次误判导致同伴受罚，从此习惯先观察再行动。
  formative_events:
    - 少年时期的误判让他对仓促决定保持警惕。
  behavior_influences:
    - 遇到危险时会先确认旁人是否会被牵连。
    - 面对档案和旧事时会表现得异常克制。
  reveal_policy: implicit_only
speech_style:
  rhythm: 短句，克制，少解释。
""",
        encoding="utf-8",
    )
    return path


def make_passing_scene(project_root: Path) -> Path:
    build_context_packet(project_root, scene=Path("scenes/scene_0001.yaml"), rebuild_index=True)
    draft = build_scene_draft(project_root, scene=Path("scenes/scene_0001.yaml")).draft_path
    text = draft.read_text(encoding="utf-8")
    body = (
        "林舟站在旧楼门口，听见楼道深处的电流声断断续续。他停在门外，数了三次呼吸，确认街角的巡逻灯还没有转向。"
        "这一次，他要把那页残缺档案和眼前的停电连起来。门后的灰尘被风推开，刚好露出一串新的脚印。"
        "他把手电压低，沿着墙边移动，心里清楚每一步都会改变同伴明天能否继续调查。"
    )
    replacements = {
        "<!-- 在这里写入场景正文。 -->": body,
        "### 新增事实候选\n\n- ": "### 新增事实候选\n\n- 林舟发现旧楼停电与残缺档案有关。",
        "### 人物状态变化\n\n- ": "### 人物状态变化\n\n- 林舟从旁观转为主动调查。",
        "### 关系变化\n\n- ": "### 关系变化\n\n- 林舟开始隐瞒自己的行动计划。",
        "### 伏笔变化\n\n- ": "### 伏笔变化\n\n- 残缺档案成为后续追查线索。",
        "### 需要人工确认\n\n- ": "### 需要人工确认\n\n- 是否确认旧楼停电为主线事件。",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    draft.write_text(text, encoding="utf-8")
    return draft


def make_reviewed_passing_scene(project_root: Path, prepare_flow: bool = True) -> Path:
    draft = make_passing_scene(project_root)
    if prepare_flow:
        prepare_formal_scene_flow(project_root)
    review_scene_draft(project_root, draft)
    write_platform_scene_review(project_root)
    return draft


def make_static_reviewed_passing_scene(project_root: Path, prepare_flow: bool = True) -> Path:
    draft = make_passing_scene(project_root)
    if prepare_flow:
        prepare_formal_scene_flow(project_root)
    review_scene_draft(project_root, draft)
    return draft


def write_platform_scene_review(project_root: Path, scene_id: str = "scene_0001", conclusion: str = "pass") -> Path:
    review_dir = project_root / "reviews" / "agent"
    review_dir.mkdir(parents=True, exist_ok=True)
    json_path = review_dir / f"{scene_id}_scene_review.json"
    report_path = review_dir / f"{scene_id}_scene_review.md"
    active_style = (project_root / "style" / "active_style_skill.json").exists()
    revision_actions = [] if conclusion == "pass" else ["局部修订审查 notes 后再进入章节装配。"]
    style_notes = [] if conclusion == "pass" else ["风格约束需要进一步执行。"]
    warnings = [] if conclusion == "pass" else ["存在待处理小修项。"]
    payload = {
        "schema": "literary-engineering-workbench/scene-review-agent/v1",
        "scene_id": scene_id,
        "conclusion": conclusion,
        "summary": "平台 agent 审查通过测试场景，未发现阻塞风险。",
        "blocking_issues": [],
        "warnings": warnings,
        "revision_actions": revision_actions,
        "character_logic": [{"character": "linzhou", "assessment": "行动符合 BDI 与背景故事隐性影响。"}],
        "canon_risks": [],
        "style_notes": style_notes,
        "style_adherence": {
            "status": "pass" if active_style else "not_applicable",
            "style_profile": "style/active_style_skill.json" if active_style else "n/a",
            "evidence": ["测试场景已按挂载文风门禁通过。"] if active_style else [],
            "deviations": [],
            "revision_actions": [],
        },
        "word_budget_adherence": {
            "status": "not_required",
            "target_words": 0,
            "min_words": 0,
            "max_words": 0,
            "clean_body_words": 120,
            "narrative_load_satisfied": True,
            "message": "test project does not require longform budget",
        },
        "new_character_register": {
            "schema": "literary-engineering-workbench/new-character-register/v0.1",
            "status": "none",
            "introduced": [],
            "ephemeral_waivers": [],
            "blocking_issues": [],
        },
        "source_paths": [
            f"scenes/{scene_id}.yaml",
            f"drafts/scenes/{scene_id}.md",
            f"memory/context_packets/{scene_id}.md",
            f"memory/context_packets/{scene_id}.trace.json",
        ],
        "agent_confidence": "platform-test",
        "next_gate": "chapter_workspace",
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(
        f"# 平台 Agent 场景审查：{scene_id}\n\n- 结论：`{conclusion}`\n- 测试报告：已通过正式门禁样例。\n",
        encoding="utf-8",
    )
    task_path = json_path.with_suffix(".agent_tasks.md")
    task_path.write_text(
        f"# 平台 Agent 任务说明：fixture review {scene_id}\n\n创建或覆盖 `{json_path.resolve().relative_to(project_root.resolve()).as_posix()}`。\n",
        encoding="utf-8",
    )
    write_agent_completion_marker(task_path, root=project_root, handled_by="platform-agent-test")
    return json_path


def write_formal_candidate_artifacts(project_root: Path, candidate: Path, scene_id: str = "scene_0001", *, revision: bool = False) -> None:
    rel_candidate = candidate.resolve().relative_to(project_root.resolve()).as_posix()
    prompt_manifest = candidate.with_suffix(".prompt.json")
    manifest = candidate.with_suffix(".json")
    task = candidate.with_suffix(".agent_tasks.md")
    prompt_manifest.write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/prompt-pack/v0.1",
                "provider": "platform-agent",
                "model": "tool-layer-agent",
                "scene": f"scenes/{scene_id}.yaml",
                "context": f"memory/context_packets/{scene_id}.md",
                "context_trace": f"memory/context_packets/{scene_id}.trace.json",
                "composition": f"drafts/compositions/{scene_id}_composition.md",
                "generation_standards": {
                    "style": "test style standard",
                    "word_budget": "test word budget standard",
                    "review_notes": "test review notes",
                    "anti_evasion": "test anti-evasion",
                    "hard_constraints": "test hard constraints",
                },
                "messages": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if revision:
        payload = {
            "schema": "literary-engineering-workbench/scene-revision/v0.1",
            "scene_id": scene_id,
            "candidate": rel_candidate,
            "prompt_manifest": prompt_manifest.resolve().relative_to(project_root.resolve()).as_posix(),
            "source_paths": [
                f"scenes/{scene_id}.yaml",
                f"memory/context_packets/{scene_id}.md",
                f"memory/context_packets/{scene_id}.trace.json",
                f"reviews/agent/{scene_id}_scene_review.json",
            ],
            "generated_by": "platform-agent",
            "anti_evasion_protocol_applied": True,
            "anti_evasion_rows": [],
            "retained_transition_proofs": [],
            "evasion_risks_unresolved": [],
            "new_character_register": {
                "schema": "literary-engineering-workbench/new-character-register/v0.1",
                "status": "none",
                "introduced": [],
                "ephemeral_waivers": [],
                "blocking_issues": [],
            },
        }
    else:
        payload = {
            "schema": "literary-engineering-workbench/scene-generation-candidate/v0.1",
            "scene_id": scene_id,
            "candidate": rel_candidate,
            "prompt_manifest": prompt_manifest.resolve().relative_to(project_root.resolve()).as_posix(),
            "source_paths": [
                f"scenes/{scene_id}.yaml",
                f"memory/context_packets/{scene_id}.md",
                f"memory/context_packets/{scene_id}.trace.json",
                f"drafts/compositions/{scene_id}_composition.md",
                prompt_manifest.resolve().relative_to(project_root.resolve()).as_posix(),
            ],
            "generated_by": "platform-agent",
            "created_at": "2026-01-01T00:00:00Z",
            "style_profile": "",
            "context": f"memory/context_packets/{scene_id}.md",
            "composition": f"drafts/compositions/{scene_id}_composition.md",
            "style_generation_standard_applied": True,
            "word_budget_standard_applied": False,
            "hard_constraints_applied": True,
            "anti_evasion_protocol_applied": True,
            "pass_with_notes_actions_applied": False,
            "new_character_register": {
                "schema": "literary-engineering-workbench/new-character-register/v0.1",
                "status": "none",
                "introduced": [],
                "ephemeral_waivers": [],
                "blocking_issues": [],
            },
        }
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task.write_text(
        f"""# 平台 Agent 任务说明：formal candidate fixture {scene_id}

## Source Artifacts

- `scenes/{scene_id}.yaml`
- `memory/context_packets/{scene_id}.md`
- `memory/context_packets/{scene_id}.trace.json`

## Tasks

[AGENT_TASK: 创建或覆盖 `{rel_candidate}`。创建或覆盖 `{manifest.resolve().relative_to(project_root.resolve()).as_posix()}`。]
""",
        encoding="utf-8",
    )
    write_agent_completion_marker(task, root=project_root, handled_by="platform-agent-test")


def prepare_formal_scene_flow(project_root: Path, scene_id: str = "scene_0001") -> None:
    context_path = project_root / "memory" / "context_packets" / f"{scene_id}.md"
    if not context_path.exists():
        build_context_packet(project_root, scene=Path(f"scenes/{scene_id}.yaml"), rebuild_index=True)

    branch_dir = project_root / "branches" / scene_id
    branch_dir.mkdir(parents=True, exist_ok=True)
    (branch_dir / "roleplay_simulation.md").write_text(
        f"""# 角色推演实验室：{scene_id}

正式 CLI 来源：`simulate-scene`

### 读取回执

- 已读取：scenes/{scene_id}.yaml
- 已读取：memory/context_packets/{scene_id}.md
- 写回边界：候选。

## Character Agent：行动提案

- 测试角色行动已由平台 Agent 按 BDI 与背景故事审查。

## World Agent：后果推演

- 后果仅作为候选，不直接写入 canon。
""",
        encoding="utf-8",
    )
    roleplay_task = branch_dir / "roleplay_simulation.agent_tasks.md"
    roleplay_task.write_text(
        f"# 平台 Agent 任务说明：fixture roleplay {scene_id}\n\n创建或覆盖 `branches/{scene_id}/roleplay_simulation.md`。\n",
        encoding="utf-8",
    )
    write_agent_completion_marker(roleplay_task, root=project_root, handled_by="platform-agent-test")
    (branch_dir / "branch_manifest.json").write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/branch-manifest/v0.1",
                "formal_cli_provenance": {
                    "created_by": "branch-simulate",
                    "agent_tasks_requested": True,
                    "manual_file_creation_allowed": False,
                },
                "scene_id": scene_id,
                "recommended_branch": "branch_character_inevitable",
                "branches": [
                    {
                        "branch_id": "branch_character_inevitable",
                        "title": "测试正式分支",
                        "premise": "角色按已知信息谨慎推进。",
                        "status": "candidate",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    branch_task = branch_dir / "branch_manifest.agent_tasks.md"
    branch_task.write_text(
        f"# 平台 Agent 任务说明：fixture branch {scene_id}\n\n创建或覆盖 `branches/{scene_id}/branch_selection.md`。\n",
        encoding="utf-8",
    )
    write_agent_completion_marker(branch_task, root=project_root, handled_by="platform-agent-test")
    (branch_dir / "branch_selection.md").write_text(
        f"""# Branch Selection：{scene_id}

## 人工决定

- decision: selected
- selected_branch: branch_character_inevitable
- reviewer: platform-agent-test
- selected_at: 2026-01-01T00:00:00Z
""",
        encoding="utf-8",
    )
    composition_dir = project_root / "drafts" / "compositions"
    composition_dir.mkdir(parents=True, exist_ok=True)
    (composition_dir / f"{scene_id}_composition.json").write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/scene-composition/v0.1",
                "formal_cli_provenance": {
                    "created_by": "compose-scene",
                    "agent_tasks_requested": True,
                    "manual_file_creation_allowed": False,
                },
                "scene_id": scene_id,
                "selected_branch": "branch_character_inevitable",
                "selection_source": "selection",
                "ready_for_generation": True,
                "flow_gate": {
                    "branch_selection_required": True,
                    "ready_for_generation": True,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (composition_dir / f"{scene_id}_composition.md").write_text(
        f"# 场景编排包：{scene_id}\n\n- selected_branch: branch_character_inevitable\n- ready_for_generation: true\n",
        encoding="utf-8",
    )
    composition_task = composition_dir / f"{scene_id}_composition.agent_tasks.md"
    composition_task.write_text(
        f"# 平台 Agent 任务说明：fixture composition {scene_id}\n\n创建或覆盖 `drafts/compositions/{scene_id}_composition.md`。\n",
        encoding="utf-8",
    )
    write_agent_completion_marker(composition_task, root=project_root, handled_by="platform-agent-test")
