import argparse
import json
import os
from pathlib import Path

from .agent_provider import AGENT_PROVIDERS, run_agent_task
from .agent_schema import repair_agent_run, validate_agent_run
from .agent_task_status import build_agent_task_status, build_route_audit
from .approval import build_approval_summary
from .asset_workshop import (
    ASSET_TYPES,
    list_asset_candidates,
    promote_candidate_asset,
)
from .branch_lab import build_branch_simulation
from .canon_lint import build_canon_lint
from .candidate_promotion import promote_scene_candidate
from .character_state_apply import apply_character_state_patch
from .character_state_evolver import build_character_state_patch
from .chapter_pipeline import build_chapter_workspace
from .context_packet import build_context_packet
from .demo_project import build_demo_project
from .director_agent import build_director_status, run_director_turn
from .dify_dsl import DEFAULT_DIFY_DSL_PATH, DifyDslOptions, build_dify_workflow_dsl
from .docx_export import DOCX_KINDS, export_markdown_to_docx
from .export_package import build_export_package
from .init_project import InitOptions, init_work_project
from .knowledge_store import KNOWLEDGE_BACKENDS, build_knowledge_store, search_knowledge_store
from .langgraph_adapter import run_literary_graph
from .longform_audit import build_longform_audit
from .memory_index import build_memory_index, search_memory
from .model_config import (
    config_path,
    default_config,
    load_config,
    redacted_effective_config,
    save_config,
)
from .orchestration_blueprint import build_orchestration_blueprint
from .platform_agent_tasks import (
    write_platform_asset_creation_task,
    write_platform_asset_review_task,
    write_platform_canon_review_task,
    write_platform_committee_task,
    write_platform_json_task,
    write_platform_patch_plan_task,
    write_platform_scene_generation_task,
    write_platform_scene_review_task,
    write_platform_style_prompt_eval_task,
    write_platform_style_prompt_task,
)
from .prompt_pack import build_scene_prompt_pack, write_prompt_manifest
from .publish import publish_chapter
from .review_ci import review_scene_draft
from .scene_composer import build_scene_composition
from .roleplay_lab import build_roleplay_simulation
from .scene_draft import build_scene_draft
from .scene_revision import build_scene_revision_task
from .protocol import protocol_to_json, render_protocol, render_protocol_list, resolve_protocol_route
from .source_ingest import INGEST_MODES, ingest_existing_work
from .style_compiler import StyleCompileOptions, compile_style_profile
from .style_evaluator import STYLE_EVAL_MODES, StyleEvalOptions, evaluate_style
from .style_lab import (
    active_project_style,
    build_style_skill,
    create_author_project,
    create_author_work,
    import_work_source,
    list_author_projects,
    list_style_skills,
    mount_style_skill,
    run_author_style_learning_platform_task,
)
from .workflow_runner import WORKFLOW_MODES, run_workflow
from .word_budget import build_word_budget


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lew",
        description="Literary Engineering Workbench command line tools.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    protocol = sub.add_parser("protocol", help="Print the mandatory agent/CLI run protocol for a route.")
    protocol.add_argument("route", nargs="?", default="", help="Route key such as scene-development, style-engineering, or export-and-release. Omit to list routes.")
    protocol.add_argument("--json", action="store_true", help="Output machine-readable JSON.")

    init = sub.add_parser("init", help="Initialize a fictional work project.")
    init.add_argument("target", help="Target project directory.")
    init.add_argument("--title", required=True, help="Work title.")
    init.add_argument("--type", default="novel", choices=["novel", "screenplay", "pseudo-record"])
    init.add_argument("--target-length", type=int, default=30000)
    init.add_argument("--language", default="zh-CN")
    init.add_argument("--premise", default="")
    init.add_argument("--genre", default="")
    init.add_argument("--style-mode", default="public_domain_or_authorized")

    demo = sub.add_parser("demo-project", help="Build a deterministic demo project with agent review artifacts.")
    demo.add_argument("target", help="Target demo project directory.")
    demo.add_argument("--title", default="文学工程 Demo")
    demo.add_argument("--skip-workflow", action="store_true", help="Create artifacts without running the demo workflow.")

    index = sub.add_parser("index", help="Build a lightweight memory index for a work project.")
    index.add_argument("project", help="Work project directory.")

    search = sub.add_parser("search", help="Search the lightweight memory index.")
    search.add_argument("project", help="Work project directory.")
    search.add_argument("query", help="Search query.")
    search.add_argument("--top-k", type=int, default=8)

    knowledge_build = sub.add_parser("knowledge-build", help="Build a metadata-rich knowledge store for a work project.")
    knowledge_build.add_argument("project", help="Work project directory.")
    knowledge_build.add_argument("--backend", default="json", choices=sorted(KNOWLEDGE_BACKENDS))
    knowledge_build.add_argument("--out", default="", help="Output store path. Defaults to memory/knowledge_store.json.")

    knowledge_search = sub.add_parser("knowledge-search", help="Search the metadata-rich knowledge store.")
    knowledge_search.add_argument("project", help="Work project directory.")
    knowledge_search.add_argument("query", help="Search query.")
    knowledge_search.add_argument("--top-k", type=int, default=8)
    knowledge_search.add_argument("--backend", default="json", choices=sorted(KNOWLEDGE_BACKENDS))
    knowledge_search.add_argument("--kind", default="", help="Filter by source kind, such as canon, characters, drafts.")
    knowledge_search.add_argument("--canon-status", default="", help="Filter by confirmed, planned, candidate, or working.")

    canon_lint = sub.add_parser("canon-lint", help="Lint project canon, character, scene, chapter, and foreshadowing consistency.")
    canon_lint.add_argument("project", help="Work project directory.")
    canon_lint.add_argument("--out", default="", help="Output markdown report path. Defaults to reviews/canon_lint.md.")
    canon_lint.add_argument("--json-out", default="", help="Output JSON report path. Defaults to reviews/canon_lint.json.")

    context = sub.add_parser("context", help="Build a scene context packet.")
    context.add_argument("project", help="Work project directory.")
    context.add_argument("--scene", default="scenes/scene_0001.yaml", help="Scene yaml path.")
    context.add_argument("--query", default="", help="Extra retrieval query.")
    context.add_argument("--top-k", type=int, default=8)
    context.add_argument("--rebuild-index", action="store_true")
    context.add_argument("--out", default="", help="Output markdown path.")

    for command, help_text in (
        ("source-ingest", "Import an existing work and write a platform-agent reverse extraction task."),
        ("extract-existing-work", "Alias for source-ingest."),
    ):
        source_ingest = sub.add_parser(command, help=help_text)
        source_ingest.add_argument("project", help="Work project directory.")
        source_ingest.add_argument("--source", default="", help="Source .txt/.md file or directory.")
        source_ingest.add_argument("--text", default="", help="Inline source text.")
        source_ingest.add_argument("--title", default="", help="Source work title.")
        source_ingest.add_argument("--work-id", default="", help="Stable import id. Defaults to title/source stem.")
        source_ingest.add_argument("--mode", default="continuation", choices=sorted(INGEST_MODES))
        source_ingest.add_argument("--chunk-size", type=int, default=6000, help="Character count per source chunk.")
        source_ingest.add_argument("--overwrite", action="store_true", help="Overwrite an existing import directory.")

    style = sub.add_parser("style-profile", help="Compile a literary style profile from a corpus.")
    style.add_argument("corpus", help="Corpus file or directory containing .txt/.md files.")
    style.add_argument("--out-dir", required=True, help="Output style asset directory.")
    style.add_argument("--name", required=True, help="Style profile name.")
    style.add_argument("--author", default="", help="Author or source label.")
    style.add_argument("--mode", default="public_domain_or_authorized")
    style.add_argument("--source-note", default="")

    style_eval = sub.add_parser("style-eval", help="Evaluate a candidate text against a style profile and reference text.")
    style_eval.add_argument("profile_dir", help="Directory containing style_metrics.json.")
    style_eval.add_argument("--reference", required=True, help="Original/reference text file.")
    style_eval.add_argument("--candidate", required=True, help="Candidate/back-translated/expanded text file.")
    style_eval.add_argument("--mode", default="back-translation", choices=sorted(STYLE_EVAL_MODES))
    style_eval.add_argument("--out-dir", default="", help="Output directory. Defaults to profile_dir/evaluation_results/{mode}.")

    style_prompt = sub.add_parser("style-prompt", help="Write a platform-agent task for an LLM-facing style constraint prompt.")
    style_prompt.add_argument("profile_dir", help="Directory containing style-profile.md and style_metrics.json.")
    style_prompt.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    style_prompt.add_argument("--out", default="", help="Output style prompt path. Defaults to profile_dir/style_prompt.md.")
    style_prompt.add_argument("--manifest-out", default="", help="Output prompt manifest path. Defaults to profile_dir/style_prompt.prompt.json.")

    style_prompt_eval = sub.add_parser("style-prompt-eval", help="Write a platform-agent task for a style-prompt evaluation candidate.")
    style_prompt_eval.add_argument("profile_dir", help="Directory containing style_prompt.md and style_metrics.json.")
    style_prompt_eval.add_argument("--reference", required=True, help="Original/reference Chinese text file.")
    style_prompt_eval.add_argument("--input", required=True, help="Back-translation English text, outline, or blind-review task input.")
    style_prompt_eval.add_argument("--mode", default="back-translation", choices=sorted(STYLE_EVAL_MODES))
    style_prompt_eval.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    style_prompt_eval.add_argument("--style-prompt", default="", help="Style prompt path. Defaults to profile_dir/style_prompt.md.")
    style_prompt_eval.add_argument("--out-dir", default="", help="Output directory. Defaults to profile_dir/evaluation_results/{mode}.")

    style_lab_list = sub.add_parser("style-lab-list", help="List author style projects and mountable style skills.")
    style_lab_list.add_argument("--library", default="", help="Style library root. Defaults to global config.")

    style_lab_author = sub.add_parser("style-lab-author", help="Create or update an author-centered style project.")
    style_lab_author.add_argument("--library", default="", help="Style library root. Defaults to global config.")
    style_lab_author.add_argument("--name", required=True, help="Author/project display name.")
    style_lab_author.add_argument("--author-id", default="", help="Stable author id.")
    style_lab_author.add_argument("--mode", default="public_domain_or_authorized")
    style_lab_author.add_argument("--source-note", default="")

    style_lab_work = sub.add_parser("style-lab-work", help="Create or update one work subproject under an author.")
    style_lab_work.add_argument("--library", default="", help="Style library root. Defaults to global config.")
    style_lab_work.add_argument("--author-id", required=True)
    style_lab_work.add_argument("--title", required=True)
    style_lab_work.add_argument("--work-id", default="")
    style_lab_work.add_argument("--year", default="")
    style_lab_work.add_argument("--notes", default="")

    style_lab_import = sub.add_parser("style-lab-import", help="Import a source text into an author work project.")
    style_lab_import.add_argument("--library", default="", help="Style library root. Defaults to global config.")
    style_lab_import.add_argument("--author-id", required=True)
    style_lab_import.add_argument("--work-id", required=True)
    style_lab_import.add_argument("--file", default="", help="Source .txt/.md file.")
    style_lab_import.add_argument("--text", default="", help="Inline source text.")
    style_lab_import.add_argument("--filename", default="")
    style_lab_import.add_argument("--chunk-chars", type=int, default=4000)

    style_lab_compile = sub.add_parser("style-lab-compile", help="Compile an author profile and write a platform-agent style prompt task.")
    style_lab_compile.add_argument("--library", default="", help="Style library root. Defaults to global config.")
    style_lab_compile.add_argument("--author-id", required=True)
    style_lab_compile.add_argument("--profile-id", default="default")
    style_lab_compile.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")

    style_lab_skill = sub.add_parser("style-lab-build-skill", help="Build a mountable style skill from an author profile.")
    style_lab_skill.add_argument("--library", default="", help="Style library root. Defaults to global config.")
    style_lab_skill.add_argument("--author-id", required=True)
    style_lab_skill.add_argument("--profile-id", default="default")
    style_lab_skill.add_argument("--style-id", default="")

    style_lab_mount = sub.add_parser("style-lab-mount", help="Mount a style skill into a creative project with highest priority.")
    style_lab_mount.add_argument("project", help="Work project directory.")
    style_lab_mount.add_argument("--library", default="", help="Style library root. Defaults to global config.")
    style_lab_mount.add_argument("--style-id", required=True)
    style_lab_mount.add_argument("--allow-unreviewed", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass style readiness gates.")

    agent_run = sub.add_parser("agent-run", help="Run a generic auditable agent task.")
    agent_run.add_argument("project", help="Work project directory.")
    agent_run.add_argument("--agent-id", required=True, help="Stable agent id, such as scene-reviewer.")
    agent_run.add_argument("--task", required=True, help="Short task name or review objective.")
    agent_run.add_argument("--system", default="", help="System prompt file. Relative paths resolve from project root.")
    agent_run.add_argument("--user", default="", help="User prompt file. Relative paths resolve from project root.")
    agent_run.add_argument("--system-text", default="", help="Inline system prompt text.")
    agent_run.add_argument("--user-text", default="", help="Inline user prompt text.")
    agent_run.add_argument("--provider", default="auto", choices=sorted(AGENT_PROVIDERS))
    agent_run.add_argument("--out-dir", default="", help="Output directory. Defaults to agents/runs/{run_id}.")

    agent_validate = sub.add_parser("agent-validate", help="Validate a parsed agent output against a workbench schema.")
    agent_validate.add_argument("project", help="Work project directory.")
    agent_validate.add_argument("--schema", required=True, help="Schema name, such as scene_review.v1.")
    agent_validate.add_argument("--run-id", default="", help="Agent run id under agents/runs/.")
    agent_validate.add_argument("--run-dir", default="", help="Agent run directory. Relative paths resolve from project root.")

    agent_repair = sub.add_parser("agent-repair", help="Repair an agent JSON output through provider and validate it.")
    agent_repair.add_argument("project", help="Work project directory.")
    agent_repair.add_argument("--schema", required=True, help="Schema name, such as scene_review.v1.")
    agent_repair.add_argument("--run-id", default="", help="Agent run id under agents/runs/.")
    agent_repair.add_argument("--run-dir", default="", help="Agent run directory. Relative paths resolve from project root.")
    agent_repair.add_argument("--provider", default="auto", choices=sorted(AGENT_PROVIDERS))

    agent_review_scene = sub.add_parser("agent-review-scene", help="Write a formal platform-agent scene review task.")
    agent_review_scene.add_argument("project", help="Work project directory.")
    agent_review_scene.add_argument("--scene", default="scenes/scene_0001.yaml")
    agent_review_scene.add_argument("--draft", default="", help="Draft path. Defaults to drafts/scenes/{scene_id}.md.")
    agent_review_scene.add_argument("--out", default="", help="Expected markdown report path.")
    agent_review_scene.add_argument("--json-out", default="", help="Expected JSON result path.")

    agent_canon_review = sub.add_parser("agent-canon-review", help="Write a formal platform-agent canon and continuity review task.")
    agent_canon_review.add_argument("project", help="Work project directory.")

    agent_build_json = sub.add_parser("agent-build-json", help="Write a platform-agent task to draft JSON for a named schema.")
    agent_build_json.add_argument("project", help="Work project directory.")
    agent_build_json.add_argument("--schema", required=True, help="Schema name, such as json_patch_plan.v1.")
    agent_build_json.add_argument("--agent-id", default="json-builder")
    agent_build_json.add_argument("--task", default="build-json")
    agent_build_json.add_argument("--source", default="", help="Optional source file.")
    agent_build_json.add_argument("--target", default="", help="Optional target path or object.")
    agent_build_json.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    agent_build_json.add_argument("--out-dir", default="", help="Output run directory.")

    agent_plan_patch = sub.add_parser("agent-plan-patch", help="Write a platform-agent task for a controlled writeback patch plan.")
    agent_plan_patch.add_argument("project", help="Work project directory.")
    agent_plan_patch.add_argument("--target", required=True, help="Safe relative target path.")
    agent_plan_patch.add_argument("--source", default="", help="Optional source file.")
    agent_plan_patch.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    agent_plan_patch.add_argument("--out", default="", help="Output markdown path.")
    agent_plan_patch.add_argument("--json-out", default="", help="Output JSON path.")

    agent_style_prompt = sub.add_parser("agent-style-prompt", help="Write a platform-agent task for style_prompt.md and schema JSON.")
    agent_style_prompt.add_argument("profile_dir", help="Directory containing style-profile.md and style_metrics.json.")
    agent_style_prompt.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    agent_style_prompt.add_argument("--out", default="", help="Output style prompt path. Defaults to profile_dir/style_prompt.md.")
    agent_style_prompt.add_argument("--json-out", default="", help="Output agent JSON path. Defaults to profile_dir/style_prompt.agent.json.")

    agent_committee = sub.add_parser("agent-committee", help="Write a formal platform-agent review committee task.")
    agent_committee.add_argument("project", help="Work project directory.")
    agent_committee.add_argument("--subject", required=True, help="Review subject label.")
    agent_committee.add_argument("--source", default="", help="Optional source file.")

    agent_task_status = sub.add_parser("agent-task-status", help="Scan platform-agent sidecars and expected artifacts.")
    agent_task_status.add_argument("project", help="Work project directory.")
    agent_task_status.add_argument("--out", default="", help="Output markdown path. Defaults to workflow/agent_task_status.md.")
    agent_task_status.add_argument("--json-out", default="", help="Output JSON path. Defaults to workflow/agent_task_status.json.")

    route_audit = sub.add_parser("route-audit", help="Audit route gates and pending platform-agent tasks.")
    route_audit.add_argument("project", help="Work project directory.")
    route_audit.add_argument("--route", default="", help="Route key such as scene-development, longform-planning, or export-and-release.")
    route_audit.add_argument("--out", default="", help="Output markdown path. Defaults to workflow/route_audit.md.")
    route_audit.add_argument("--json-out", default="", help="Output JSON path. Defaults to workflow/route_audit.json.")

    director_chat = sub.add_parser("director-chat", help="Run the top-level creative director agent for one user direction.")
    director_chat.add_argument("project", help="Work project directory.")
    director_chat.add_argument("--message", required=True, help="High-level creative direction from the user.")
    director_chat.add_argument("--provider", default="auto", choices=sorted(AGENT_PROVIDERS))
    director_chat.add_argument("--no-execute", action="store_true", help="Plan and record the director decision without running the delegated workflow.")
    director_chat.add_argument("--agent-tasks", action="store_true", help="Ask delegated workflows to emit platform-agent task sidecars.")

    director_status = sub.add_parser("director-status", help="Show project status as seen by the creative director.")
    director_status.add_argument("project", help="Work project directory.")
    director_status.add_argument("--limit", type=int, default=8)

    for command, asset_type, help_text in [
        ("agent-create-character", "character", "Write a platform-agent task for a character profile candidate."),
        ("agent-create-background-story", "background-story", "Write a platform-agent task for a hidden background-story candidate."),
        ("agent-create-relationship", "relationship", "Write a platform-agent task for a relationship graph candidate."),
        ("agent-create-world", "world", "Write a platform-agent task for a world-rules candidate."),
        ("agent-create-location", "location", "Write a platform-agent task for a location candidate."),
        ("agent-create-organization", "organization", "Write a platform-agent task for an organization candidate."),
        ("agent-create-outline", "outline", "Write a platform-agent task for a plot outline candidate."),
        ("agent-create-chapter-plan", "chapter-plan", "Write a platform-agent task for a chapter-plan candidate."),
        ("agent-create-scene-list", "scene-list", "Write a platform-agent task for a scene-list candidate."),
    ]:
        create = sub.add_parser(command, help=help_text)
        create.set_defaults(asset_type=asset_type)
        create.add_argument("project", help="Work project directory.")
        create.add_argument("--brief", default="", help="Creative brief or constraints for the candidate.")
        create.add_argument("--target-id", default="", help="Stable id for the target character/location/organization when useful.")
        create.add_argument("--source", default="", help="Optional source file. Relative paths resolve from project root.")
        create.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
        create.add_argument("--out-dir", default="", help="Legacy compatibility only; formal command writes task sidecars next to expected outputs.")

    create_asset = sub.add_parser("asset-create", help="Write a platform-agent task for any supported candidate asset by type.")
    create_asset.add_argument("project", help="Work project directory.")
    create_asset.add_argument("--type", required=True, choices=ASSET_TYPES)
    create_asset.add_argument("--brief", default="")
    create_asset.add_argument("--target-id", default="")
    create_asset.add_argument("--source", default="")
    create_asset.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    create_asset.add_argument("--out-dir", default="", help="Legacy compatibility only; formal command writes task sidecars next to expected outputs.")

    list_assets = sub.add_parser("list-candidate-assets", help="List candidate assets created by agent asset commands.")
    list_assets.add_argument("project", help="Work project directory.")
    list_assets.add_argument("--type", default="", choices=("", *ASSET_TYPES))

    review_asset = sub.add_parser("review-candidate-asset", help="Write a platform-agent task to review a candidate asset before promotion.")
    review_asset.add_argument("project", help="Work project directory.")
    review_asset.add_argument("candidate", help="Candidate path or candidate id.")
    review_asset.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")

    promote_asset = sub.add_parser("promote-candidate-asset", help="Promote any reviewed and approved candidate asset.")
    promote_asset.add_argument("project", help="Work project directory.")
    promote_asset.add_argument("candidate", help="Candidate path or candidate id.")
    promote_asset.add_argument("--group", default="", choices=("", "character", "world", "outline"))
    promote_asset.add_argument("--approval-run-id", default="")
    promote_asset.add_argument("--allow-unapproved", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass approval gates.")

    for command, group, help_text in [
        ("promote-character-candidate", "character", "Promote a character/background/relationship candidate."),
        ("promote-world-candidate", "world", "Promote a world/location/organization candidate."),
        ("promote-outline-candidate", "outline", "Promote an outline/chapter/scene-list candidate."),
    ]:
        promote = sub.add_parser(command, help=help_text)
        promote.set_defaults(promote_group=group)
        promote.add_argument("project", help="Work project directory.")
        promote.add_argument("candidate", help="Candidate path or candidate id.")
        promote.add_argument("--approval-run-id", default="")
        promote.add_argument("--allow-unapproved", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass approval gates.")

    draft = sub.add_parser("draft-scene", help="Create a scene draft workspace from a context packet.")
    draft.add_argument("project", help="Work project directory.")
    draft.add_argument("--scene", default="scenes/scene_0001.yaml")
    draft.add_argument("--context", default="", help="Existing context packet path.")
    draft.add_argument("--query", default="", help="Extra retrieval query when context needs rebuilding.")
    draft.add_argument("--rebuild-context", action="store_true")
    draft.add_argument("--out", default="", help="Output draft path.")

    review = sub.add_parser("review-scene", help="Review a scene draft workspace.")
    review.add_argument("project", help="Work project directory.")
    review.add_argument("draft", help="Draft markdown path.")
    review.add_argument("--out", default="", help="Output review report path.")

    generate = sub.add_parser("generate-scene", help="Write a formal platform-agent scene generation task.")
    generate.add_argument("project", help="Work project directory.")
    generate.add_argument("--scene", default="scenes/scene_0001.yaml")
    generate.add_argument("--context", default="", help="Existing context packet path.")
    generate.add_argument("--composition", default="", help="Existing scene composition path. Defaults to drafts/compositions/{scene_id}_composition.md.")
    generate.add_argument("--query", default="", help="Extra retrieval query when context needs rebuilding.")
    generate.add_argument("--rebuild-context", action="store_true")
    generate.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    generate.add_argument("--out", default="", help="Output candidate markdown path.")
    generate.add_argument("--agent-tasks", action="store_true", help="Legacy compatibility only; formal command always writes a platform-agent task.")
    generate.add_argument("--allow-unselected-composition", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass branch-selection gates.")
    generate.add_argument("--allow-missing-composition", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass scene-composition gates.")

    revise = sub.add_parser("revise-scene", help="Write a formal platform-agent scene revision task.")
    revise.add_argument("project", help="Work project directory.")
    revise.add_argument("--scene", default="scenes/scene_0001.yaml")
    revise.add_argument("--draft", default="", help="Draft path. Defaults to drafts/scenes/{scene_id}.md.")
    revise.add_argument("--review", default="", help="Review JSON/Markdown path. Defaults to platform Agent review JSON or static review.")
    revise.add_argument("--query", default="", help="Extra retrieval query when context needs rebuilding.")
    revise.add_argument("--rebuild-context", action="store_true")
    revise.add_argument("--out", default="", help="Expected revision candidate path. Defaults to drafts/revisions/{scene_id}_revision.md.")
    revise.add_argument("--report-out", default="", help="Expected revision report path.")
    revise.add_argument("--manifest-out", default="", help="Expected revision manifest JSON path.")
    revise.add_argument("--prompt-manifest-out", default="", help="Revision prompt manifest JSON path.")
    revise.add_argument("--agent-tasks-out", default="", help="Revision task sidecar path.")

    promote = sub.add_parser("promote-candidate", help="Promote a generated scene candidate into the draft review lane.")
    promote.add_argument("project", help="Work project directory.")
    promote.add_argument("--scene", default="scenes/scene_0001.yaml")
    promote.add_argument("--candidate", default="", help="Candidate markdown path. Defaults to latest candidate for the scene.")
    promote.add_argument("--out", default="", help="Output draft path. Defaults to drafts/scenes/{scene_id}.md.")
    promote.add_argument("--overwrite", action="store_true", help="Replace an existing scene draft.")
    promote.add_argument("--approval-run-id", default="", help="Optional workflow approve run id used as selection evidence.")
    promote.add_argument("--selection-note", default="", help="Human note explaining why this candidate was selected.")
    promote.add_argument("--allow-unreviewed", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass candidate-specific platform review.")
    promote.add_argument("--allow-review-notes", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass unresolved review notes.")

    state_evolve = sub.add_parser("state-evolve", help="Create a reviewable character state evolution patch from a scene artifact.")
    state_evolve.add_argument("project", help="Work project directory.")
    state_evolve.add_argument("--scene", default="scenes/scene_0001.yaml")
    state_evolve.add_argument("--source", default="", help="Draft, candidate, composition markdown, or composition JSON path. Defaults to the scene draft when present.")
    state_evolve.add_argument("--out", default="", help="Output patch markdown path.")
    state_evolve.add_argument("--json-out", default="", help="Output patch JSON path.")
    state_evolve.add_argument("--agent-tasks", action="store_true", help="Write a platform-agent task sidecar for reviewing the state patch.")

    state_apply = sub.add_parser("state-apply", help="Apply an approved character state patch to character files.")
    state_apply.add_argument("project", help="Work project directory.")
    state_apply.add_argument("--patch", default="", help="State patch JSON path. Defaults to latest *_state_patch.json.")
    state_apply.add_argument("--approval-run-id", default="", help="Workflow run id with an approve record.")
    state_apply.add_argument("--allow-unapproved", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass approval gates.")
    state_apply.add_argument("--allow-unresolved", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass unresolved patch gates.")
    state_apply.add_argument("--out", default="", help="Output apply markdown report path.")
    state_apply.add_argument("--json-out", default="", help="Output apply JSON manifest path.")

    simulate = sub.add_parser("simulate-scene", help="Create a roleplay simulation workspace for a scene.")
    simulate.add_argument("project", help="Work project directory.")
    simulate.add_argument("--scene", default="scenes/scene_0001.yaml")
    simulate.add_argument("--context", default="", help="Existing context packet path.")
    simulate.add_argument("--query", default="", help="Extra retrieval query when context needs rebuilding.")
    simulate.add_argument("--rebuild-context", action="store_true")
    simulate.add_argument("--out", default="", help="Output simulation path.")
    simulate.add_argument("--agent", "--agent-tasks", dest="agent_tasks", action="store_true", help="Generate platform-agent executable task directives instead of empty placeholders.")

    branch = sub.add_parser("branch-simulate", help="Create scored multi-branch plot candidates for a scene.")
    branch.add_argument("project", help="Work project directory.")
    branch.add_argument("--scene", default="scenes/scene_0001.yaml")
    branch.add_argument("--context", default="", help="Existing context packet path.")
    branch.add_argument("--query", default="", help="Extra retrieval query when context needs rebuilding.")
    branch.add_argument("--rebuild-context", action="store_true")
    branch.add_argument("--branch-count", type=int, default=4, help="Number of branches to create, between 2 and 5.")
    branch.add_argument("--out", default="", help="Output markdown path.")
    branch.add_argument("--json-out", default="", help="Output JSON manifest path.")
    branch.add_argument("--selection-out", default="", help="Output human selection record path.")
    branch.add_argument("--agent", "--agent-tasks", dest="agent_tasks", action="store_true", help="Write a platform-agent task sidecar for reviewing branch decisions.")

    compose = sub.add_parser("compose-scene", help="Create a scene composition packet from context, characters, and branch artifacts.")
    compose.add_argument("project", help="Work project directory.")
    compose.add_argument("--scene", default="scenes/scene_0001.yaml")
    compose.add_argument("--context", default="", help="Existing context packet path.")
    compose.add_argument("--query", default="", help="Extra retrieval query when context needs rebuilding.")
    compose.add_argument("--rebuild-context", action="store_true")
    compose.add_argument("--branch-manifest", default="", help="Existing branch manifest path. Defaults to branches/{scene_id}/branch_manifest.json.")
    compose.add_argument("--branch-selection", default="", help="Existing branch selection path. Defaults to branches/{scene_id}/branch_selection.md.")
    compose.add_argument("--out", default="", help="Output composition markdown path.")
    compose.add_argument("--json-out", default="", help="Output composition JSON path.")
    compose.add_argument("--agent-tasks", action="store_true", help="Write a platform-agent task sidecar without polluting composition artifacts.")
    compose.add_argument("--allow-recommended-branch", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass branch-selection gates.")
    compose.add_argument("--allow-missing-branch", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass branch-simulation gates.")

    orchestration = sub.add_parser("orchestration-plan", help="Create an agent workflow platform blueprint.")
    orchestration.add_argument("project", help="Work project directory.")
    orchestration.add_argument(
        "--platforms",
        default="",
        help="Comma-separated platform keys. Defaults to langgraph,dify,llamaindex-workflows,crewai,microsoft-agent-framework.",
    )
    orchestration.add_argument("--out", default="", help="Output markdown path.")
    orchestration.add_argument("--json-out", default="", help="Output JSON path.")

    chapter = sub.add_parser("chapter-workspace", help="Assemble a chapter-level workspace from scene artifacts.")
    chapter.add_argument("project", help="Work project directory.")
    chapter.add_argument("--chapter-id", default="chapter_0001")
    chapter.add_argument("--scenes", default="", help="Comma-separated scene yaml paths. Defaults to chapter scenes.")
    chapter.add_argument("--build-missing", action="store_true", help="Create missing scene draft workspaces.")
    chapter.add_argument("--review-drafts", action="store_true", help="Run review on available scene drafts.")
    chapter.add_argument("--agent-review", action="store_true", help="Write platform-agent review tasks and require completed platform review JSON for ready scenes.")
    chapter.add_argument("--out", default="", help="Output chapter markdown path.")
    chapter.add_argument("--json-out", default="", help="Output chapter JSON path.")

    for command, help_text in (
        ("word-budget", "Build a long-form word budget and platform-agent expansion task."),
        ("longform-budget", "Alias for word-budget."),
    ):
        word_budget = sub.add_parser(command, help=help_text)
        word_budget.add_argument("project", help="Work project directory.")
        word_budget.add_argument("--target-words", type=int, default=0, help="Target total character count. Defaults to project.yaml target_length.")
        word_budget.add_argument("--volumes", type=int, default=0, help="Volume count. Defaults to project.yaml volumes or an inferred value.")
        word_budget.add_argument("--genre", default="", help="Genre preset, such as general, mystery, speculative, urban, or literary.")
        word_budget.add_argument("--time-span", default="", help="Story time-span note for platform-agent planning.")
        word_budget.add_argument("--outline", default="", help="Existing outline path. Defaults to plot/outline.md.")
        word_budget.add_argument("--out", default="", help="Output markdown path. Defaults to plot/word_budget/word_budget.md.")
        word_budget.add_argument("--json-out", default="", help="Output JSON path. Defaults to plot/word_budget/word_budget.json.")
        word_budget.add_argument("--agent-tasks-out", default="", help="Output agent task sidecar. Defaults to plot/word_budget/word_budget.agent_tasks.md.")

    longform = sub.add_parser("longform-audit", help="Audit long-form continuity, readiness, and graph structure.")
    longform.add_argument("project", help="Work project directory.")
    longform.add_argument("--target-length", type=int, default=100000)
    longform.add_argument("--out", default="", help="Output audit markdown path.")
    longform.add_argument("--json-out", default="", help="Output audit JSON path.")
    longform.add_argument("--graph-out", default="", help="Output lightweight graph JSON path.")

    export = sub.add_parser("export-package", help="Export a chapter as Markdown and optional DOCX artifacts.")
    export.add_argument("project", help="Work project directory.")
    export.add_argument("--chapter-id", default="chapter_0001")
    export.add_argument("--include-blocked", action="store_true", help="Maintainer/debug only; formal Skill hosts must not export non-ready scenes.")
    export.add_argument("--rebuild-chapter", action="store_true", help="Rebuild chapter workspace before export.")
    export.add_argument("--out-dir", default="", help="Output directory. Defaults to exports/{chapter_id}.")
    export.add_argument("--formats", default="md", help="Comma-separated output formats: md,docx. Defaults to md.")

    export_docx = sub.add_parser("export-docx", help="Export a Markdown/text artifact to an editable DOCX file.")
    export_docx.add_argument("source", help="Source Markdown or text file.")
    export_docx.add_argument("--out", default="", help="Output DOCX path. Defaults to source path with .docx suffix.")
    export_docx.add_argument("--title", default="", help="Document title override.")
    export_docx.add_argument("--kind", default="novel", choices=sorted(DOCX_KINDS), help="Document style preset.")
    export_docx.add_argument("--no-overwrite", action="store_true", help="Fail if the output DOCX already exists.")

    publish = sub.add_parser("publish-chapter", help="Publish a reviewed and approved chapter release.")
    publish.add_argument("project", help="Work project directory.")
    publish.add_argument("--chapter-id", default="chapter_0001")
    publish.add_argument("--release-id", default="", help="Release id. Defaults to a UTC timestamp.")
    publish.add_argument("--approval-run-id", default="", help="Require a matching approve record for this workflow run id.")
    publish.add_argument("--allow-unapproved", action="store_true", help="Maintainer/debug only; formal Skill hosts must not publish without approval.")
    publish.add_argument("--rebuild-chapter", action="store_true", help="Rebuild chapter workspace and reviews before publishing.")
    publish.add_argument("--rebuild-export", action="store_true", help="Rebuild export package before publishing.")
    publish.add_argument("--out-dir", default="", help="Output release directory. Defaults to releases/{chapter_id}/{release_id}.")
    publish.add_argument("--overwrite", action="store_true", help="Allow replacing an existing release directory.")
    publish.add_argument("--export-formats", default="md", help="Comma-separated export formats for release: md,docx.")

    workflow = sub.add_parser("run-workflow", help="Run a file-backed agent workflow and write state/log artifacts.")
    workflow.add_argument("project", help="Work project directory.")
    workflow.add_argument("--mode", default="full-cycle", choices=sorted(WORKFLOW_MODES))
    workflow.add_argument("--scene", default="scenes/scene_0001.yaml")
    workflow.add_argument("--chapter-id", default="chapter_0001")
    workflow.add_argument("--target-length", type=int, default=100000)
    workflow.add_argument("--include-blocked", action="store_true", help="Maintainer/debug only; formal Skill hosts must not export non-ready scenes.")
    workflow.add_argument("--overwrite-draft", action="store_true", help="Regenerate draft workspace even when one exists.")
    workflow.add_argument("--generate-candidate", action="store_true", help="Generate a scene candidate after scene composition.")
    workflow.add_argument("--promote-candidate", action="store_true", help="Promote the generated or latest candidate only after the formal candidate review gate passes.")
    workflow.add_argument("--agent-review", action="store_true", help="Run schema-gated agent scene/canon review nodes.")
    workflow.add_argument("--agent-tasks", action="store_true", help="Generate platform-agent task sidecars for creative workflow artifacts.")
    workflow.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal workflow writes platform-agent tasks.")
    workflow.add_argument("--run-id", default="", help="Use a stable workflow run id instead of an auto-generated one.")
    workflow.add_argument("--resume-run-id", default="", help="Create a new linked run that resumes/retries from a previous run id.")
    workflow.add_argument("--overwrite-run", action="store_true", help="Allow replacing an existing run directory with the same run id.")
    workflow.add_argument("--out-dir", default="", help="Workflow run directory. Defaults to workflow/runs/{run_id}.")

    approval = sub.add_parser("approval-summary", help="Summarize workflow approval records and follow-up tasks.")
    approval.add_argument("project", help="Work project directory.")
    approval.add_argument("--run-id", default="", help="Filter summary to one workflow run id.")
    approval.add_argument("--out", default="", help="Output markdown path. Defaults to workflow/approvals/approval_summary.md.")

    langgraph = sub.add_parser("run-langgraph", help="Run the literary workflow through a LangGraph StateGraph.")
    langgraph.add_argument("project", help="Work project directory.")
    langgraph.add_argument("--scene", default="scenes/scene_0001.yaml")
    langgraph.add_argument("--chapter-id", default="chapter_0001")
    langgraph.add_argument("--target-length", type=int, default=100000)
    langgraph.add_argument("--include-blocked", action="store_true", help="Maintainer/debug only; formal Skill hosts must not export non-ready scenes.")
    langgraph.add_argument("--overwrite-draft", action="store_true", help="Regenerate draft workspace even when one exists.")
    langgraph.add_argument("--generate-candidate", action="store_true", help="Generate a scene candidate after scene composition.")
    langgraph.add_argument("--promote-candidate", action="store_true", help="Promote the generated or latest candidate only after the formal candidate review gate passes.")
    langgraph.add_argument("--agent-review", action="store_true", help="Run schema-gated agent scene/canon review nodes.")
    langgraph.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal workflow writes platform-agent tasks.")
    langgraph.add_argument("--thread-id", default="", help="External orchestration thread id for LangGraph config.")

    serve = sub.add_parser("serve-api", help="Start a FastAPI backend for Dify and workflow clients.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument(
        "--allowed-root",
        action="append",
        default=[],
        help="Allowed project root or parent directory. Can be passed more than once.",
    )
    serve.add_argument(
        "--api-token",
        default="",
        help="Require this API token for workflow endpoints. If omitted, LEW_API_TOKEN is used when set.",
    )

    dify = sub.add_parser("dify-dsl", help="Generate a Dify Workflow DSL starter for the workbench API.")
    dify.add_argument("--out", default=str(DEFAULT_DIFY_DSL_PATH), help="Output YAML path.")
    dify.add_argument("--app-name", default="文学工程审稿台", help="Dify app name.")
    dify.add_argument("--api-base", default="http://127.0.0.1:8765", help="Workbench API base URL.")
    dify.add_argument("--dsl-version", default="0.6.0", help="Dify DSL version to declare. Defaults to 0.6.0.")
    dify.add_argument("--default-mode", default="full-cycle", choices=sorted(WORKFLOW_MODES))
    dify.add_argument("--default-scene", default="scenes/scene_0001.yaml")
    dify.add_argument("--default-chapter-id", default="chapter_0001")

    config_show = sub.add_parser("config-show", help="Show the global workbench configuration with secrets redacted.")
    config_show.add_argument("--raw", action="store_true", help="Show the normalized raw config instead of the effective view.")

    config_init = sub.add_parser("config-init", help="Create or reset the global workbench configuration.")
    config_init.add_argument("--overwrite", action="store_true", help="Overwrite an existing config with defaults.")

    config_set = sub.add_parser("config-set-profile", help="Create or update one global model provider profile.")
    config_set.add_argument("--name", default="deepseek", help="Profile name.")
    config_set.add_argument("--api-base", default="", help="HTTP chat API base URL.")
    config_set.add_argument("--model", default="", help="Model name.")
    config_set.add_argument("--api-key-env", default="", help="Environment variable that contains the API key.")
    config_set.add_argument("--temperature", type=float, default=None)
    config_set.add_argument("--max-tokens", type=int, default=None)
    config_set.add_argument("--timeout", type=float, default=None)
    config_set.add_argument("--project-root", default="", help="Default work project root for API/front-end workflows.")
    config_set.add_argument("--activate", action="store_true", help="Make this profile active.")

    return parser


def _read_prompt_arg(project: Path, file_arg: str, text_arg: str, label: str) -> str:
    if text_arg:
        return text_arg
    if not file_arg:
        raise ValueError(f"{label} prompt requires --{label} or --{label}-text")
    path = Path(file_arg)
    if not path.is_absolute():
        path = project / path
    if not path.exists():
        raise ValueError(f"{label} prompt file does not exist: {path}")
    return path.read_text(encoding="utf-8")


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "protocol":
        if not args.route:
            print(protocol_to_json(None) if args.json else render_protocol_list(), end="")
            return 0
        try:
            route = resolve_protocol_route(args.route)
        except KeyError as exc:
            parser.error(str(exc))
        print(protocol_to_json(route) if args.json else render_protocol(route), end="")
        return 0

    if args.command == "init":
        result = init_work_project(
            InitOptions(
                target=Path(args.target),
                title=args.title,
                work_type=args.type,
                target_length=args.target_length,
                language=args.language,
                premise=args.premise,
                genre=args.genre,
                style_mode=args.style_mode,
            )
        )
        print(f"created: {result.root}")
        print(f"files: {len(result.files)}")
        for file in result.files:
            print(f"- {file.relative_to(result.root).as_posix()}")
        return 0

    if args.command == "demo-project":
        try:
            result = build_demo_project(Path(args.target), title=args.title, run_agent_workflow=not args.skip_workflow)
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"demo: {result.root}")
        print(f"draft: {result.draft_path}")
        print(f"review: {result.review_path}")
        print(f"agent_scene_review: {result.agent_scene_review}")
        print(f"agent_canon_review: {result.agent_canon_review}")
        print(f"committee: {result.committee_review}")
        print(f"workflow_state: {result.workflow_state or 'n/a'}")
        print(f"report: {result.report_path}")
        return 0

    if args.command == "index":
        result = build_memory_index(Path(args.project))
        print(f"indexed: {result.project_root}")
        print(f"index: {result.index_path}")
        print(f"sources: {result.source_count}")
        print(f"chunks: {result.chunk_count}")
        return 0

    if args.command == "search":
        hits = search_memory(Path(args.project), args.query, top_k=args.top_k)
        print(f"hits: {len(hits)}")
        for i, hit in enumerate(hits, 1):
            preview = " ".join(hit.text.split())[:160]
            print(f"{i}. score={hit.score:.1f} source={hit.source} id={hit.chunk_id}")
            print(f"   {preview}")
        return 0

    if args.command == "knowledge-build":
        out = Path(args.out) if args.out else None
        result = build_knowledge_store(Path(args.project), backend=args.backend, output=out)
        print(f"knowledge_store: {result.store_path}")
        print(f"backend: {result.backend}")
        print(f"sources: {result.source_count}")
        print(f"items: {result.item_count}")
        return 0

    if args.command == "knowledge-search":
        hits = search_knowledge_store(
            Path(args.project),
            args.query,
            top_k=args.top_k,
            backend=args.backend,
            kind=args.kind,
            canon_status=args.canon_status,
        )
        print(f"hits: {len(hits)}")
        for i, hit in enumerate(hits, 1):
            preview = " ".join(hit.text.split())[:160]
            print(
                f"{i}. score={hit.score:.1f} source={hit.source} "
                f"kind={hit.kind} canon_status={hit.canon_status} id={hit.chunk_id}"
            )
            print(f"   {preview}")
        return 0

    if args.command == "canon-lint":
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        result = build_canon_lint(Path(args.project), output=out, json_output=json_out)
        print(f"canon_lint: {result.report_path}")
        print(f"json: {result.json_path}")
        print(f"status: {result.status}")
        print(f"issues: {result.issue_count}")
        print(f"blocking: {result.blocking_count}")
        print(f"warnings: {result.warning_count}")
        return 0

    if args.command == "context":
        out = Path(args.out) if args.out else None
        result = build_context_packet(
            Path(args.project),
            scene=Path(args.scene),
            query=args.query,
            top_k=args.top_k,
            rebuild_index=args.rebuild_index,
            output=out,
        )
        print(f"context: {result.output_path}")
        print(f"retrievals: {result.retrieval_count}")
        return 0

    if args.command in {"source-ingest", "extract-existing-work"}:
        if not args.source and not args.text:
            parser.error(f"{args.command} requires --source or --text")
        result = ingest_existing_work(
            Path(args.project),
            source=Path(args.source) if args.source else None,
            text=args.text,
            title=args.title,
            work_id=args.work_id,
            mode=args.mode,
            chunk_size=args.chunk_size,
            overwrite=args.overwrite,
        )
        print(f"source_import: {result.import_dir}")
        print(f"work_id: {result.work_id}")
        print(f"manifest: {result.manifest_path}")
        print(f"report: {result.report_path}")
        print(f"agent_task: {result.task_path}")
        print(f"sources: {result.source_count}")
        print(f"chunks: {result.chunk_count}")
        print("candidate_outputs:")
        for key, value in result.candidate_outputs.items():
            print(f"- {key}: {value}")
        print("receiver: platform-agent")
        return 0

    if args.command == "style-profile":
        result = compile_style_profile(
            StyleCompileOptions(
                corpus=Path(args.corpus),
                output_dir=Path(args.out_dir),
                name=args.name,
                author=args.author,
                mode=args.mode,
                source_note=args.source_note,
            )
        )
        print(f"style: {result.output_dir}")
        print(f"profile: {result.profile_path}")
        print(f"metrics: {result.metrics_path}")
        print(f"manifest: {result.corpus_manifest_path}")
        print(f"evaluation: {result.evaluation_dir}")
        print(f"sources: {result.source_count}")
        return 0

    if args.command == "style-eval":
        result = evaluate_style(
            StyleEvalOptions(
                profile_dir=Path(args.profile_dir),
                reference=Path(args.reference),
                candidate=Path(args.candidate),
                mode=args.mode,
                out_dir=Path(args.out_dir) if args.out_dir else None,
            )
        )
        print(f"style_eval_report: {result.report_path}")
        print(f"style_eval_metrics: {result.metrics_path}")
        print(f"mode: {result.mode}")
        print(f"overall_score: {result.overall_score}")
        print(f"risk_level: {result.risk_level}")
        return 0

    if args.command == "style-prompt":
        out = Path(args.out) if args.out else None
        manifest_out = Path(args.manifest_out) if args.manifest_out else None
        result = write_platform_style_prompt_task(
            Path(args.profile_dir),
            output=out,
            json_path=manifest_out,
        )
        print(f"style_prompt_task: {result.task_path}")
        print(f"expected_style_prompt: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        print("receiver: platform-agent")
        return 0

    if args.command == "style-prompt-eval":
        result = write_platform_style_prompt_eval_task(
            Path(args.profile_dir),
            reference=Path(args.reference),
            task_input=Path(args.input),
            mode=args.mode,
            style_prompt=Path(args.style_prompt) if args.style_prompt else None,
            output_dir=Path(args.out_dir) if args.out_dir else None,
        )
        print(f"style_prompt_eval_task: {result.task_path}")
        print(f"expected_candidate: {result.expected_report_path}")
        print(f"expected_prompt_manifest: {result.expected_json_path}")
        print("receiver: platform-agent")
        return 0

    if args.command == "style-lab-list":
        library = Path(args.library) if args.library else None
        print(json.dumps({"authors": list_author_projects(library), "style_skills": list_style_skills(library)}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "style-lab-author":
        result = create_author_project(
            Path(args.library) if args.library else None,
            name=args.name,
            author_id=args.author_id,
            mode=args.mode,
            source_note=args.source_note,
        )
        print(f"style_library: {result.library_root}")
        print(f"author_id: {result.author_id}")
        print(f"author_dir: {result.author_dir}")
        print(f"manifest: {result.manifest_path}")
        return 0

    if args.command == "style-lab-work":
        result = create_author_work(
            Path(args.library) if args.library else None,
            author_id=args.author_id,
            title=args.title,
            work_id=args.work_id,
            year=args.year,
            notes=args.notes,
        )
        print(f"style_library: {result.library_root}")
        print(f"author_id: {result.author_id}")
        print(f"work_id: {result.work_id}")
        print(f"work_dir: {result.work_dir}")
        print(f"manifest: {result.manifest_path}")
        return 0

    if args.command == "style-lab-import":
        if not args.text and not args.file:
            parser.error("style-lab-import requires --text or --file")
        result = import_work_source(
            Path(args.library) if args.library else None,
            author_id=args.author_id,
            work_id=args.work_id,
            text=args.text,
            source_path=Path(args.file) if args.file else None,
            filename=args.filename,
            chunk_chars=args.chunk_chars,
        )
        print(f"source_id: {result.source_id}")
        print(f"raw: {result.raw_path}")
        print(f"normalized: {result.normalized_path}")
        print(f"manifest: {result.manifest_path}")
        print(f"chunks: {result.chunk_count}")
        print(f"chars: {result.char_count}")
        return 0

    if args.command == "style-lab-compile":
        result = run_author_style_learning_platform_task(
            Path(args.library) if args.library else None,
            author_id=args.author_id,
            profile_id=args.profile_id,
        )
        print(f"profile_dir: {result.profile_dir}")
        print(f"profile: {result.profile_path}")
        print(f"metrics: {result.metrics_path}")
        print(f"style_prompt_task: {result.style_prompt_task_path}")
        print(f"expected_style_prompt: {result.expected_style_prompt_path}")
        print(f"expected_json: {result.expected_json_path}")
        print(f"sources: {result.source_count}")
        return 0

    if args.command == "style-lab-build-skill":
        result = build_style_skill(
            Path(args.library) if args.library else None,
            author_id=args.author_id,
            profile_id=args.profile_id,
            style_id=args.style_id,
        )
        print(f"style_id: {result.style_id}")
        print(f"skill_dir: {result.skill_dir}")
        print(f"manifest: {result.manifest_path}")
        print(f"style_markdown: {result.style_markdown_path}")
        print(f"prompt: {result.prompt_path}")
        return 0

    if args.command == "style-lab-mount":
        result = mount_style_skill(
            Path(args.project),
            library_root=Path(args.library) if args.library else None,
            style_id=args.style_id,
            allow_unreviewed=args.allow_unreviewed,
        )
        print(f"style_id: {result.style_id}")
        print(f"mount_dir: {result.mount_dir}")
        print(f"mount_manifest: {result.mount_manifest_path}")
        print(f"project_style: {result.project_style_path}")
        print(json.dumps(active_project_style(Path(args.project)), ensure_ascii=False, indent=2))
        return 0

    if args.command == "agent-run":
        project = Path(args.project)
        try:
            system_prompt = _read_prompt_arg(project, args.system, args.system_text, "system")
            user_prompt = _read_prompt_arg(project, args.user, args.user_text, "user")
            result = run_agent_task(
                project,
                agent_id=args.agent_id,
                task=args.task,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                provider=args.provider,
                output_dir=Path(args.out_dir) if args.out_dir else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"run_id: {result.run_id}")
        print(f"status: {result.status}")
        print(f"provider: {result.provider}")
        print(f"parse_status: {result.parse_status}")
        print(f"input: {result.input_path}")
        print(f"raw_output: {result.raw_output_path}")
        print(f"parsed_output: {result.parsed_output_path}")
        print(f"validation: {result.validation_path}")
        return 0

    if args.command == "agent-validate":
        try:
            result = validate_agent_run(
                Path(args.project),
                run_id=args.run_id,
                run_dir=Path(args.run_dir) if args.run_dir else None,
                schema_name=args.schema,
            )
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        print(f"schema: {result.schema_name}")
        print(f"status: {result.status}")
        print(f"errors: {result.error_count}")
        print(f"warnings: {result.warning_count}")
        print(f"validation: {result.validation_path}")
        return 0

    if args.command == "agent-repair":
        try:
            result = repair_agent_run(
                Path(args.project),
                run_id=args.run_id,
                run_dir=Path(args.run_dir) if args.run_dir else None,
                schema_name=args.schema,
                provider=args.provider,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"schema: {result.schema_name}")
        print(f"status: {result.status}")
        print(f"repair_run: {result.repair_run_dir}")
        print(f"validation: {result.validation_path}")
        return 0

    if args.command == "agent-review-scene":
        try:
            root = Path(args.project).resolve()
            scene_path = Path(args.scene)
            scene_path = scene_path if scene_path.is_absolute() else root / scene_path
            draft_path = Path(args.draft) if args.draft else root / "drafts" / "scenes" / f"{scene_path.stem}.md"
            draft_path = draft_path if draft_path.is_absolute() else root / draft_path
            result = write_platform_scene_review_task(
                root,
                scene_path=scene_path,
                draft_path=draft_path,
                report_path=Path(args.out) if args.out else None,
                json_path=Path(args.json_out) if args.json_out else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"agent_scene_review_task: {result.task_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        return 0

    if args.command == "agent-canon-review":
        try:
            result = write_platform_canon_review_task(Path(args.project).resolve())
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"agent_canon_review_task: {result.task_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        return 0

    if args.command == "agent-build-json":
        try:
            result = write_platform_json_task(
                Path(args.project).resolve(),
                schema_name=args.schema,
                task=args.task,
                source=Path(args.source) if args.source else None,
                target=args.target,
                output_dir=Path(args.out_dir) if args.out_dir else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"json_task: {result.task_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        print("receiver: platform-agent")
        return 0

    if args.command == "agent-plan-patch":
        try:
            result = write_platform_patch_plan_task(
                Path(args.project).resolve(),
                target=args.target,
                source=Path(args.source) if args.source else None,
                report_path=Path(args.out) if args.out else None,
                json_path=Path(args.json_out) if args.json_out else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"patch_plan_task: {result.task_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        print("receiver: platform-agent")
        return 0

    if args.command == "agent-style-prompt":
        try:
            result = write_platform_style_prompt_task(
                Path(args.profile_dir),
                output=Path(args.out) if args.out else None,
                json_path=Path(args.json_out) if args.json_out else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"style_prompt_task: {result.task_path}")
        print(f"expected_style_prompt: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        print("receiver: platform-agent")
        return 0

    if args.command == "agent-committee":
        try:
            root = Path(args.project).resolve()
            source = Path(args.source) if args.source else None
            if source and not source.is_absolute():
                source = root / source
            result = write_platform_committee_task(
                root,
                subject=args.subject,
                source=source,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"agent_committee_task: {result.task_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        return 0

    if args.command == "agent-task-status":
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        try:
            result = build_agent_task_status(Path(args.project), output=out, json_output=json_out)
        except FileNotFoundError as exc:
            parser.error(str(exc))
        print(f"agent_task_status: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"tasks: {result.task_count}")
        print(f"pending: {result.pending_count}")
        print(f"partial: {result.partial_count}")
        print(f"complete: {result.complete_count}")
        print(f"missing_expected: {result.missing_expected_count}")
        return 0

    if args.command == "route-audit":
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        try:
            result = build_route_audit(Path(args.project), route=args.route, output=out, json_output=json_out)
        except FileNotFoundError as exc:
            parser.error(str(exc))
        print(f"route_audit: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"route: {result.route}")
        print(f"gates: {result.gate_count}")
        print(f"blocking: {result.blocking_count}")
        print(f"warnings: {result.warning_count}")
        print(f"pending_tasks: {result.pending_task_count}")
        return 0

    if args.command == "director-chat":
        try:
            result = run_director_turn(
                Path(args.project),
                args.message,
                provider=args.provider,
                auto_execute=not args.no_execute,
                agent_tasks=args.agent_tasks,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"reply: {result.reply}")
        print(f"run_id: {result.run_id}")
        print(f"status: {result.status}")
        print(f"decision: {result.decision_path}")
        print(f"report: {result.report_path}")
        print(f"agent_run: {result.agent_run_dir}")
        print(f"validation: {result.validation_path}")
        if result.workflow_state_path:
            print(f"workflow_state: {result.workflow_state_path}")
        return 0

    if args.command == "director-status":
        data = build_director_status(Path(args.project), limit=args.limit)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.command in {
        "agent-create-character",
        "agent-create-background-story",
        "agent-create-relationship",
        "agent-create-world",
        "agent-create-location",
        "agent-create-organization",
        "agent-create-outline",
        "agent-create-chapter-plan",
        "agent-create-scene-list",
    }:
        try:
            result = write_platform_asset_creation_task(
                Path(args.project).resolve(),
                asset_type=args.asset_type,
                brief=args.brief,
                target_id=args.target_id,
                source=Path(args.source) if args.source else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"asset_creation_task: {result.task_path}")
        print(f"expected_candidate: {result.expected_json_path}")
        print(f"expected_report: {result.expected_report_path}")
        print("receiver: platform-agent")
        return 0

    if args.command == "asset-create":
        try:
            result = write_platform_asset_creation_task(
                Path(args.project).resolve(),
                asset_type=args.type,
                brief=args.brief,
                target_id=args.target_id,
                source=Path(args.source) if args.source else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"asset_creation_task: {result.task_path}")
        print(f"expected_candidate: {result.expected_json_path}")
        print(f"expected_report: {result.expected_report_path}")
        print("receiver: platform-agent")
        return 0

    if args.command == "list-candidate-assets":
        for item in list_asset_candidates(Path(args.project), asset_type=args.type):
            print(f"{item['candidate_id']}\t{item['asset_type']}\t{item['status']}\t{item['path']}\t{item['title']}")
        return 0

    if args.command == "review-candidate-asset":
        try:
            result = write_platform_asset_review_task(
                Path(args.project).resolve(),
                candidate_path=Path(args.candidate),
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"asset_review_task: {result.task_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        print("receiver: platform-agent")
        return 0

    if args.command == "promote-candidate-asset":
        try:
            result = promote_candidate_asset(
                Path(args.project),
                args.candidate,
                group=args.group,
                approval_run_id=args.approval_run_id,
                allow_unapproved=args.allow_unapproved,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"promotion: {result.report_path}")
        print(f"manifest: {result.manifest_path}")
        print(f"status: {result.status}")
        for path in result.output_paths:
            print(f"output: {path}")
        return 0

    if args.command in {"promote-character-candidate", "promote-world-candidate", "promote-outline-candidate"}:
        try:
            result = promote_candidate_asset(
                Path(args.project),
                args.candidate,
                group=args.promote_group,
                approval_run_id=args.approval_run_id,
                allow_unapproved=args.allow_unapproved,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"promotion: {result.report_path}")
        print(f"manifest: {result.manifest_path}")
        print(f"status: {result.status}")
        for path in result.output_paths:
            print(f"output: {path}")
        return 0

    if args.command == "draft-scene":
        context = Path(args.context) if args.context else None
        out = Path(args.out) if args.out else None
        result = build_scene_draft(
            Path(args.project),
            scene=Path(args.scene),
            context=context,
            query=args.query,
            rebuild_context=args.rebuild_context,
            output=out,
        )
        print(f"draft: {result.draft_path}")
        print(f"context: {result.context_path}")
        print(f"scene: {result.scene_id}")
        return 0

    if args.command == "review-scene":
        out = Path(args.out) if args.out else None
        result = review_scene_draft(Path(args.project), Path(args.draft), output=out)
        print(f"review: {result.report_path}")
        print(f"conclusion: {result.conclusion}")
        print(f"issues: {result.issue_count}")
        return 0

    if args.command == "generate-scene":
        try:
            root = Path(args.project).resolve()
            scene_path = _cli_path(root, args.scene)
            scene_id = scene_path.stem
            context_path = _cli_path(root, args.context) if args.context else root / "memory" / "context_packets" / f"{scene_id}.md"
            if args.rebuild_context or not context_path.exists():
                context_path = build_context_packet(root, scene=scene_path, query=args.query, rebuild_index=True, output=context_path).output_path
            composition = _cli_path(root, args.composition) if args.composition else None
            candidate = _cli_path(root, args.out) if args.out else root / "drafts" / "candidates" / f"{scene_id}-platform-agent.md"
            prompt_pack = build_scene_prompt_pack(
                root,
                scene_path,
                context_path,
                composition=composition,
                allow_unselected_composition=args.allow_unselected_composition,
                allow_missing_composition=args.allow_missing_composition,
            )
            prompt_manifest = candidate.with_suffix(".prompt.json")
            write_prompt_manifest(prompt_pack, prompt_manifest, provider="platform-agent", model="tool-layer-agent")
            result = write_platform_scene_generation_task(
                root,
                scene_path=scene_path,
                context_path=context_path,
                composition_path=prompt_pack.composition_path,
                prompt_manifest_path=prompt_manifest,
                candidate_path=candidate,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError, KeyError) as exc:
            parser.error(str(exc))
        print(f"scene_generation_task: {result.task_path}")
        print(f"expected_candidate: {result.expected_report_path}")
        print(f"expected_manifest: {result.expected_json_path}")
        print(f"prompt_manifest: {prompt_manifest}")
        print("receiver: platform-agent")
        print(f"scene: {scene_id}")
        return 0

    if args.command == "revise-scene":
        try:
            result = build_scene_revision_task(
                Path(args.project),
                scene=Path(args.scene),
                draft=Path(args.draft) if args.draft else None,
                review=Path(args.review) if args.review else None,
                query=args.query,
                rebuild_context=args.rebuild_context,
                output=Path(args.out) if args.out else None,
                report_output=Path(args.report_out) if args.report_out else None,
                manifest_output=Path(args.manifest_out) if args.manifest_out else None,
                prompt_manifest_output=Path(args.prompt_manifest_out) if args.prompt_manifest_out else None,
                task_output=Path(args.agent_tasks_out) if args.agent_tasks_out else None,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"revision_task: {result.task_path}")
        print(f"prompt_manifest: {result.prompt_manifest_path}")
        print(f"expected_candidate: {result.expected_candidate_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_manifest: {result.expected_manifest_path}")
        print(f"sources: {result.source_count}")
        print("receiver: platform-agent")
        print(f"scene: {result.scene_id}")
        return 0

    if args.command == "promote-candidate":
        candidate = Path(args.candidate) if args.candidate else None
        out = Path(args.out) if args.out else None
        try:
            result = promote_scene_candidate(
                Path(args.project),
                scene=Path(args.scene),
                candidate=candidate,
                output=out,
                overwrite=args.overwrite,
                approval_run_id=args.approval_run_id,
                selection_note=args.selection_note,
                allow_unreviewed=args.allow_unreviewed,
                allow_review_notes=args.allow_review_notes,
            )
        except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"draft: {result.draft_path}")
        print(f"candidate: {result.candidate_path}")
        print(f"manifest: {result.manifest_path}")
        print(f"report: {result.report_path}")
        print(f"scene: {result.scene_id}")
        print(f"chars: {result.chars}")
        print(f"approval_run_id: {result.approval_run_id or 'n/a'}")
        return 0

    if args.command == "state-evolve":
        source = Path(args.source) if args.source else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        result = build_character_state_patch(
            Path(args.project),
            scene=Path(args.scene),
            source=source,
            output=out,
            json_output=json_out,
            agent_tasks=args.agent_tasks,
        )
        print(f"state_patch: {result.output_path}")
        print(f"json: {result.json_path}")
        if result.agent_tasks_path:
            print(f"agent_tasks: {result.agent_tasks_path}")
        print(f"scene: {result.scene_id}")
        print(f"source: {result.source_path}")
        print(f"characters: {result.character_count}")
        print(f"unresolved: {result.unresolved_count}")
        return 0

    if args.command == "state-apply":
        patch = Path(args.patch) if args.patch else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        try:
            result = apply_character_state_patch(
                Path(args.project),
                patch=patch,
                approval_run_id=args.approval_run_id,
                allow_unapproved=args.allow_unapproved,
                allow_unresolved=args.allow_unresolved,
                output=out,
                json_output=json_out,
            )
        except RuntimeError as exc:
            parser.error(str(exc))
        print(f"state_apply: {result.report_path}")
        print(f"json: {result.manifest_path}")
        print(f"scene: {result.scene_id}")
        print(f"status: {result.status}")
        print(f"characters: {result.applied_character_count}")
        print(f"updates: {result.update_count}")
        print(f"approval_run_id: {result.approval_run_id or 'n/a'}")
        return 0

    if args.command == "simulate-scene":
        context = Path(args.context) if args.context else None
        out = Path(args.out) if args.out else None
        result = build_roleplay_simulation(
            Path(args.project),
            scene=Path(args.scene),
            context=context,
            query=args.query,
            rebuild_context=args.rebuild_context,
            output=out,
            agent_mode=args.agent_tasks,
        )
        print(f"simulation: {result.output_path}")
        print(f"context: {result.context_path}")
        print(f"scene: {result.scene_id}")
        print(f"characters: {result.character_count}")
        return 0

    if args.command == "branch-simulate":
        context = Path(args.context) if args.context else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        selection_out = Path(args.selection_out) if args.selection_out else None
        try:
            result = build_branch_simulation(
                Path(args.project),
                scene=Path(args.scene),
                context=context,
                query=args.query,
                rebuild_context=args.rebuild_context,
                branch_count=args.branch_count,
                output=out,
                json_output=json_out,
                selection_output=selection_out,
                agent_tasks=args.agent_tasks,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(f"branch_simulation: {result.output_path}")
        print(f"manifest: {result.manifest_path}")
        print(f"selection: {result.selection_path}")
        if result.agent_tasks_path:
            print(f"agent_tasks: {result.agent_tasks_path}")
        print(f"context: {result.context_path}")
        print(f"scene: {result.scene_id}")
        print(f"branches: {result.branch_count}")
        print(f"recommended: {result.recommended_branch}")
        return 0

    if args.command == "compose-scene":
        context = Path(args.context) if args.context else None
        manifest = Path(args.branch_manifest) if args.branch_manifest else None
        selection = Path(args.branch_selection) if args.branch_selection else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        try:
            result = build_scene_composition(
                Path(args.project),
                scene=Path(args.scene),
                context=context,
                query=args.query,
                rebuild_context=args.rebuild_context,
                branch_manifest=manifest,
                branch_selection=selection,
                output=out,
                json_output=json_out,
                agent_tasks=args.agent_tasks,
                allow_recommended_branch=args.allow_recommended_branch,
                allow_missing_branch=args.allow_missing_branch,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"composition: {result.output_path}")
        print(f"json: {result.json_path}")
        if result.agent_tasks_path:
            print(f"agent_tasks: {result.agent_tasks_path}")
        print(f"context: {result.context_path}")
        print(f"scene: {result.scene_id}")
        print(f"branch: {result.selected_branch}")
        print(f"characters: {result.character_count}")
        print(f"beats: {result.beat_count}")
        return 0

    if args.command == "orchestration-plan":
        platforms = [item.strip() for item in args.platforms.split(",")] if args.platforms else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        try:
            result = build_orchestration_blueprint(
                Path(args.project),
                platforms=platforms,
                output=out,
                json_output=json_out,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(f"blueprint: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"platforms: {result.platform_count}")
        print(f"nodes: {result.node_count}")
        return 0

    if args.command == "chapter-workspace":
        scenes = [Path(item.strip()) for item in args.scenes.split(",") if item.strip()] if args.scenes else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        result = build_chapter_workspace(
            Path(args.project),
            chapter_id=args.chapter_id,
            scenes=scenes,
            build_missing=args.build_missing,
            review_drafts=args.review_drafts,
            agent_review=args.agent_review,
            output=out,
            json_output=json_out,
        )
        print(f"chapter: {result.chapter_id}")
        print(f"workspace: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"scenes: {result.scene_count}")
        print(f"ready: {result.ready_count}")
        print(f"blocked: {result.blocked_count}")
        return 0

    if args.command in {"word-budget", "longform-budget"}:
        try:
            result = build_word_budget(
                Path(args.project),
                target_words=args.target_words,
                volumes=args.volumes,
                genre=args.genre,
                time_span=args.time_span,
                outline=Path(args.outline) if args.outline else None,
                output=Path(args.out) if args.out else None,
                json_output=Path(args.json_out) if args.json_out else None,
                agent_tasks_output=Path(args.agent_tasks_out) if args.agent_tasks_out else None,
            )
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        print(f"word_budget: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"agent_tasks: {result.agent_tasks_path}")
        print(f"scene_inventory_tasks: {result.scene_inventory_tasks_path}")
        print(f"target_words: {result.target_words}")
        print(f"volumes: {result.volume_count}")
        print(f"chapters: {result.chapter_count}")
        print(f"scenes: {result.scene_count}")
        print(f"status: {result.status}")
        print(f"issues: {result.issue_count}")
        print("receiver: platform-agent")
        return 0

    if args.command == "longform-audit":
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        graph_out = Path(args.graph_out) if args.graph_out else None
        result = build_longform_audit(
            Path(args.project),
            target_length=args.target_length,
            output=out,
            json_output=json_out,
            graph_output=graph_out,
        )
        print(f"audit: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"graph: {result.graph_path}")
        print(f"chapters: {result.chapter_count}")
        print(f"scenes: {result.scene_count}")
        print(f"draft_chars: {result.draft_chars}")
        print(f"issues: {result.issue_count}")
        return 0

    if args.command == "export-package":
        out_dir = Path(args.out_dir) if args.out_dir else None
        try:
            result = build_export_package(
                Path(args.project),
                chapter_id=args.chapter_id,
                include_blocked=args.include_blocked,
                rebuild_chapter=args.rebuild_chapter,
                output_dir=out_dir,
                formats=args.formats,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(f"chapter: {result.chapter_id}")
        print(f"output_dir: {result.output_dir}")
        print(f"manifest: {result.manifest_path}")
        print(f"novel: {result.novel_path}")
        print(f"screenplay: {result.screenplay_path}")
        print(f"video_prompt_pack: {result.video_prompt_path}")
        for key, path in result.docx_outputs.items():
            print(f"{key}_docx: {path}")
        for key, path in result.docx_layout_plans.items():
            print(f"{key}_docx_layout: {path}")
        for key, path in result.docx_inspections.items():
            print(f"{key}_docx_inspection: {path}")
        print(f"exported_scenes: {result.exported_scene_count}")
        print(f"skipped_scenes: {result.skipped_scene_count}")
        return 0

    if args.command == "export-docx":
        out = Path(args.out) if args.out else None
        try:
            result = export_markdown_to_docx(
                Path(args.source),
                out,
                title=args.title,
                kind=args.kind,
                overwrite=not args.no_overwrite,
            )
        except (FileNotFoundError, FileExistsError, ValueError) as exc:
            parser.error(str(exc))
        print(f"source: {result.source_path}")
        print(f"docx: {result.docx_path}")
        print(f"layout_plan: {result.layout_plan_path}")
        print(f"inspection: {result.inspection_path}")
        print(f"title: {result.title}")
        print(f"paragraphs: {result.paragraph_count}")
        print(f"warnings: {result.warning_count}")
        return 0

    if args.command == "publish-chapter":
        out_dir = Path(args.out_dir) if args.out_dir else None
        try:
            result = publish_chapter(
                Path(args.project),
                chapter_id=args.chapter_id,
                release_id=args.release_id,
                approval_run_id=args.approval_run_id,
                allow_unapproved=args.allow_unapproved,
                rebuild_chapter=args.rebuild_chapter,
                rebuild_export=args.rebuild_export,
                output_dir=out_dir,
                overwrite=args.overwrite,
                export_formats=args.export_formats,
            )
        except (RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"release: {result.release_dir}")
        print(f"manifest: {result.manifest_path}")
        print(f"notes: {result.notes_path}")
        print(f"rollback: {result.rollback_path}")
        print(f"latest: {result.latest_path}")
        print(f"status: {result.status}")
        print(f"chapter: {result.chapter_id}")
        print(f"release_id: {result.release_id}")
        print(f"published_scenes: {result.published_scene_count}")
        print(f"approval_run_id: {result.approval_run_id or 'n/a'}")
        return 0

    if args.command == "run-workflow":
        out_dir = Path(args.out_dir) if args.out_dir else None
        result = run_workflow(
            Path(args.project),
            mode=args.mode,
            scene=Path(args.scene),
            chapter_id=args.chapter_id,
            target_length=args.target_length,
            include_blocked=args.include_blocked,
            overwrite_draft=args.overwrite_draft,
            generate_candidate=args.generate_candidate,
            promote_candidate=args.promote_candidate,
            agent_review=args.agent_review,
            agent_tasks=args.agent_tasks,
            provider=args.provider,
            output_dir=out_dir,
            run_id=args.run_id or None,
            resumed_from=args.resume_run_id,
            overwrite_run=args.overwrite_run,
        )
        print(f"run_id: {result.run_id}")
        print(f"status: {result.status}")
        print(f"state: {result.state_path}")
        print(f"log: {result.log_path}")
        print(f"nodes: {result.node_count}")
        print(f"blocked: {str(result.blocked).lower()}")
        return 0

    if args.command == "approval-summary":
        out = Path(args.out) if args.out else None
        result = build_approval_summary(Path(args.project), run_id=args.run_id, output=out)
        print(f"approval_summary: {result.output_path}")
        print(f"records: {result.record_count}")
        print(f"tasks: {result.task_count}")
        return 0

    if args.command == "run-langgraph":
        try:
            result = run_literary_graph(
                Path(args.project),
                scene=Path(args.scene),
                chapter_id=args.chapter_id,
                target_length=args.target_length,
                include_blocked=args.include_blocked,
                overwrite_draft=args.overwrite_draft,
                generate_candidate=args.generate_candidate,
                promote_candidate=args.promote_candidate,
                agent_review=args.agent_review,
                provider=args.provider,
                thread_id=args.thread_id,
            )
        except RuntimeError as exc:
            parser.error(str(exc))
        print("langgraph_result:")
        for key in sorted(result):
            print(f"{key}: {result[key]}")
        return 0

    if args.command == "serve-api":
        try:
            import uvicorn

            from .api_server import create_app
        except ImportError as exc:
            parser.error(f"serve-api requires optional deps: fastapi, uvicorn, pydantic. {exc}")
        try:
            app = create_app(
                allowed_roots=[Path(item) for item in args.allowed_root],
                api_token=args.api_token or os.environ.get("LEW_API_TOKEN", ""),
            )
        except RuntimeError as exc:
            parser.error(str(exc))
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    if args.command == "dify-dsl":
        result = build_dify_workflow_dsl(
            DifyDslOptions(
                output=Path(args.out),
                app_name=args.app_name,
                api_base=args.api_base,
                dsl_version=args.dsl_version,
                default_mode=args.default_mode,
                default_scene=args.default_scene,
                default_chapter_id=args.default_chapter_id,
            )
        )
        print(f"dify_dsl: {result.output_path}")
        print(f"app_name: {result.app_name}")
        print(f"api_base: {result.api_base}")
        print(f"nodes: {result.node_count}")
        print(f"endpoints: {result.endpoint_count}")
        return 0

    if args.command == "config-show":
        data = load_config() if args.raw else redacted_effective_config()
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.command == "config-init":
        path = config_path()
        if path.exists() and not args.overwrite:
            print(f"config_exists: {path}")
            print("use --overwrite to reset it")
            return 0
        path = save_config(default_config())
        print(f"config: {path}")
        print(json.dumps(redacted_effective_config(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "config-set-profile":
        cfg = load_config()
        profiles = cfg.setdefault("profiles", {})
        profile = dict(profiles.get(args.name, {}))
        if args.api_base:
            profile["api_base"] = args.api_base
        if args.model:
            profile["model"] = args.model
        if args.api_key_env:
            profile["api_key_env"] = args.api_key_env
        if args.temperature is not None:
            profile["temperature"] = args.temperature
        if args.max_tokens is not None:
            profile["max_tokens"] = args.max_tokens
        if args.timeout is not None:
            profile["timeout"] = args.timeout
        profile.setdefault("provider", "http-chat")
        profile.setdefault("api_key_env", "LEW_MODEL_API_KEY")
        profiles[args.name] = profile
        if args.activate or not cfg.get("active_profile"):
            cfg["active_profile"] = args.name
        if args.project_root:
            cfg.setdefault("defaults", {})["project_root"] = args.project_root
        path = save_config(cfg)
        print(f"config: {path}")
        print(json.dumps(redacted_effective_config(), ensure_ascii=False, indent=2))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def _cli_path(root: Path, value: str | Path) -> Path:
    path = value if isinstance(value, Path) else Path(value)
    return path if path.is_absolute() else root / path
