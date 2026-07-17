from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from shutil import copyfile


@dataclass(frozen=True)
class InitOptions:
    target: Path
    title: str
    work_type: str = "novel"
    target_length: int = 30000
    language: str = "zh-CN"
    premise: str = ""
    genre: str = ""
    style_mode: str = "public_domain_or_authorized"


@dataclass(frozen=True)
class InitResult:
    root: Path
    files: tuple[Path, ...]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _write(path: Path, content: str, files: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    files.append(path)


def _copy_template(template_name: str, target: Path, files: list[Path]) -> None:
    src = _repo_root() / "templates" / template_name
    target.parent.mkdir(parents=True, exist_ok=True)
    copyfile(src, target)
    files.append(target)


def _project_yaml(options: InitOptions) -> str:
    return f"""project:
  title: {_quote(options.title)}
  type: {options.work_type}
  target_length: {options.target_length}
  language: {options.language}
  status: planning
  created_at: {_quote(datetime.now(timezone.utc).isoformat())}

creative_brief:
  premise: {_quote(options.premise)}
  genre: {_quote(options.genre)}
  audience: ""
  central_question: ""
  themes: []
  forbidden_elements: []

style:
  mode: {options.style_mode}
  target_profiles: []
  blend_strategy: ""

generation:
  default_provider: auto
  prompt_templates:
    system: prompts/scene_generation_system.md
    user: prompts/scene_generation_user.md
  model_env:
    global_config: ~/.lew/config.json
    api_base: LEW_MODEL_API_BASE
    api_key: LEW_MODEL_API_KEY
    model_name: LEW_MODEL_NAME

workflow:
  require_human_approval_for:
    - confirmed_canon
    - major_character_turn
    - main_plot_branch_merge
    - final_export

quality_gates:
  canon_test: required
  character_test: required
  plot_test: required
  style_test: required
  originality_test: required
"""


def _agents_md(title: str) -> str:
    return f"""# Agent 入口：{title}

本目录是一部具体作品的文学工程项目。Agent 接手时必须先读：

1. `project.yaml`
2. `agentread.yaml`
3. `canon/world_rules.yaml`
4. `characters/_template.yaml`
5. `plot/outline.md`
6. `style/style-profile.md`
7. `prompts/scene_generation_system.md`
8. `prompts/scene_generation_user.md`

## 工作原则

- 正文生成前先构建场景上下文包。
- 模型生成必须使用 prompts 下的版本化提示词模板。
- 软记忆召回不能覆盖 canon。
- 新事实必须先进入候选区，再由人工确认。
- 角色推演必须基于人物 BDI。
- 审查未通过的草稿不能进入正稿。

## 默认流程

```text
读取项目状态 -> 构建场景上下文包 -> 角色推演 -> 分支推演 -> 场景编排 -> 候选生成 -> 审查 -> 写回候选 -> 人工确认
```
"""


def _agentread_yaml() -> str:
    return """schema: literary-work-project/v0.1
read_first:
  - AGENTS.md
  - project.yaml
  - canon/world_rules.yaml
  - plot/outline.md
task_routes:
  create_scene:
    read:
      - project.yaml
      - canon/world_rules.yaml
      - canon/timeline.yaml
      - characters/_template.yaml
      - plot/outline.md
      - style/style-profile.md
      - scenes/scene_0001.yaml
  review_draft:
    read:
      - canon/facts.json
      - characters/_template.yaml
      - plot/foreshadowing.csv
      - style/style-profile.md
      - reviews/review-report-template.md
  update_canon:
    read:
      - canon/facts.json
      - canon/timeline.yaml
      - reviews/
"""


def init_work_project(options: InitOptions) -> InitResult:
    root = options.target.resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"target directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []

    _write(root / "project.yaml", _project_yaml(options), files)
    _write(root / "AGENTS.md", _agents_md(options.title), files)
    _write(root / "agentread.yaml", _agentread_yaml(), files)

    _write(root / "canon" / "world_rules.yaml", "rules: []\nconstraints: []\nopen_questions: []\n", files)
    _write(root / "canon" / "timeline.yaml", "events: []\n", files)
    _write(
        root / "canon" / "facts.json",
        json.dumps({"facts": [], "conflicts": [], "candidates": []}, ensure_ascii=False, indent=2) + "\n",
        files,
    )
    _write(root / "canon" / "locations.yaml", "locations: []\n", files)
    _write(root / "canon" / "organizations.yaml", "organizations: []\n", files)
    _write(root / "canon" / "forbidden_changes.yaml", "forbidden_changes: []\n", files)
    _write(root / "canon" / "candidates" / "world_rules" / "README.md", "# world rule candidates\n\nAgent 生成的世界观候选放在这里。不得直接作为 confirmed canon。\n", files)
    _write(root / "canon" / "candidates" / "locations" / "README.md", "# location candidates\n\nAgent 生成的地点候选放在这里。\n", files)
    _write(root / "canon" / "candidates" / "organizations" / "README.md", "# organization candidates\n\nAgent 生成的组织候选放在这里。\n", files)

    _copy_template("character.yaml", root / "characters" / "_template.yaml", files)
    _write(root / "characters" / "candidates" / "README.md", "# character candidates\n\nAgent 生成的人物候选放在这里。未经 review 和 approve，不得晋升为正式人物档案。\n", files)
    _write(root / "characters" / "candidates" / "background_stories" / "README.md", "# background story candidates\n\nAgent 生成的人物背景故事候选放在这里。背景故事只作为隐性行为因果。\n", files)
    _write(root / "characters" / "state_patches" / "README.md", "# state_patches\n\n人物状态演化候选 patch 放在这里。未经人工确认，不得写回人物档案。\n", files)
    _copy_template("scene.yaml", root / "scenes" / "scene_0001.yaml", files)
    _copy_template("style/style-profile.md", root / "style" / "style-profile.md", files)
    _copy_template("review-report.md", root / "reviews" / "review-report-template.md", files)
    _write(root / "reviews" / "longform" / "README.md", "# longform\n\n长篇连续性审计报告放在这里。\n", files)

    _write(root / "plot" / "outline.md", f"# {options.title} 大纲\n\n## Premise\n\n{options.premise or '尚未填写。'}\n", files)
    _write(root / "plot" / "candidates" / "outlines" / "README.md", "# outline candidates\n\nAgent 生成的大纲、章节计划和场景列表候选放在这里。\n", files)
    _write(root / "plot" / "candidates" / "relationships" / "README.md", "# relationship candidates\n\nAgent 生成的人物关系网候选放在这里。\n", files)
    _write(root / "plot" / "scene_graph.json", json.dumps({"scenes": [], "edges": []}, ensure_ascii=False, indent=2) + "\n", files)
    _write(root / "plot" / "longform_graph.json", json.dumps({"nodes": [], "edges": []}, ensure_ascii=False, indent=2) + "\n", files)
    _write(root / "plot" / "chapters" / "README.md", "# chapters\n\n章节级状态 JSON 放在这里。\n", files)
    _write(root / "plot" / "foreshadowing.csv", "foreshadow_id,setup_scene,visibility,expected_payoff,status,notes\n", files)
    _write(root / "plot" / "conflict_matrix.md", "# 冲突矩阵\n\n| 角色/势力 | 目标 | 冲突对象 | 代价 |\n| --- | --- | --- | --- |\n", files)

    _write(root / "drafts" / "README.md", "# drafts\n\n正文草稿和正稿版本放在这里。\n", files)
    _write(root / "drafts" / "chapters" / "README.md", "# chapters\n\n章节级工作台和章节草稿放在这里。\n", files)
    _write(root / "memory" / "README.md", "# memory\n\n向量索引、摘要和检索日志放在这里。\n", files)
    _write(root / "memory" / "retrieval_logs" / "README.md", "# retrieval_logs\n\n每次生成前的检索记录放在这里。\n", files)
    _write(root / "memory" / "context_packets" / "README.md", "# context_packets\n\n场景上下文包放在这里。\n", files)
    _write(root / "branches" / "README.md", "# branches\n\n剧情分支实验放在这里。\n", files)
    _write(root / "agents" / "runs" / "README.md", "# agent runs\n\n通用 Agent 输入输出、schema validation 和 repair attempts 放在这里。\n", files)
    _write(root / "agents" / "patch_plans" / "README.md", "# patch plans\n\nAgent 生成的受控写回计划放在这里。未经审批不得直接应用。\n", files)
    _write(root / "agents" / "committee" / "README.md", "# committee\n\n多 Agent 审稿委员会的独立意见和汇总结果放在这里。\n", files)
    _copy_template("prompts/scene_generation_system.md", root / "prompts" / "scene_generation_system.md", files)
    _copy_template("prompts/scene_generation_user.md", root / "prompts" / "scene_generation_user.md", files)
    _write(root / "prompts" / "video_prompt_template.md", "# 视频提示词模板\n\n待后期根据场景状态生成。\n", files)
    _write(root / "exports" / "README.md", "# exports\n\n最终导出文件放在这里。\n", files)
    _write(root / "exports" / "video_prompts" / "README.md", "# video_prompts\n\n视频提示词包可复制或归档到这里。\n", files)
    _write(root / "exports" / "screenplays" / "README.md", "# screenplays\n\n剧本格式导出可复制或归档到这里。\n", files)
    _write(root / "exports" / "chapters" / "README.md", "# chapters\n\n小说章节导出可复制或归档到这里。\n", files)
    _write(root / "releases" / "README.md", "# releases\n\n通过 publish-chapter 生成的发布版本放在这里。\n", files)
    _write(root / "workflow" / "runs" / "README.md", "# workflow runs\n\nAgent 工作流运行状态和日志放在这里。\n", files)
    _write(root / "tests" / "README.md", "# tests\n\n作品级审查和回归测试放在这里。\n", files)

    return InitResult(root=root, files=tuple(files))
