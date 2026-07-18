"""CLI-mediated task registry for formal platform-agent work."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Callable

from .agent_tasks import agent_task_completion_status, default_agent_completion_path, write_agent_completion_marker
from .agent_schema import validate_payload
from .anti_ai_style import style_lint_gate, style_lint_gate_message
from .asset_workshop import ASSET_CANDIDATE_DIRS, ASSET_SCHEMA_NAMES, PROMOTABLE_GROUPS
from .candidate_promotion import candidate_generation_gate, candidate_review_gate
from .draft_text import final_body_from_draft_path
from .flow_gates import FlowGateError, branch_selection_status, ensure_composition_ready_for_generation
from .style_prompt import style_prompt_quality_report
from .word_budget import ensure_scene_word_budget_ready, word_budget_adherence_for_body
from .workflow_state import build_workflow_state


TASK_SCHEMA = "literary-engineering-workbench/agent-task/v1"
SUBMISSION_SCHEMA = "literary-engineering-workbench/agent-submission/v1"
EVENT_SCHEMA = "literary-engineering-workbench/workflow-event/v1"
SUPPORTED_ROUTES = {"scene-development", "longform-planning", "source-ingest", "style-engineering", "character-and-world-assets"}


@dataclass(frozen=True)
class RouteDefinition:
    route: str
    ready_message: str
    select_work_item: Callable[[Path, dict[str, object], Path | str | None], dict[str, object] | None]
    build_task: Callable[[Path, str, dict[str, object]], dict[str, object]]
    validate_task: Callable[[Path, dict[str, object]], tuple[list[str], list[str]]]


@dataclass(frozen=True)
class TaskRegistryResult:
    project_root: Path
    task_id: str
    task_json_path: Path | None
    task_markdown_path: Path | None
    status: str
    route: str
    scene_id: str
    current_state: str
    message: str
    expected_output_count: int = 0


@dataclass(frozen=True)
class TaskSubmissionResult:
    project_root: Path
    task_id: str
    task_json_path: Path
    submission_path: Path
    status: str
    artifact_count: int
    message: str


@dataclass(frozen=True)
class WorkflowEventsResult:
    project_root: Path
    events_path: Path
    markdown_path: Path
    event_count: int


def issue_next_task(
    project_root: Path,
    *,
    route: str = "scene-development",
    scene: Path | str | None = None,
    force: bool = False,
) -> TaskRegistryResult:
    """Issue the next formal platform-agent task from the derived workflow state."""

    root = project_root.resolve()
    normalized_route = _normalize_route(route or "scene-development")
    if normalized_route not in SUPPORTED_ROUTES:
        raise ValueError(f"task registry supports {', '.join(sorted(SUPPORTED_ROUTES))}, got: {normalized_route}")
    route_def = _route_definition(normalized_route)
    state_payload = _workflow_payload(root, normalized_route)
    work_item = route_def.select_work_item(root, state_payload, scene)
    if work_item is None:
        return TaskRegistryResult(
            project_root=root,
            task_id="",
            task_json_path=None,
            task_markdown_path=None,
            status="ready",
            route=normalized_route,
            scene_id="",
            current_state="ready",
            message=route_def.ready_message,
        )
    scene_id = str(work_item.get("scene_id") or work_item.get("target_id") or "")
    current_state = str(work_item.get("current_step") or "")
    if not scene_id or current_state == "ready":
        return TaskRegistryResult(
            project_root=root,
            task_id="",
            task_json_path=None,
            task_markdown_path=None,
            status="ready",
            route=normalized_route,
            scene_id=scene_id,
            current_state="ready",
            message=route_def.ready_message,
        )

    task = route_def.build_task(root, normalized_route, work_item)
    task_id = str(task["task_id"])
    task_json = _task_json_path(root, task_id)
    task_markdown = _task_markdown_path(root, task_id)
    task["task_json"] = _rel(task_json, root)
    task["task_markdown"] = _rel(task_markdown, root)

    if task_json.exists() and not force:
        existing = _read_json(task_json)
        existing_status = str(existing.get("status") or "")
        if existing_status in {"issued", "opened", "submitted", "blocked"}:
            return TaskRegistryResult(
                project_root=root,
                task_id=task_id,
                task_json_path=task_json,
                task_markdown_path=task_markdown,
                status=existing_status,
                route=normalized_route,
                scene_id=str(existing.get("scene_id") or scene_id),
                current_state=current_state,
                message="existing active task returned; use --force to refresh",
                expected_output_count=len(existing.get("expected_outputs") or []),
            )

    task_json.parent.mkdir(parents=True, exist_ok=True)
    task_markdown.parent.mkdir(parents=True, exist_ok=True)
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task_markdown.write_text(_render_task_markdown(task, root), encoding="utf-8")
    _append_event(root, "task_issued", task_id, {"route": normalized_route, "scene_id": scene_id, "current_state": current_state})
    return TaskRegistryResult(
        project_root=root,
        task_id=task_id,
        task_json_path=task_json,
        task_markdown_path=task_markdown,
        status="issued",
        route=normalized_route,
        scene_id=scene_id,
        current_state=current_state,
        message="task issued",
        expected_output_count=len(task.get("expected_outputs") or []),
    )


def open_task(project_root: Path, task_id: str) -> TaskRegistryResult:
    """Mark a task as opened and rewrite its readable task package."""

    root = project_root.resolve()
    task_json = _task_json_path(root, task_id)
    task = _load_task(task_json)
    task["status"] = "opened"
    task["opened_at"] = _now()
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task_markdown = _task_markdown_path(root, task_id)
    task_markdown.write_text(_render_task_markdown(task, root), encoding="utf-8")
    _append_event(root, "task_opened", task_id, {"route": task.get("route", ""), "scene_id": task.get("scene_id", "")})
    return TaskRegistryResult(
        project_root=root,
        task_id=task_id,
        task_json_path=task_json,
        task_markdown_path=task_markdown,
        status="opened",
        route=str(task.get("route") or ""),
        scene_id=str(task.get("scene_id") or ""),
        current_state=str(task.get("current_state") or ""),
        message="task opened",
        expected_output_count=len(task.get("expected_outputs") or []),
    )


def submit_task(
    project_root: Path,
    task_id: str,
    artifacts: list[Path | str],
    *,
    note: str = "",
) -> TaskSubmissionResult:
    """Record platform-agent outputs for a formal task."""

    root = project_root.resolve()
    task_json = _task_json_path(root, task_id)
    task = _load_task(task_json)
    if not artifacts:
        raise ValueError("task-submit requires at least one --from artifact")
    rel_artifacts: list[str] = []
    missing: list[str] = []
    for item in artifacts:
        path = _resolve_project_path(root, item)
        rel = _rel(path, root)
        rel_artifacts.append(rel)
        if not path.exists():
            missing.append(rel)
    if missing:
        raise FileNotFoundError(f"submitted artifacts do not exist: {', '.join(missing)}")
    submission_path = _submission_path(root, task_id)
    payload = {
        "schema": SUBMISSION_SCHEMA,
        "task_id": task_id,
        "route": task.get("route", ""),
        "scene_id": task.get("scene_id", ""),
        "submitted_at": _now(),
        "submitted_by": "platform-agent",
        "artifacts": rel_artifacts,
        "note": note,
    }
    submission_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task["status"] = "submitted"
    task["submission"] = _rel(submission_path, root)
    task["submitted_artifacts"] = rel_artifacts
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _append_event(root, "task_submitted", task_id, {"artifacts": rel_artifacts})
    return TaskSubmissionResult(
        project_root=root,
        task_id=task_id,
        task_json_path=task_json,
        submission_path=submission_path,
        status="submitted",
        artifact_count=len(rel_artifacts),
        message="task submission recorded",
    )


def complete_task(
    project_root: Path,
    task_id: str,
    *,
    handled_by: str = "platform-agent",
    notes: list[str] | None = None,
) -> TaskRegistryResult:
    """Validate task outputs and write the formal completion marker."""

    root = project_root.resolve()
    task_json = _task_json_path(root, task_id)
    task = _load_task(task_json)
    expected_outputs = [str(item) for item in task.get("expected_outputs") or []]
    missing = [item for item in expected_outputs if not _resolve_project_path(root, item).exists()]
    validation_notes: list[str] = []
    if missing:
        _block_task(root, task_json, task, task_id, f"missing expected outputs: {', '.join(missing)}")
        raise FileNotFoundError(f"missing expected outputs: {', '.join(missing)}")

    route = str(task.get("route") or "scene-development")
    gate_errors, gate_notes = _route_definition(route).validate_task(root, task)
    if gate_errors:
        message = "; ".join(gate_errors)
        _block_task(root, task_json, task, task_id, message)
        raise ValueError(message)
    validation_notes.extend(gate_notes)

    completion_path = default_agent_completion_path(_task_markdown_path(root, task_id))
    write_agent_completion_marker(
        _task_markdown_path(root, task_id),
        root=root,
        handled_by=handled_by,
        notes=[*(notes or []), *validation_notes],
    )
    task["status"] = "complete"
    task["completed_at"] = _now()
    task["completion"] = _rel(completion_path, root)
    task["validation"] = {"status": "pass", "missing_expected_outputs": [], "notes": validation_notes}
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _append_event(root, "task_completed", task_id, {"completion": _rel(completion_path, root)})
    state = build_workflow_state(root, route=route)
    _append_event(root, "workflow_state_refreshed", task_id, {"state": _rel(state.json_path, root)})
    return TaskRegistryResult(
        project_root=root,
        task_id=task_id,
        task_json_path=task_json,
        task_markdown_path=_task_markdown_path(root, task_id),
        status="complete",
        route=str(task.get("route") or ""),
        scene_id=str(task.get("scene_id") or ""),
        current_state=str(task.get("current_state") or ""),
        message="task completed and workflow state refreshed",
        expected_output_count=len(expected_outputs),
    )


def advance_workflow(
    project_root: Path,
    *,
    route: str = "scene-development",
) -> TaskRegistryResult:
    """Refresh the derived workflow state without allowing manual state jumps."""

    root = project_root.resolve()
    normalized_route = _normalize_route(route or "scene-development")
    if normalized_route not in SUPPORTED_ROUTES:
        raise ValueError(f"task registry supports {', '.join(sorted(SUPPORTED_ROUTES))}, got: {normalized_route}")
    state = build_workflow_state(root, route=normalized_route)
    _append_event(root, "workflow_advanced", "", {"route": normalized_route, "state": _rel(state.json_path, root)})
    return TaskRegistryResult(
        project_root=root,
        task_id="",
        task_json_path=state.json_path,
        task_markdown_path=state.markdown_path,
        status="refreshed",
        route=normalized_route,
        scene_id="",
        current_state="derived",
        message="workflow state refreshed from artifacts; no manual state override performed",
        expected_output_count=0,
    )


def build_workflow_events(
    project_root: Path,
    *,
    output: Path | None = None,
) -> WorkflowEventsResult:
    root = project_root.resolve()
    events_path = _events_path(root)
    events = _read_events(events_path)
    markdown_path = output if output and output.is_absolute() else root / (output or Path("workflow/events.md"))
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(_render_events_markdown(events), encoding="utf-8")
    return WorkflowEventsResult(root, events_path, markdown_path, len(events))


def _route_definition(route: str) -> RouteDefinition:
    normalized = _normalize_route(route or "scene-development")
    definitions = {
        "scene-development": RouteDefinition(
            route="scene-development",
            ready_message="no pending scene-development task found",
            select_work_item=_select_scene_state,
            build_task=_build_task_payload,
            validate_task=_state_gate_validation,
        ),
        "longform-planning": RouteDefinition(
            route="longform-planning",
            ready_message="longform-planning route is ready",
            select_work_item=_select_longform_state,
            build_task=_build_longform_task_payload,
            validate_task=_longform_state_gate_validation,
        ),
        "source-ingest": RouteDefinition(
            route="source-ingest",
            ready_message="source-ingest route has no pending imported source",
            select_work_item=_select_source_ingest_state,
            build_task=_build_source_ingest_task_payload,
            validate_task=_source_ingest_state_gate_validation,
        ),
        "style-engineering": RouteDefinition(
            route="style-engineering",
            ready_message="style-engineering route has no pending style profile",
            select_work_item=_select_style_engineering_state,
            build_task=_build_style_engineering_task_payload,
            validate_task=_style_engineering_state_gate_validation,
        ),
        "character-and-world-assets": RouteDefinition(
            route="character-and-world-assets",
            ready_message="character-and-world-assets route has no pending candidate asset",
            select_work_item=_select_asset_state,
            build_task=_build_asset_task_payload,
            validate_task=_asset_state_gate_validation,
        ),
    }
    try:
        return definitions[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported route: {route}") from exc


def _build_task_payload(root: Path, route: str, scene_state: dict[str, object]) -> dict[str, object]:
    scene_id = str(scene_state.get("scene_id") or "")
    scene_rel = str(scene_state.get("scene") or f"scenes/{scene_id}.yaml")
    current_state = str(scene_state.get("current_step") or "")
    next_action = str(scene_state.get("next_action") or "")
    blueprint = _blueprint_for_state(root, scene_id, scene_rel, current_state, next_action)
    task_id = _task_id(route, scene_id, current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    return {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": scene_id,
        "scene": scene_rel,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": [
            "SKILL.md",
            "AGENTS.md",
            "agentread.yaml",
            "references/agent-run-protocol.md",
            "references/cli-run-protocol.md",
            "references/punctuation-standard.md",
        ],
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": blueprint.get("word_count_target", 0),
        "word_count_min": blueprint.get("word_count_min", 0),
        "word_count_max": blueprint.get("word_count_max", 0),
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_workbench task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_workbench task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not hand-write same-named formal files to bypass the documented command.",
            "Do not use debug/bypass flags such as --allow-unreviewed, --allow-review-notes, --include-blocked, --allow-unapproved, --allow-missing-composition, --allow-unselected-composition, --allow-recommended-branch, or --allow-missing-branch.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
            "Do not let subagents draft, revise, polish, expand, or finalize creative body text.",
            "Do not write API keys or provider secrets into the work project.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }


def _build_longform_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = _longform_blueprint_for_state(root, current_state, next_action)
    task_id = _task_id(route, "longform", current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    return {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": "longform",
        "target_id": "longform",
        "scene": "project.yaml",
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get(
            "required_reading",
            [
                "SKILL.md",
                "AGENTS.md",
                "agentread.yaml",
                "references/agent-run-protocol.md",
                "references/cli-run-protocol.md",
                "docs/modules/longform-word-budget.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": blueprint.get("word_count_target", 0),
        "word_count_min": blueprint.get("word_count_min", 0),
        "word_count_max": blueprint.get("word_count_max", 0),
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_workbench task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_workbench task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not treat word_budget.json as final plot or sufficient narrative inventory by itself.",
            "Do not bypass word_budget.agent_tasks.md or scene_inventory_expansion.agent_tasks.md.",
            "Do not start bulk scene generation while longform-planning is blocked.",
            "Do not satisfy target length by making each scene verbose; expand narrative inventory instead.",
            "Do not overwrite formal plot/outline.md or scenes/ before candidate review and user approval.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }


def _build_source_ingest_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    work_id = str(state.get("work_id") or state.get("target_id") or "")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    import_dir = str(state.get("import_dir") or f"sources/imports/{work_id}")
    blueprint = _source_ingest_blueprint_for_state(root, work_id, import_dir, current_state, next_action)
    task_id = _task_id(route, work_id or "source", current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    return {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": work_id,
        "target_id": work_id,
        "work_id": work_id,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get(
            "required_reading",
            [
                "SKILL.md",
                "AGENTS.md",
                "agentread.yaml",
                "references/agent-run-protocol.md",
                "references/cli-run-protocol.md",
                "references/artifact-contracts.md",
                "references/workflows.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": 0,
        "word_count_min": 0,
        "word_count_max": 0,
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_workbench task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_workbench task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not write source-derived material directly into canon, character, plot, draft, export, or release files.",
            "Do not treat extracted claims as confirmed facts without evidence_refs, confidence, unknowns, contradiction notes, review, and approval.",
            "Do not skip extract_project_files.agent_tasks.md after source-ingest creates it.",
            "Do not copy long source passages into extraction reports.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }


def _build_style_engineering_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    profile_id = str(state.get("profile_id") or state.get("target_id") or "")
    profile_dir = str(state.get("profile_dir") or "")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = _style_engineering_blueprint_for_state(root, profile_id, profile_dir, current_state, next_action)
    task_id = _task_id(route, profile_id or "style-profile", current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    return {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": profile_id,
        "target_id": profile_id,
        "profile_id": profile_id,
        "profile_dir": profile_dir,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get(
            "required_reading",
            [
                "SKILL.md",
                "AGENTS.md",
                "agentread.yaml",
                "references/agent-run-protocol.md",
                "references/cli-run-protocol.md",
                "references/workflows.md",
                "docs/modules/style-compiler.md",
                "docs/implementation/phase26-style-prompt-effectiveness.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": 0,
        "word_count_min": 0,
        "word_count_max": 0,
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_workbench task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_workbench task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not mount a Style Skill from an under-specified prompt.",
            "Do not use --allow-unreviewed for formal Skill-host work.",
            "Do not treat style metrics or a dry profile report as an LLM-facing prompt.",
            "Do not pursue exact author imitation unless the corpus is public-domain, authorized, or user-owned.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }


def _build_asset_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    candidate_id = str(state.get("candidate_id") or state.get("target_id") or "asset-intake")
    asset_type = str(state.get("asset_type") or "")
    candidate = str(state.get("candidate") or "")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = _asset_blueprint_for_state(root, candidate_id, asset_type, candidate, current_state, next_action)
    task_id = _task_id(route, candidate_id, current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    return {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": candidate_id,
        "target_id": candidate_id,
        "candidate_id": candidate_id,
        "asset_type": asset_type,
        "candidate": candidate,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get(
            "required_reading",
            [
                "SKILL.md",
                "AGENTS.md",
                "agentread.yaml",
                "references/agent-run-protocol.md",
                "references/cli-run-protocol.md",
                "references/artifact-contracts.md",
                "references/workflows.md",
                "docs/implementation/phase38-agent-character-creation.md",
                "docs/implementation/phase41-candidate-review-promotion.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": 0,
        "word_count_min": 0,
        "word_count_max": 0,
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_workbench task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_workbench task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not write directly into canon/, characters/, plot/outline.md, scenes/, drafts/, exports/, or releases/ from a candidate task.",
            "Do not promote any candidate asset without a clean platform-agent asset review and an approve record.",
            "Do not use --allow-unapproved or any debug approval bypass in formal Skill-host work.",
            "Do not let extracted/source-derived claims become canon without evidence_refs, confidence, review, and approval.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }


def _blueprint_for_state(root: Path, scene_id: str, scene_rel: str, current_state: str, next_action: str) -> dict[str, object]:
    context = f"memory/context_packets/{scene_id}.md"
    branch_dir = f"branches/{scene_id}"
    composition = f"drafts/compositions/{scene_id}_composition"
    candidate = f"drafts/candidates/{scene_id}-platform-agent"
    review = f"reviews/agent/{scene_id}_scene_review"
    state_patch = f"characters/state_patches/{scene_id}_state_patch"
    common_sources = [scene_rel]
    table: dict[str, dict[str, object]] = {
        "context-packet": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.context.v1",
            "command": f"python -m literary_engineering_workbench context <project> --scene {scene_rel}",
            "source_paths": common_sources,
            "expected_outputs": [context],
            "hard_constraints": ["Run the documented context command; inspect the output path before submitting."],
            "style_constraints": [],
            "validation_gates": ["context packet exists"],
            "next_allowed_states": ["roleplay-simulation"],
        },
        "roleplay-simulation": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.roleplay.prepare.v1",
            "command": f"python -m literary_engineering_workbench simulate-scene <project> --scene {scene_rel} --agent",
            "source_paths": [scene_rel, context],
            "expected_outputs": [f"{branch_dir}/roleplay_simulation.md", f"{branch_dir}/roleplay_simulation.agent_tasks.md"],
            "hard_constraints": ["Use --agent so the platform-agent RP task is emitted as a sidecar."],
            "style_constraints": [],
            "validation_gates": ["roleplay simulation exists", "roleplay sidecar exists"],
            "next_allowed_states": ["roleplay-agent-task"],
        },
        "roleplay-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.roleplay.execute.v1",
            "command": "",
            "source_paths": [scene_rel, context, f"{branch_dir}/roleplay_simulation.md", f"{branch_dir}/roleplay_simulation.agent_tasks.md"],
            "expected_outputs": [f"{branch_dir}/roleplay_simulation.agent_completion.json"],
            "hard_constraints": [
                "Read the roleplay sidecar and fill roleplay/world/branch/canon/writeback reasoning as platform agent.",
                "Create the original roleplay_simulation.agent_completion.json before continuing.",
            ],
            "style_constraints": [],
            "validation_gates": ["roleplay sidecar completion marker exists"],
            "next_allowed_states": ["branch-manifest"],
        },
        "branch-manifest": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.branch.prepare.v1",
            "command": f"python -m literary_engineering_workbench branch-simulate <project> --scene {scene_rel} --agent",
            "source_paths": [scene_rel, context, f"{branch_dir}/roleplay_simulation.md"],
            "expected_outputs": [f"{branch_dir}/branch_simulation.md", f"{branch_dir}/branch_manifest.json", f"{branch_dir}/branch_manifest.agent_tasks.md"],
            "hard_constraints": ["Use --agent so branch review and selection tasks are emitted."],
            "style_constraints": [],
            "validation_gates": ["branch manifest exists", "branch sidecar exists"],
            "next_allowed_states": ["branch-agent-task"],
        },
        "branch-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.branch.execute.v1",
            "command": "",
            "source_paths": [scene_rel, context, f"{branch_dir}/branch_simulation.md", f"{branch_dir}/branch_manifest.json", f"{branch_dir}/branch_manifest.agent_tasks.md"],
            "expected_outputs": [f"{branch_dir}/branch_selection.md", f"{branch_dir}/branch_manifest.agent_completion.json"],
            "hard_constraints": ["Read branch candidates, write formal selected decision, and complete the branch sidecar marker."],
            "style_constraints": [],
            "validation_gates": ["branch_selection.md exists", "branch sidecar completion marker exists"],
            "next_allowed_states": ["branch-selection"],
        },
        "branch-selection": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.branch.selection.v1",
            "command": "",
            "source_paths": [scene_rel, f"{branch_dir}/branch_manifest.json", f"{branch_dir}/branch_selection.md"],
            "expected_outputs": [f"{branch_dir}/branch_selection.md"],
            "hard_constraints": ["branch_selection.md must contain decision: selected and selected_branch before composition."],
            "style_constraints": [],
            "validation_gates": ["branch_selection_status == selected"],
            "next_allowed_states": ["composition-json"],
        },
        "composition-json": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.composition.prepare.v1",
            "command": f"python -m literary_engineering_workbench compose-scene <project> --scene {scene_rel} --agent-tasks",
            "source_paths": [scene_rel, context, f"{branch_dir}/branch_manifest.json", f"{branch_dir}/branch_selection.md"],
            "expected_outputs": [f"{composition}.md", f"{composition}.json", f"{composition}.agent_tasks.md"],
            "hard_constraints": ["Composition must use formal branch_selection and created_by=compose-scene provenance."],
            "style_constraints": [],
            "validation_gates": ["composition JSON exists", "composition sidecar exists"],
            "next_allowed_states": ["composition-agent-task"],
        },
        "composition-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.composition.execute.v1",
            "command": "",
            "source_paths": [scene_rel, context, f"{composition}.md", f"{composition}.json", f"{composition}.agent_tasks.md"],
            "expected_outputs": [f"{composition}.agent_completion.json"],
            "hard_constraints": ["Read the composition sidecar, perform platform-agent composition review, and complete the marker."],
            "style_constraints": [],
            "validation_gates": ["composition sidecar completion marker exists"],
            "next_allowed_states": ["scene-word-budget-contract"],
        },
        "scene-word-budget-contract": {
            "task_type": "deterministic-cli-plus-platform-review",
            "prompt_asset_id": "route.longform-planning.scene-budget.v1",
            "command": "python -m literary_engineering_workbench word-budget <project> --target-words <target>",
            "source_paths": [scene_rel, "project.yaml", "plot/word_budget/word_budget.json"],
            "expected_outputs": ["plot/word_budget/word_budget.json"],
            "hard_constraints": ["Longform scenes must carry word_count_target/min/max before formal generation."],
            "style_constraints": [],
            "validation_gates": ["scene word budget contract passes or is not required"],
            "next_allowed_states": ["candidate-generation-provenance"],
        },
        "candidate-generation-provenance": {
            "task_type": "main-platform-agent-prose",
            "prompt_asset_id": "route.scene-development.prose.generate.v1",
            "command": f"python -m literary_engineering_workbench generate-scene <project> --scene {scene_rel}",
            "source_paths": [scene_rel, context, f"{composition}.md", f"{composition}.json"],
            "expected_outputs": [f"{candidate}.md", f"{candidate}.json", f"{candidate}.prompt.json", f"{candidate}.agent_tasks.md", f"{candidate}.agent_completion.json"],
            "hard_constraints": [
                "Run generate-scene to obtain prompt manifest and sidecar, then the main platform agent personally writes the candidate body.",
                "The candidate must not be drafted by a subagent and must not include workflow traces.",
            ],
            "style_constraints": [
                "Apply mounted Style Skill first at expression level.",
                "Apply punctuation standard, Style Lint Gate, and anti-evasion rules before submitting.",
            ],
            "validation_gates": ["candidate Markdown exists", "candidate manifest exists", "prompt manifest exists", "generation sidecar completion marker exists"],
            "next_allowed_states": ["generation-agent-task", "candidate-review"],
        },
        "generation-agent-task": {
            "task_type": "main-platform-agent-prose",
            "prompt_asset_id": "route.scene-development.prose.complete.v1",
            "command": "",
            "source_paths": [scene_rel, f"{candidate}.prompt.json", f"{candidate}.agent_tasks.md"],
            "expected_outputs": [f"{candidate}.md", f"{candidate}.json", f"{candidate}.agent_completion.json"],
            "hard_constraints": ["Complete the generate-scene sidecar after candidate Markdown and manifest are checked."],
            "style_constraints": ["Candidate must satisfy style, punctuation, word budget, and anti-evasion protocol before completion."],
            "validation_gates": ["generation sidecar completion marker exists"],
            "next_allowed_states": ["candidate-review"],
        },
        "candidate-review": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.scene-development.agent-review.v1",
            "command": f"python -m literary_engineering_workbench agent-review-scene <project> --scene {scene_rel} --draft {candidate}.md",
            "source_paths": [scene_rel, f"{candidate}.md", f"{candidate}.json", context],
            "expected_outputs": [f"{review}.json", f"{review}.md", f"{review}.agent_tasks.md", f"{review}.agent_completion.json"],
            "hard_constraints": ["Review the exact candidate path; pass_with_notes, warnings, or revision actions block promotion."],
            "style_constraints": ["Handle deterministic Style Lint evidence and anti-evasion risks explicitly."],
            "validation_gates": ["scene_review.v1 JSON exists", "review cites exact candidate", "review conclusion is clean pass"],
            "next_allowed_states": ["agent-review-task", "promotion-manifest"],
        },
        "agent-review-task": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.scene-development.agent-review.complete.v1",
            "command": "",
            "source_paths": [scene_rel, f"{review}.agent_tasks.md", f"{candidate}.md"],
            "expected_outputs": [f"{review}.json", f"{review}.md", f"{review}.agent_completion.json"],
            "hard_constraints": ["Complete AgentReview sidecar only after writing JSON/Markdown review for the exact candidate."],
            "style_constraints": ["Medium+ Style Lint findings are blocking unless revised and re-reviewed."],
            "validation_gates": ["AgentReview completion marker exists"],
            "next_allowed_states": ["promotion-manifest"],
        },
        "promotion-manifest": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.promote.v1",
            "command": f"python -m literary_engineering_workbench promote-candidate <project> --scene {scene_rel}",
            "source_paths": [scene_rel, f"{candidate}.md", f"{review}.json"],
            "expected_outputs": [f"drafts/promotions/{scene_id}_promotion.json", f"drafts/promotions/{scene_id}_promotion.md", f"drafts/scenes/{scene_id}.md"],
            "hard_constraints": ["Do not use --allow-unreviewed or --allow-review-notes."],
            "style_constraints": [],
            "validation_gates": ["promotion manifest exists", "promoted draft exists"],
            "next_allowed_states": ["static-review"],
        },
        "promoted-draft": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.promote.v1",
            "command": f"python -m literary_engineering_workbench promote-candidate <project> --scene {scene_rel}",
            "source_paths": [scene_rel, f"{candidate}.md", f"{review}.json"],
            "expected_outputs": [f"drafts/scenes/{scene_id}.md"],
            "hard_constraints": ["Promoted draft must come from promote-candidate, not manual copy."],
            "style_constraints": [],
            "validation_gates": ["promoted draft exists"],
            "next_allowed_states": ["static-review"],
        },
        "static-review": {
            "task_type": "deterministic-review",
            "prompt_asset_id": "route.scene-development.static-review.v1",
            "command": f"python -m literary_engineering_workbench review-scene <project> drafts/scenes/{scene_id}.md",
            "source_paths": [scene_rel, f"drafts/scenes/{scene_id}.md"],
            "expected_outputs": [f"reviews/{scene_id}-review.md"],
            "hard_constraints": ["Static review must be clean before chapter/export readiness."],
            "style_constraints": ["Apply punctuation and Style Lint concerns surfaced by review."],
            "validation_gates": ["static review conclusion is pass"],
            "next_allowed_states": ["state-patch-json"],
        },
        "state-patch-json": {
            "task_type": "deterministic-cli-plus-platform-review",
            "prompt_asset_id": "route.scene-development.state-evolve.prepare.v1",
            "command": f"python -m literary_engineering_workbench state-evolve <project> --scene {scene_rel} --agent-tasks",
            "source_paths": [scene_rel, f"drafts/scenes/{scene_id}.md"],
            "expected_outputs": [f"{state_patch}.md", f"{state_patch}.json", f"{state_patch}.agent_tasks.md"],
            "hard_constraints": ["State patch is candidate material until reviewed and approved."],
            "style_constraints": [],
            "validation_gates": ["state patch JSON exists", "state-evolve sidecar exists"],
            "next_allowed_states": ["state-agent-task"],
        },
        "state-agent-task": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.scene-development.state-evolve.execute.v1",
            "command": "",
            "source_paths": [scene_rel, f"{state_patch}.md", f"{state_patch}.json", f"{state_patch}.agent_tasks.md"],
            "expected_outputs": [f"{state_patch}.agent_completion.json"],
            "hard_constraints": ["Review state patch consequences and complete the marker; do not apply state without approval."],
            "style_constraints": [],
            "validation_gates": ["state-evolve sidecar completion marker exists"],
            "next_allowed_states": ["ready"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.scene-development.repair.v1",
        "command": next_action,
        "source_paths": common_sources,
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing formal gate."],
        "style_constraints": [],
        "validation_gates": ["route-specific gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def _longform_blueprint_for_state(root: Path, current_state: str, next_action: str) -> dict[str, object]:
    project_text = _read_text(root / "project.yaml")
    target_words = _project_int(project_text, "target_length") or _project_int(project_text, "target_words") or 100000
    volumes = _project_int(project_text, "volumes")
    genre = _project_scalar(project_text, "genre")
    command = f"python -m literary_engineering_workbench word-budget <project> --target-words {target_words}"
    if volumes:
        command += f" --volumes {volumes}"
    if genre:
        command += f" --genre {genre}"
    common_sources = ["project.yaml", "plot/outline.md", "scenes/"]
    table: dict[str, dict[str, object]] = {
        "word-budget-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.longform-planning.word-budget.prepare.v1",
            "command": command,
            "source_paths": common_sources,
            "expected_outputs": [
                "plot/word_budget/word_budget.md",
                "plot/word_budget/word_budget.json",
                "plot/word_budget/word_budget.agent_tasks.md",
                "plot/word_budget/scene_inventory_expansion.agent_tasks.md",
            ],
            "hard_constraints": [
                "Run word-budget / longform-budget before bulk outline or scene generation.",
                "Inspect both emitted platform-agent sidecars; this task is only the deterministic budget scaffold.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["word_budget.json exists", "word budget schema is valid", "budget and scene inventory sidecars exist"],
            "next_allowed_states": ["budget-agent-task"],
        },
        "budget-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.longform-planning.budget-expansion.execute.v1",
            "command": "",
            "source_paths": [
                "project.yaml",
                "plot/outline.md",
                "plot/word_budget/word_budget.md",
                "plot/word_budget/word_budget.json",
                "plot/word_budget/word_budget.agent_tasks.md",
            ],
            "expected_outputs": [
                "plot/candidates/outlines/word_budget_expansion.md",
                "reviews/word_budget/word_budget_review.md",
                "plot/word_budget/word_budget.agent_completion.json",
            ],
            "hard_constraints": [
                "Read word_budget.agent_tasks.md and write the budgeted outline candidate plus review.",
                "Judge whether the narrative inventory can support target length; do not solve shortfall by padding scenes.",
                "Keep expanded outline as candidate material until review and user approval.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["budget sidecar completion marker exists", "budgeted outline candidate exists", "word-budget review conclusion is pass"],
            "next_allowed_states": ["budget-review", "scene-inventory-agent-task"],
        },
        "budget-review": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.longform-planning.budget-review.v1",
            "command": "",
            "source_paths": [
                "plot/word_budget/word_budget.json",
                "plot/candidates/outlines/word_budget_expansion.md",
                "reviews/word_budget/word_budget_review.md",
            ],
            "expected_outputs": ["reviews/word_budget/word_budget_review.md"],
            "hard_constraints": ["The review conclusion must be pass before scene inventory planning is treated as formal."],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["word-budget review conclusion is pass"],
            "next_allowed_states": ["scene-inventory-agent-task"],
        },
        "scene-inventory-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.longform-planning.scene-inventory.execute.v1",
            "command": "",
            "source_paths": [
                "plot/word_budget/word_budget.json",
                "plot/word_budget/scene_inventory_expansion.agent_tasks.md",
                "plot/candidates/outlines/word_budget_expansion.md",
            ],
            "expected_outputs": [
                "plot/candidates/scenes/word_budget_scene_inventory.md",
                "reviews/word_budget/scene_inventory_review.md",
                "plot/word_budget/scene_inventory_expansion.agent_completion.json",
            ],
            "hard_constraints": [
                "Read scene_inventory_expansion.agent_tasks.md and create budgeted scene inventory candidates.",
                "Each added scene candidate needs target words, function, participants, conflict, information release, consequence, and setup/payoff role.",
                "Scene inventory remains candidate material until review and user approval.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["scene inventory sidecar completion marker exists", "scene inventory candidate exists", "scene inventory review conclusion is pass"],
            "next_allowed_states": ["scene-inventory-review"],
        },
        "scene-inventory-review": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.longform-planning.scene-inventory-review.v1",
            "command": "",
            "source_paths": [
                "plot/word_budget/word_budget.json",
                "plot/candidates/scenes/word_budget_scene_inventory.md",
                "reviews/word_budget/scene_inventory_review.md",
            ],
            "expected_outputs": ["reviews/word_budget/scene_inventory_review.md"],
            "hard_constraints": ["The scene inventory review conclusion must be pass before longform-planning is ready."],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["scene inventory review conclusion is pass"],
            "next_allowed_states": ["ready"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.longform-planning.repair.v1",
        "command": next_action,
        "source_paths": common_sources,
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing longform-planning gate."],
        "style_constraints": [],
        "word_count_target": target_words,
        "validation_gates": ["longform-planning gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def _source_ingest_blueprint_for_state(root: Path, work_id: str, import_dir: str, current_state: str, next_action: str) -> dict[str, object]:
    manifest_path = root / import_dir / "source_manifest.json"
    manifest = _read_json(manifest_path)
    candidate_outputs = _source_candidate_outputs_from_manifest(manifest, work_id)
    task_path = f"{import_dir}/extract_project_files.agent_tasks.md"
    completion = f"{import_dir}/extract_project_files.agent_completion.json"
    report = f"{import_dir}/source_ingest.md"
    chunks = [str(item.get("path") or "") for item in manifest.get("chunks", []) if isinstance(item, dict)]
    candidate_values = list(candidate_outputs.values())
    review = candidate_outputs.get("review", f"reviews/source_ingest/{work_id}_extraction_review.md")
    table: dict[str, dict[str, object]] = {
        "source-manifest": {
            "task_type": "deterministic-cli-or-repair",
            "prompt_asset_id": "route.source-ingest.import.v1",
            "command": "python -m literary_engineering_workbench source-ingest <project> --source <source> --title <title> --work-id <work-id>",
            "source_paths": ["project.yaml"],
            "expected_outputs": [f"{import_dir}/source_manifest.json", report, task_path],
            "hard_constraints": [
                "Run source-ingest with explicit source/text/title/work-id when starting a new import.",
                "If repairing an invalid manifest, preserve source evidence and candidate output paths.",
            ],
            "style_constraints": [],
            "validation_gates": ["source manifest exists", "source ingest report exists", "extraction sidecar exists", "source_manifest schema is valid"],
            "next_allowed_states": ["extraction-agent-task"],
        },
        "extraction-agent-task": {
            "task_type": "platform-agent-extraction",
            "prompt_asset_id": "route.source-ingest.extract-project-files.v1",
            "command": "",
            "source_paths": [f"{import_dir}/source_manifest.json", report, task_path, *chunks],
            "expected_outputs": [*candidate_values, completion],
            "hard_constraints": [
                "Read extract_project_files.agent_tasks.md and all source chunks before writing extracted candidates.",
                "Every extracted claim must include evidence_refs, confidence, unknowns, and contradiction notes when relevant.",
                "Write only candidate assets and source-ingest review; do not overwrite confirmed project files.",
            ],
            "style_constraints": [
                "For style notes from non-public-domain or unauthorized sources, abstract high-level craft features only.",
            ],
            "validation_gates": ["extraction sidecar completion marker exists", "all candidate outputs exist"],
            "next_allowed_states": ["extraction-review"],
        },
        "extraction-review": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.source-ingest.extraction-review.v1",
            "command": "",
            "source_paths": [f"{import_dir}/source_manifest.json", *[item for item in candidate_values if item != review], review],
            "expected_outputs": [review],
            "hard_constraints": [
                "The extraction review must be a clean pass before source-derived candidates are treated as route-ready.",
                "pass_with_notes, missing evidence, copied long passages, or direct canon writeback are blocking.",
            ],
            "style_constraints": [],
            "validation_gates": ["source-ingest extraction review conclusion is pass"],
            "next_allowed_states": ["ready"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.source-ingest.repair.v1",
        "command": next_action,
        "source_paths": [f"{import_dir}/source_manifest.json", report],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing source-ingest gate."],
        "style_constraints": [],
        "validation_gates": ["source-ingest gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def _style_engineering_blueprint_for_state(root: Path, profile_id: str, profile_dir: str, current_state: str, next_action: str) -> dict[str, object]:
    profile = f"{profile_dir}/style-profile.md"
    metrics = f"{profile_dir}/style_metrics.json"
    corpus_manifest = f"{profile_dir}/corpus_manifest.yaml"
    task = f"{profile_dir}/style_prompt.agent_tasks.md"
    prompt = f"{profile_dir}/style_prompt.md"
    agent_json = f"{profile_dir}/style_prompt.agent.json"
    completion = f"{profile_dir}/style_prompt.agent_completion.json"
    eval_dir = f"{profile_dir}/evaluation_results"
    table: dict[str, dict[str, object]] = {
        "style-profile": {
            "task_type": "deterministic-cli-or-repair",
            "prompt_asset_id": "route.style-engineering.profile.v1",
            "command": "python -m literary_engineering_workbench style-profile <corpus> --out-dir <profile-dir> --name <name>",
            "source_paths": [profile_dir],
            "expected_outputs": [profile, metrics],
            "hard_constraints": ["Compile or repair style-profile.md and style_metrics.json before prompt generation."],
            "style_constraints": [],
            "validation_gates": ["style profile exists", "style metrics exists"],
            "next_allowed_states": ["style-prompt-task-file"],
        },
        "style-prompt-task-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.style-engineering.prompt.prepare.v1",
            "command": f"python -m literary_engineering_workbench style-prompt <project>/{profile_dir}",
            "source_paths": [profile, metrics, corpus_manifest],
            "expected_outputs": [task],
            "hard_constraints": [
                "Run style-prompt to create a platform-agent style prompt task sidecar.",
                "The command prepares the task; the platform agent still writes style_prompt.md and style_prompt.agent.json.",
            ],
            "style_constraints": [],
            "validation_gates": ["style_prompt.agent_tasks.md exists"],
            "next_allowed_states": ["style-prompt-agent-task"],
        },
        "style-prompt-agent-task": {
            "task_type": "platform-agent-style-prompt",
            "prompt_asset_id": "route.style-engineering.prompt.execute.v1",
            "command": "",
            "source_paths": [profile, metrics, corpus_manifest, task],
            "expected_outputs": [prompt, agent_json, completion],
            "hard_constraints": [
                "Read style_prompt.agent_tasks.md and write a detailed executable LLM-facing style prompt.",
                "style_prompt.md must be 500-2500 non-whitespace detail characters.",
                "style_prompt.md must include all required blocks: identity/boundary, mechanism, narrative distance, rhythm, punctuation, imagery, psychology/behavior, dialogue, AI-trace controls, forbidden tendencies, and self-check.",
            ],
            "style_constraints": [
                "Do not authorize mechanical contrast frames or dash variants as style.",
                "Public-domain or authorized corpora may support closer imitation; otherwise extract high-level craft only.",
            ],
            "validation_gates": ["style prompt sidecar completion marker exists", "style_prompt.md exists", "style_prompt.agent.json exists", "style prompt quality passes"],
            "next_allowed_states": ["style-prompt-quality", "style-eval-readiness"],
        },
        "style-prompt-quality": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.style-engineering.prompt-quality.v1",
            "command": "",
            "source_paths": [profile, metrics, prompt, agent_json],
            "expected_outputs": [prompt, agent_json],
            "hard_constraints": [
                "Revise style_prompt.md until style_prompt_quality_report passes length and required-block checks.",
                "A vague prompt that only says the style is beautiful, restrained, literary, or advanced is not mountable.",
            ],
            "style_constraints": [],
            "validation_gates": ["style prompt quality passes"],
            "next_allowed_states": ["style-eval-readiness"],
        },
        "style-eval-readiness": {
            "task_type": "platform-agent-evaluation",
            "prompt_asset_id": "route.style-engineering.eval.v1",
            "command": f"python -m literary_engineering_workbench style-prompt-eval <project>/{profile_dir} --reference <reference> --input <input>",
            "source_paths": [profile, metrics, prompt, agent_json, eval_dir],
            "expected_outputs": [],
            "hard_constraints": [
                "Run or prepare at least one style-prompt evaluation and then run style-eval on the resulting candidate.",
                "At least one style_eval_*.json must have overall_score >= 45 and risk_level not in high_copy_risk/low_similarity.",
                "Do not build or mount a formal Style Skill until evaluation readiness passes.",
            ],
            "style_constraints": [],
            "validation_gates": ["accepted style_eval JSON exists"],
            "next_allowed_states": ["ready"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.style-engineering.repair.v1",
        "command": next_action,
        "source_paths": [profile_dir],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and repair the missing style-engineering gate."],
        "style_constraints": [],
        "validation_gates": ["style-engineering gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def _asset_blueprint_for_state(root: Path, candidate_id: str, asset_type: str, candidate: str, current_state: str, next_action: str) -> dict[str, object]:
    candidate_rel = candidate or ""
    candidate_path = _resolve_project_path(root, candidate_rel) if candidate_rel else root / "characters" / "candidates" / f"{candidate_id}.json"
    candidate_report = _rel(candidate_path.with_suffix(".md"), root)
    creation_task = _rel(candidate_path.with_suffix(".agent_tasks.md"), root)
    creation_completion = _rel(default_agent_completion_path(candidate_path.with_suffix(".agent_tasks.md")), root)
    review = f"reviews/assets/{candidate_id}_review.md"
    review_json = f"reviews/assets/{candidate_id}_review.json"
    review_task = f"reviews/assets/{candidate_id}_review.agent_tasks.md"
    review_completion = f"reviews/assets/{candidate_id}_review.agent_completion.json"
    promotion = f"workflow/asset_promotions/{candidate_id}_promotion.json"
    promotion_report = f"workflow/asset_promotions/{candidate_id}_promotion.md"
    group = _asset_promotion_group(asset_type)
    type_hint = asset_type or "<character|background-story|relationship|world|location|organization|outline|chapter-plan|scene-list>"
    table: dict[str, dict[str, object]] = {
        "asset-intake": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.character-world-assets.intake.v1",
            "command": "python -m literary_engineering_workbench asset-create <project> --type <type> --brief <user brief> [--target-id <id>] [--source <path>]",
            "source_paths": ["project.yaml", "canon", "characters", "plot", "style"],
            "expected_outputs": [],
            "hard_constraints": [
                "Choose the smallest asset type from the user's direction, then run asset-create or agent-create-* to create a platform-agent sidecar.",
                "This task is complete only after the asset creation sidecar or candidate asset exists.",
                "The platform agent must not write directly to confirmed canon, character files, outline, scenes, drafts, exports, or releases.",
            ],
            "style_constraints": [],
            "validation_gates": ["at least one asset creation sidecar or candidate exists"],
            "next_allowed_states": ["asset-creation-agent-task"],
        },
        "asset-creation-agent-task": {
            "task_type": "platform-agent-asset-creation",
            "prompt_asset_id": "route.character-world-assets.create.v1",
            "command": "",
            "source_paths": ["project.yaml", "canon", "characters", "plot", "style", creation_task],
            "expected_outputs": [candidate_rel, candidate_report, creation_completion],
            "hard_constraints": [
                f"Read the asset creation sidecar and write a {type_hint} candidate asset, not a confirmed project file.",
                "Candidate JSON must satisfy its schema and include candidate_id, risks, source_paths, and promotion_notes.",
                "Character and background-story assets must preserve background_story as hidden behavioral causality, not exposition.",
            ],
            "style_constraints": ["Mounted style may inform names/tone but cannot override canon, world rules, or user constraints."],
            "validation_gates": ["asset creation sidecar completed", "candidate JSON exists", "candidate report exists", "candidate schema validates"],
            "next_allowed_states": ["asset-review-task-file"],
        },
        "asset-review-task-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.character-world-assets.review.prepare.v1",
            "command": f"python -m literary_engineering_workbench review-candidate-asset <project> {candidate_rel}",
            "source_paths": [candidate_rel, candidate_report, "canon", "characters", "plot", "style"],
            "expected_outputs": [review_task],
            "hard_constraints": [
                "Run review-candidate-asset to create a formal platform-agent asset review sidecar.",
                "The command prepares the review task; the platform agent still performs the semantic review.",
            ],
            "style_constraints": [],
            "validation_gates": ["asset review sidecar exists"],
            "next_allowed_states": ["asset-review-agent-task"],
        },
        "asset-review-agent-task": {
            "task_type": "platform-agent-asset-review",
            "prompt_asset_id": "route.character-world-assets.review.execute.v1",
            "command": "",
            "source_paths": [candidate_rel, candidate_report, review_task, "canon", "characters", "plot", "style"],
            "expected_outputs": [review, review_json, review_completion],
            "hard_constraints": [
                "Review candidate asset against schema, canon, character logic, originality, hidden background-story policy, and promotion risk.",
                "Write JSON with status pass|failed|revise_required plus blocking_issues, warnings, revision_actions, and promotion_risks.",
                "Do not use review as approval. A clean review only permits asking the user whether to approve promotion.",
            ],
            "style_constraints": [],
            "validation_gates": ["asset review sidecar completed", "review JSON exists", "review Markdown exists", "review status is pass"],
            "next_allowed_states": ["asset-review-pass", "asset-approval"],
        },
        "asset-review-pass": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.character-world-assets.review-fix.v1",
            "command": "",
            "source_paths": [candidate_rel, review, review_json],
            "expected_outputs": [candidate_rel, candidate_report, review, review_json],
            "hard_constraints": [
                "Resolve blocking asset review notes before asking for approval.",
                "Do not bury revise_required findings as harmless warnings.",
                "After revising the candidate, rerun or update the asset review and completion marker.",
            ],
            "style_constraints": [],
            "validation_gates": ["review status pass", "no blocking_issues", "no revision_actions"],
            "next_allowed_states": ["asset-approval"],
        },
        "asset-approval": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.character-world-assets.approval.v1",
            "command": f"Ask the user whether to approve candidate `{candidate_id}` for promotion; record approve decision with run_id `{candidate_id}` through the platform approval mechanism.",
            "source_paths": [candidate_rel, review, review_json, "workflow/approvals/index.jsonl"],
            "expected_outputs": ["workflow/approvals/index.jsonl"],
            "hard_constraints": [
                "The platform agent must not self-approve candidate promotion.",
                "If the user asks for revision or rejection, record that decision and do not promote.",
                "Approval must reference the candidate_id/run_id that promote-candidate-asset will use.",
            ],
            "style_constraints": [],
            "validation_gates": ["approve record exists for candidate_id"],
            "next_allowed_states": ["asset-promotion"],
        },
        "asset-promotion": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.character-world-assets.promote.v1",
            "command": f"python -m literary_engineering_workbench promote-candidate-asset <project> {candidate_rel} --group {group or '<group>'} --approval-run-id {candidate_id}",
            "source_paths": [candidate_rel, review, review_json, "workflow/approvals/index.jsonl"],
            "expected_outputs": [promotion, promotion_report],
            "hard_constraints": [
                "Promote only after clean review and matching approve record.",
                "Do not use --allow-unapproved in formal Skill-host work.",
                "After promotion, run canon-lint or the relevant downstream route before relying on the new project facts.",
            ],
            "style_constraints": [],
            "validation_gates": ["promotion manifest exists", "allow_unapproved is false", "promotion outputs exist"],
            "next_allowed_states": ["ready"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.character-world-assets.repair.v1",
        "command": next_action,
        "source_paths": [candidate_rel] if candidate_rel else ["project.yaml", "canon", "characters", "plot"],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and repair the missing character/world asset gate."],
        "style_constraints": [],
        "validation_gates": ["character/world asset gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def _render_task_markdown(task: dict[str, object], root: Path) -> str:
    task_id = str(task.get("task_id") or "")
    completion = default_agent_completion_path(_task_markdown_path(root, task_id))
    lines = [
        f"# CLI 中介平台 Agent 任务：{task_id}",
        "",
        "本文件由 `task-next` / `task-open` 生成，代表一个正式项目操作任务。",
        "用户可以继续与平台 Agent 自然对话；但本任务涉及的正式产物必须通过 CLI 提交和完成。",
        "",
        "## Task Metadata",
        "",
        f"- task_id: `{task_id}`",
        f"- route: `{task.get('route', '')}`",
        f"- scene_id: `{task.get('scene_id', '')}`",
        f"- current_state: `{task.get('current_state', '')}`",
        f"- task_type: `{task.get('task_type', '')}`",
        f"- prompt_asset_id: `{task.get('prompt_asset_id', '')}`",
        f"- status: `{task.get('status', '')}`",
        f"- completion_marker: `{_rel(completion, root)}`",
        "",
        "## Required Reading",
        "",
    ]
    for item in task.get("required_reading") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Source Artifacts", ""])
    source_paths = list(task.get("source_paths") or [])
    if source_paths:
        for item in source_paths:
            lines.append(f"- `{item}`")
    else:
        lines.append("- 无。")
    lines.extend(["", "## Command", ""])
    command = str(task.get("command") or "").strip()
    if command:
        lines.extend(["```powershell", command, "```"])
    else:
        lines.append("- 本任务主要由平台 Agent 读取 source artifacts 后写出判断或创作产物。")
    lines.extend(["", "## Hard Constraints", ""])
    for item in task.get("hard_constraints") or []:
        lines.append(f"- {item}")
    style_constraints = list(task.get("style_constraints") or [])
    if style_constraints:
        lines.extend(["", "## Style Constraints", ""])
        for item in style_constraints:
            lines.append(f"- {item}")
    lines.extend(["", "## Expected Outputs", ""])
    expected_outputs = list(task.get("expected_outputs") or [])
    if expected_outputs:
        for item in expected_outputs:
            lines.append(f"- 创建或覆盖 `{item}`")
    else:
        lines.append("- 本任务没有固定文件输出；完成前仍需通过 `task-submit` 记录证据。")
    lines.extend(["", "## Validation Gates", ""])
    for item in task.get("validation_gates") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Forbidden Shortcuts", ""])
    for item in task.get("forbidden_shortcuts") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Agent Execution",
            "",
            "[AGENT_TASK: 读取本任务的 Required Reading 和 Source Artifacts。按 Command 或 Hard Constraints 完成产物。完成后先运行 task-submit 记录你写出的产物，再运行 task-complete。不得只手写文件后跳到下一步。]",
            "",
            "推荐提交命令：",
            "",
            "```powershell",
            str(task.get("submission_command") or ""),
            "```",
            "",
            "推荐完成命令：",
            "",
            "```powershell",
            str(task.get("completion_command") or ""),
            "```",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _workflow_payload(root: Path, route: str) -> dict[str, object]:
    result = build_workflow_state(root, route=route)
    return _read_json(result.json_path)


def _select_scene_state(root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    scenes = [item for item in payload.get("scenes", []) if isinstance(item, dict)]
    if scene:
        scene_path = _resolve_project_path(root, scene)
        scene_id = _scene_id(scene_path)
        scene_rel = _rel(scene_path, root)
        return next((item for item in scenes if item.get("scene_id") == scene_id or item.get("scene") == scene_rel), None)
    return next((item for item in scenes if item.get("status") != "ready"), None)


def _select_longform_state(root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    _ = root
    _ = scene
    state = payload.get("longform") if isinstance(payload.get("longform"), dict) else {}
    if not state or state.get("status") == "ready":
        return None
    return state


def _select_source_ingest_state(root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    _ = root
    items = [item for item in payload.get("source_ingests", []) if isinstance(item, dict)]
    if scene:
        target = str(scene).replace("\\", "/").strip("/")
        return next(
            (
                item
                for item in items
                if str(item.get("work_id") or "") == target
                or str(item.get("target_id") or "") == target
                or str(item.get("import_dir") or "").rstrip("/").endswith(target)
            ),
            None,
        )
    return next((item for item in items if item.get("status") != "ready"), None)


def _select_style_engineering_state(root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    _ = root
    items = [item for item in payload.get("styles", []) if isinstance(item, dict)]
    if scene:
        target = str(scene).replace("\\", "/").strip("/")
        return next(
            (
                item
                for item in items
                if str(item.get("profile_id") or "") == target
                or str(item.get("target_id") or "") == target
                or str(item.get("profile_dir") or "").rstrip("/").endswith(target)
            ),
            None,
        )
    return next((item for item in items if item.get("status") != "ready"), None)


def _select_asset_state(root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    _ = root
    items = [item for item in payload.get("assets", []) if isinstance(item, dict)]
    if scene:
        target = str(scene).replace("\\", "/").strip("/")
        return next(
            (
                item
                for item in items
                if str(item.get("candidate_id") or "") == target
                or str(item.get("target_id") or "") == target
                or str(item.get("candidate") or "").rstrip("/").endswith(target)
            ),
            None,
        )
    return next((item for item in items if item.get("status") != "ready"), None)


def _scene_id(scene_path: Path) -> str:
    text = scene_path.read_text(encoding="utf-8", errors="ignore") if scene_path.exists() else ""
    match = re.search(r"(?m)^\s*scene_id:\s*['\"]?([^'\"\n#]+)", text)
    if match:
        scene_id = match.group(1).strip().strip("\"'")
        if scene_id:
            return scene_id
    return scene_path.stem


def _block_task(root: Path, task_json: Path, task: dict[str, object], task_id: str, message: str) -> None:
    task["status"] = "blocked"
    task["validation"] = {"status": "fail", "message": message}
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _append_event(root, "task_blocked", task_id, {"message": message})


def _state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    """Run current-state-specific gates after expected outputs exist."""

    current_state = str(task.get("current_state") or "")
    scene_id = str(task.get("scene_id") or "")
    errors: list[str] = []
    notes: list[str] = []
    if not current_state:
        return errors, notes

    if current_state == "roleplay-simulation":
        errors.extend(_roleplay_gate_errors(root, scene_id))
    if current_state in {"branch-manifest", "branch-agent-task"}:
        errors.extend(_branch_manifest_gate_errors(root, scene_id))
    if current_state == "branch-selection":
        branch_errors, branch_notes = _branch_selection_gate(root, scene_id)
        errors.extend(branch_errors)
        notes.extend(branch_notes)
    if current_state in {"composition-json", "composition-agent-task"}:
        errors.extend(_composition_gate_errors(root, scene_id))
    if current_state == "scene-word-budget-contract":
        errors.extend(_word_budget_gate_errors(root, task))
    if current_state in {"candidate-generation-provenance", "generation-agent-task"}:
        candidate = _candidate_path_for_task(root, task)
        errors.extend(_candidate_generation_gate_errors(root, task, candidate))
        errors.extend(_candidate_body_gate_errors(root, task, candidate))
    if current_state in {"candidate-review", "agent-review-task"}:
        candidate = _candidate_path_for_task(root, task)
        errors.extend(_candidate_generation_gate_errors(root, task, candidate))
        errors.extend(_candidate_review_gate_errors(root, task, candidate))
    if current_state in {"promotion-manifest", "promoted-draft"}:
        errors.extend(_promotion_gate_errors(root, task))
    if current_state == "static-review":
        errors.extend(_static_review_gate_errors(root, scene_id))
    if current_state in {"state-patch-json", "state-agent-task"}:
        errors.extend(_state_patch_gate_errors(root, scene_id))
    return errors, notes


def _longform_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "word-budget-file":
        errors.extend(_word_budget_file_gate_errors(root))
    if current_state in {"budget-agent-task", "budget-review"}:
        errors.extend(_word_budget_file_gate_errors(root))
        errors.extend(_longform_sidecar_completion_errors(root / "plot" / "word_budget" / "word_budget.agent_tasks.md", root, "word-budget expansion"))
        errors.extend(
            _longform_required_artifact_errors(
                root,
                [root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"],
                "word-budget expansion",
            )
        )
        errors.extend(_longform_review_gate_errors(root / "reviews" / "word_budget" / "word_budget_review.md", root, "word-budget review"))
    if current_state in {"scene-inventory-agent-task", "scene-inventory-review"}:
        errors.extend(_word_budget_file_gate_errors(root))
        errors.extend(_longform_sidecar_completion_errors(root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md", root, "scene-inventory expansion"))
        errors.extend(
            _longform_required_artifact_errors(
                root,
                [root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"],
                "scene-inventory expansion",
            )
        )
        errors.extend(_longform_review_gate_errors(root / "reviews" / "word_budget" / "scene_inventory_review.md", root, "scene-inventory review"))
    if current_state in {"budget-agent-task", "budget-review"} and not errors:
        notes.append("word-budget expansion reviewed")
    if current_state in {"scene-inventory-agent-task", "scene-inventory-review"} and not errors:
        notes.append("scene inventory reviewed")
    return errors, notes


def _source_ingest_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    work_id = str(task.get("work_id") or task.get("target_id") or task.get("scene_id") or "")
    import_dir = _source_import_dir_for_task(root, task)
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "source-manifest":
        errors.extend(_source_manifest_gate_errors(root, import_dir))
    if current_state == "extraction-agent-task":
        errors.extend(_source_manifest_gate_errors(root, import_dir))
        errors.extend(_source_extraction_gate_errors(root, import_dir, work_id, require_review_pass=False))
    if current_state == "extraction-review":
        errors.extend(_source_manifest_gate_errors(root, import_dir))
        errors.extend(_source_extraction_gate_errors(root, import_dir, work_id, require_review_pass=True))
    if current_state == "extraction-agent-task" and not errors:
        notes.append("source extraction candidates and sidecar completion marker exist")
    if current_state == "extraction-review" and not errors:
        notes.append("source extraction review passed")
    return errors, notes


def _style_engineering_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    profile_dir = _style_profile_dir_for_task(root, task)
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "style-profile":
        errors.extend(_style_profile_gate_errors(root, profile_dir))
    if current_state == "style-prompt-task-file":
        errors.extend(_style_profile_gate_errors(root, profile_dir))
        if not (profile_dir / "style_prompt.agent_tasks.md").exists():
            errors.append(f"style prompt task sidecar missing: {_rel(profile_dir / 'style_prompt.agent_tasks.md', root)}")
    if current_state in {"style-prompt-agent-task", "style-prompt-quality"}:
        errors.extend(_style_profile_gate_errors(root, profile_dir))
        errors.extend(_style_prompt_gate_errors(root, profile_dir))
    if current_state == "style-eval-readiness":
        errors.extend(_style_profile_gate_errors(root, profile_dir))
        errors.extend(_style_prompt_gate_errors(root, profile_dir))
        errors.extend(_style_eval_gate_errors(root, profile_dir))
    if current_state in {"style-prompt-agent-task", "style-prompt-quality"} and not errors:
        notes.append("style prompt task completed and quality gate passed")
    if current_state == "style-eval-readiness" and not errors:
        notes.append("style evaluation readiness passed")
    return errors, notes


def _asset_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    candidate = _asset_candidate_path_for_task(root, task)
    candidate_id = str(task.get("candidate_id") or task.get("target_id") or candidate.stem)
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "asset-intake":
        errors.extend(_asset_intake_gate_errors(root))
    if current_state == "asset-creation-agent-task":
        errors.extend(_asset_creation_gate_errors(root, candidate))
    if current_state == "asset-review-task-file":
        errors.extend(_asset_creation_gate_errors(root, candidate))
        review_task = root / "reviews" / "assets" / f"{candidate_id}_review.agent_tasks.md"
        if not review_task.exists():
            errors.append(f"asset review sidecar missing: {_rel(review_task, root)}")
    if current_state in {"asset-review-agent-task", "asset-review-pass"}:
        errors.extend(_asset_creation_gate_errors(root, candidate))
        errors.extend(_asset_review_gate_errors(root, candidate_id, require_pass=True))
    if current_state == "asset-approval":
        errors.extend(_asset_creation_gate_errors(root, candidate))
        errors.extend(_asset_review_gate_errors(root, candidate_id, require_pass=True))
        errors.extend(_asset_approval_gate_errors(root, candidate_id))
    if current_state == "asset-promotion":
        errors.extend(_asset_creation_gate_errors(root, candidate))
        errors.extend(_asset_review_gate_errors(root, candidate_id, require_pass=True))
        errors.extend(_asset_approval_gate_errors(root, candidate_id))
        errors.extend(_asset_promotion_gate_errors(root, candidate_id))
    if current_state in {"asset-creation-agent-task", "asset-review-task-file"} and not errors:
        notes.append("asset candidate creation gate passed")
    if current_state in {"asset-review-agent-task", "asset-review-pass"} and not errors:
        notes.append("asset review gate passed")
    if current_state == "asset-promotion" and not errors:
        notes.append("asset promotion gate passed")
    return errors, notes


def _word_budget_file_gate_errors(root: Path) -> list[str]:
    json_path = root / "plot" / "word_budget" / "word_budget.json"
    markdown_path = root / "plot" / "word_budget" / "word_budget.md"
    budget_task = root / "plot" / "word_budget" / "word_budget.agent_tasks.md"
    scene_task = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    errors: list[str] = []
    for path in (markdown_path, json_path, budget_task, scene_task):
        if not path.exists():
            errors.append(f"missing longform budget artifact: {_rel(path, root)}")
    payload, error = _read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/word-budget/v1":
        errors.append("word_budget.json has wrong or missing schema")
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    if _to_int(target.get("target_words") or totals.get("target_words")) <= 0:
        errors.append("word_budget.json target_words must be positive")
    if not isinstance(payload.get("chapter_budgets"), list) or not payload.get("chapter_budgets"):
        errors.append("word_budget.json must contain chapter_budgets")
    if not isinstance(payload.get("scene_inventory_binding"), dict):
        errors.append("word_budget.json must contain scene_inventory_binding")
    return errors


def _longform_sidecar_completion_errors(task_path: Path, root: Path, label: str) -> list[str]:
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is True:
        return []
    return [f"{label} sidecar is incomplete: {state.get('message')}"]


def _longform_required_artifact_errors(root: Path, paths: list[Path], label: str) -> list[str]:
    missing = [_rel(path, root) for path in paths if not path.exists()]
    if not missing:
        return []
    return [f"{label} required artifact missing: {', '.join(missing)}"]


def _longform_review_gate_errors(path: Path, root: Path, label: str) -> list[str]:
    conclusion = _static_review_conclusion(path)
    if conclusion == "pass":
        return []
    return [f"{label} conclusion must be pass; got {conclusion or 'missing'} at {_rel(path, root)}"]


def _source_manifest_gate_errors(root: Path, import_dir: Path) -> list[str]:
    manifest_path = import_dir / "source_manifest.json"
    report_path = import_dir / "source_ingest.md"
    task_path = import_dir / "extract_project_files.agent_tasks.md"
    errors: list[str] = []
    for path in (manifest_path, report_path, task_path):
        if not path.exists():
            errors.append(f"missing source-ingest artifact: {_rel(path, root)}")
    payload, error = _read_optional_json(manifest_path)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/source-ingest/v1":
        errors.append("source_manifest.json has wrong or missing schema")
    if not payload.get("work_id"):
        errors.append("source_manifest.json must contain work_id")
    if not isinstance(payload.get("chunks"), list) or not payload.get("chunks"):
        errors.append("source_manifest.json must contain source chunks")
    if not isinstance(payload.get("candidate_outputs"), dict) or not payload.get("candidate_outputs"):
        errors.append("source_manifest.json must contain candidate_outputs")
    return errors


def _source_extraction_gate_errors(root: Path, import_dir: Path, work_id: str, *, require_review_pass: bool) -> list[str]:
    manifest = _read_json(import_dir / "source_manifest.json")
    outputs = _source_candidate_outputs_from_manifest(manifest, work_id or import_dir.name)
    task_path = import_dir / "extract_project_files.agent_tasks.md"
    state = agent_task_completion_status(task_path, root=root)
    errors: list[str] = []
    if state.get("complete") is not True:
        errors.append(f"source extraction sidecar is incomplete: {state.get('message')}")
    for key, rel in outputs.items():
        path = root / rel
        if not path.exists():
            errors.append(f"source extraction output missing: {key} -> {rel}")
    if require_review_pass:
        review = root / outputs.get("review", f"reviews/source_ingest/{work_id}_extraction_review.md")
        conclusion = _static_review_conclusion(review)
        if conclusion != "pass":
            errors.append(f"source-ingest extraction review conclusion must be pass; got {conclusion or 'missing'} at {_rel(review, root)}")
    return errors


def _source_import_dir_for_task(root: Path, task: dict[str, object]) -> Path:
    work_id = str(task.get("work_id") or task.get("target_id") or task.get("scene_id") or "")
    source_paths = [str(item) for item in task.get("source_paths") or []]
    for item in source_paths:
        normalized = item.replace("\\", "/")
        if "/source_manifest.json" in f"/{normalized}":
            return _resolve_project_path(root, normalized).parent
    return root / "sources" / "imports" / (work_id or "source")


def _source_candidate_outputs_from_manifest(manifest: dict[str, object], work_id: str) -> dict[str, str]:
    outputs = manifest.get("candidate_outputs") if isinstance(manifest.get("candidate_outputs"), dict) else {}
    if outputs:
        return {str(key): str(value) for key, value in outputs.items() if str(value).strip()}
    return {
        "project_brief": f"sources/imports/{work_id}/extracted/project_brief.md",
        "characters": f"characters/candidates/extracted/{work_id}_characters.md",
        "world": f"canon/candidates/extracted/{work_id}_world.md",
        "outline": f"plot/candidates/extracted/{work_id}_outline.md",
        "timeline": f"plot/candidates/extracted/{work_id}_timeline.md",
        "foreshadowing": f"plot/candidates/extracted/{work_id}_foreshadowing.md",
        "style_notes": f"style/candidates/{work_id}_style_generation_notes.md",
        "review": f"reviews/source_ingest/{work_id}_extraction_review.md",
    }


def _style_profile_gate_errors(root: Path, profile_dir: Path) -> list[str]:
    errors: list[str] = []
    for path in (profile_dir / "style-profile.md", profile_dir / "style_metrics.json"):
        if not path.exists():
            errors.append(f"style profile artifact missing: {_rel(path, root)}")
    return errors


def _style_prompt_gate_errors(root: Path, profile_dir: Path) -> list[str]:
    task_path = profile_dir / "style_prompt.agent_tasks.md"
    prompt_path = profile_dir / "style_prompt.md"
    agent_json = profile_dir / "style_prompt.agent.json"
    errors: list[str] = []
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"style prompt sidecar is incomplete: {state.get('message')}")
    for path in (prompt_path, agent_json):
        if not path.exists():
            errors.append(f"style prompt artifact missing: {_rel(path, root)}")
    if prompt_path.exists():
        report = style_prompt_quality_report(_read_text(prompt_path))
        if not report.get("length_ok"):
            errors.append(
                "style_prompt.md detail length must be 500-2500 non-whitespace characters; "
                f"got {report.get('detail_chars')}"
            )
        if not report.get("structure_ok"):
            missing = ", ".join(str(item) for item in report.get("missing_blocks", []))
            errors.append(f"style_prompt.md missing required prompt blocks: {missing}")
    return errors


def _style_eval_gate_errors(root: Path, profile_dir: Path) -> list[str]:
    accepted = _accepted_style_eval_jsons(profile_dir)
    if accepted:
        return []
    return [f"accepted style_eval_*.json missing under {_rel(profile_dir / 'evaluation_results', root)}"]


def _accepted_style_eval_jsons(profile_dir: Path) -> list[Path]:
    accepted: list[Path] = []
    for path in sorted((profile_dir / "evaluation_results").glob("*/style_eval_*.json")):
        payload, error = _read_optional_json(path)
        if error:
            continue
        risk = str(payload.get("risk_level") or "")
        try:
            score = float(payload.get("overall_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        if risk in {"high_copy_risk", "low_similarity"} or score < 45:
            continue
        accepted.append(path)
    return accepted


def _style_profile_dir_for_task(root: Path, task: dict[str, object]) -> Path:
    profile_dir = str(task.get("profile_dir") or "").strip()
    if profile_dir:
        return _resolve_project_path(root, profile_dir)
    source_paths = [str(item) for item in task.get("source_paths") or []]
    for item in source_paths:
        normalized = item.replace("\\", "/")
        if normalized.endswith("/style-profile.md"):
            return _resolve_project_path(root, normalized).parent
    profile_id = str(task.get("profile_id") or task.get("target_id") or task.get("scene_id") or "style-profile")
    return root / "style" / profile_id


def _asset_intake_gate_errors(root: Path) -> list[str]:
    for folder in ASSET_CANDIDATE_DIRS.values():
        base = root / folder
        if not base.exists():
            continue
        if any(base.glob("*.agent_tasks.md")) or any(base.glob("*.json")):
            return []
    return ["no candidate asset or asset creation sidecar exists; run asset-create / agent-create-* first"]


def _asset_creation_gate_errors(root: Path, candidate: Path) -> list[str]:
    errors: list[str] = []
    task_path = candidate.with_suffix(".agent_tasks.md")
    report_path = candidate.with_suffix(".md")
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"asset creation sidecar is incomplete: {state.get('message')}")
    payload, error = _read_optional_json(candidate)
    if error:
        errors.append(error)
    else:
        asset_type = _asset_type_from_payload_or_path(root, candidate, payload)
        schema_name = ASSET_SCHEMA_NAMES.get(asset_type, "")
        if not schema_name:
            errors.append(f"unknown asset type for candidate: {asset_type or _rel(candidate, root)}")
        else:
            schema_errors, _warnings = validate_payload(payload, schema_name)
            errors.extend(f"asset candidate schema error at {item.get('path')}: {item.get('message')}" for item in schema_errors)
        candidate_id = str(payload.get("candidate_id") or "").strip()
        if not candidate_id:
            errors.append("asset candidate JSON must contain candidate_id")
        if not isinstance(payload.get("risks"), list):
            errors.append("asset candidate JSON must contain risks list")
        if not isinstance(payload.get("source_paths"), list):
            errors.append("asset candidate JSON must contain source_paths list")
        if not isinstance(payload.get("promotion_notes"), str) or not str(payload.get("promotion_notes") or "").strip():
            errors.append("asset candidate JSON must contain promotion_notes")
    if not report_path.exists():
        errors.append(f"asset candidate report missing: {_rel(report_path, root)}")
    return errors


def _asset_review_gate_errors(root: Path, candidate_id: str, *, require_pass: bool) -> list[str]:
    review = root / "reviews" / "assets" / f"{candidate_id}_review.md"
    review_json = review.with_suffix(".json")
    review_task = review_json.with_suffix(".agent_tasks.md")
    errors: list[str] = []
    state = agent_task_completion_status(review_task, root=root)
    if state.get("complete") is not True:
        errors.append(f"asset review sidecar is incomplete: {state.get('message')}")
    payload, error = _read_optional_json(review_json)
    if error:
        errors.append(error)
    else:
        status = str(payload.get("status") or "").strip().lower()
        if require_pass and status != "pass":
            errors.append(f"asset review status must be pass; got {status or 'missing'} at {_rel(review_json, root)}")
        blocking = payload.get("blocking_issues")
        if isinstance(blocking, list) and blocking:
            errors.append(f"asset review has blocking_issues: {len(blocking)}")
        revisions = payload.get("revision_actions")
        if isinstance(revisions, list) and revisions:
            errors.append(f"asset review has unresolved revision_actions: {len(revisions)}")
        candidate_ref = str(payload.get("candidate") or "").strip()
        if candidate_ref and Path(candidate_ref).stem != candidate_id:
            errors.append(f"asset review candidate mismatch: {candidate_ref} does not match {candidate_id}")
    if not review.exists():
        errors.append(f"asset review report missing: {_rel(review, root)}")
    return errors


def _asset_approval_gate_errors(root: Path, candidate_id: str) -> list[str]:
    approval = _approval_record_for_run(root, candidate_id)
    if str(approval.get("decision") or "") == "approve":
        return []
    return [f"asset promotion requires approve record for run_id {candidate_id}; got {approval.get('decision') or 'missing'}"]


def _asset_promotion_gate_errors(root: Path, candidate_id: str) -> list[str]:
    manifest = root / "workflow" / "asset_promotions" / f"{candidate_id}_promotion.json"
    report = manifest.with_suffix(".md")
    payload, error = _read_optional_json(manifest)
    errors: list[str] = []
    if error:
        errors.append(error)
        return errors
    if payload.get("status") != "promoted":
        errors.append(f"asset promotion status must be promoted; got {payload.get('status') or 'missing'}")
    if payload.get("allow_unapproved"):
        errors.append("asset promotion used allow_unapproved; formal Skill-host route must not use approval bypass")
    if str(payload.get("candidate_id") or "") != candidate_id:
        errors.append(f"asset promotion candidate_id mismatch: {payload.get('candidate_id') or 'missing'}")
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), list) else []
    if not outputs:
        errors.append("asset promotion manifest must list outputs")
    for item in outputs:
        path = _resolve_project_path(root, str(item))
        if not path.exists():
            errors.append(f"asset promotion output missing: {_rel(path, root)}")
    if not report.exists():
        errors.append(f"asset promotion report missing: {_rel(report, root)}")
    return errors


def _asset_candidate_path_for_task(root: Path, task: dict[str, object]) -> Path:
    candidate = str(task.get("candidate") or "").strip()
    if candidate:
        return _resolve_project_path(root, candidate)
    candidates = [
        *[str(item) for item in task.get("submitted_artifacts") or []],
        *[str(item) for item in task.get("expected_outputs") or []],
        *[str(item) for item in task.get("source_paths") or []],
    ]
    for item in candidates:
        normalized = item.replace("\\", "/")
        if not normalized.endswith(".json"):
            continue
        if ".agent_" in normalized or "/reviews/" in f"/{normalized}" or "/workflow/" in f"/{normalized}":
            continue
        if _is_asset_candidate_rel(normalized):
            return _resolve_project_path(root, item)
    candidate_id = str(task.get("candidate_id") or task.get("target_id") or "asset-intake")
    return root / "characters" / "candidates" / f"{candidate_id}.json"


def _is_asset_candidate_rel(value: str) -> bool:
    normalized = value.replace("\\", "/").lstrip("/")
    return any(normalized.startswith(folder.as_posix() + "/") for folder in ASSET_CANDIDATE_DIRS.values())


def _asset_type_from_payload_or_path(root: Path, candidate: Path, payload: dict[str, object]) -> str:
    asset_type = str(payload.get("asset_type") or "").strip().lower().replace("_", "-")
    if asset_type:
        return asset_type
    rel = _rel(candidate, root)
    for item_type, folder in ASSET_CANDIDATE_DIRS.items():
        if rel.startswith(folder.as_posix() + "/"):
            return item_type
    return ""


def _asset_promotion_group(asset_type: str) -> str:
    normalized = asset_type.strip().lower().replace("_", "-")
    for group, members in PROMOTABLE_GROUPS.items():
        if normalized in members:
            return group
    return ""


def _approval_record_for_run(root: Path, run_id: str) -> dict[str, object]:
    index = root / "workflow" / "approvals" / "index.jsonl"
    if not index.exists():
        return {}
    latest: dict[str, object] = {}
    for line in index.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("run_id") == run_id:
            latest = payload
    return latest


def _roleplay_gate_errors(root: Path, scene_id: str) -> list[str]:
    path = root / "branches" / scene_id / "roleplay_simulation.md"
    text = _read_text(path)
    if not text:
        return [f"roleplay simulation is empty or unreadable: {_rel(path, root)}"]
    if "正式 CLI 来源" not in text or "simulate-scene" not in text:
        return [
            "roleplay simulation lacks CLI provenance text from simulate-scene; "
            "manual RP files are exploratory/debug-only for the formal route"
        ]
    return []


def _branch_manifest_gate_errors(root: Path, scene_id: str) -> list[str]:
    path = root / "branches" / scene_id / "branch_manifest.json"
    payload, error = _read_optional_json(path)
    if error:
        return [error]
    if not payload:
        return [f"branch manifest is missing or empty: {_rel(path, root)}"]
    provenance = payload.get("formal_cli_provenance") if isinstance(payload.get("formal_cli_provenance"), dict) else {}
    created_by = str(provenance.get("created_by") or "")
    if created_by != "branch-simulate":
        return [
            "branch manifest lacks formal_cli_provenance.created_by=branch-simulate; "
            "run branch-simulate --agent instead of hand-writing the manifest"
        ]
    if provenance.get("agent_tasks_requested") is not True:
        return ["branch manifest was not created with --agent; branch sidecar is required for formal route"]
    return []


def _branch_selection_gate(root: Path, scene_id: str) -> tuple[list[str], list[str]]:
    selection = root / "branches" / scene_id / "branch_selection.md"
    branch_state = branch_selection_status(selection)
    if branch_state.get("status") != "selected":
        return [str(branch_state.get("message") or "branch selection is not selected")], []
    return [], [f"branch selection: {branch_state.get('selected_branch')}"]


def _composition_gate_errors(root: Path, scene_id: str) -> list[str]:
    composition = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    try:
        payload = ensure_composition_ready_for_generation(root, composition)
    except (FlowGateError, json.JSONDecodeError, OSError, ValueError) as exc:
        return [str(exc)]
    if payload.get("ready_for_generation") is not True:
        return ["composition ready_for_generation must be true before prose generation"]
    provenance = payload.get("formal_cli_provenance") if isinstance(payload.get("formal_cli_provenance"), dict) else {}
    if provenance.get("agent_tasks_requested") is not True:
        return ["composition was not created with --agent-tasks; composition sidecar is required"]
    return []


def _word_budget_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    scene_path = _scene_path_for_task(root, task)
    try:
        contract = ensure_scene_word_budget_ready(root, scene_path)
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)]
    if contract.get("status") == "not_required":
        return []
    errors: list[str] = []
    scene_inventory_task = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    if scene_inventory_task.exists():
        completion = agent_task_completion_status(scene_inventory_task, root=root)
        if completion.get("complete") is not True:
            errors.append(f"scene-inventory word-budget sidecar is incomplete: {completion.get('message')}")
    scene_inventory_review = root / "reviews" / "word_budget" / "scene_inventory_review.md"
    if scene_inventory_task.exists() and not scene_inventory_review.exists():
        errors.append("formal longform scene generation requires reviews/word_budget/scene_inventory_review.md")
    return errors


def _candidate_generation_gate_errors(root: Path, task: dict[str, object], candidate: Path) -> list[str]:
    scene_id = str(task.get("scene_id") or candidate.stem.split("-")[0])
    gate = candidate_generation_gate(root, scene_id, candidate)
    if gate.get("status") == "pass":
        return []
    details: list[str] = [str(gate.get("message") or "candidate generation gate failed")]
    missing = gate.get("missing")
    invalid = gate.get("invalid")
    if isinstance(missing, list) and missing:
        details.append("missing=" + ", ".join(str(item) for item in missing))
    if isinstance(invalid, list) and invalid:
        details.append("invalid=" + ", ".join(str(item) for item in invalid))
    return ["; ".join(details)]


def _candidate_body_gate_errors(root: Path, task: dict[str, object], candidate: Path) -> list[str]:
    if not candidate.exists():
        return [f"candidate Markdown is missing: {_rel(candidate, root)}"]
    scene_path = _scene_path_for_task(root, task)
    body = final_body_from_draft_path(candidate)
    errors: list[str] = []
    if not body:
        errors.append(f"candidate has no cleaned deliverable body: {_rel(candidate, root)}")
        return errors
    lint_gate = style_lint_gate(body)
    if lint_gate.get("status") == "blocking":
        errors.append(f"candidate failed Style Lint Gate: {style_lint_gate_message(lint_gate)}")
    budget = word_budget_adherence_for_body(root, scene_path, body)
    if budget.get("status") not in {"pass", "not_required"}:
        errors.append(f"candidate failed scene word-budget gate: {budget.get('message')}")
    return errors


def _candidate_review_gate_errors(root: Path, task: dict[str, object], candidate: Path) -> list[str]:
    scene_id = str(task.get("scene_id") or candidate.stem.split("-")[0])
    gate = candidate_review_gate(root, scene_id, candidate)
    if gate.get("status") == "pass":
        return []
    message = str(gate.get("message") or "candidate review gate failed")
    lint_gate = gate.get("style_lint")
    if isinstance(lint_gate, dict) and lint_gate.get("status") == "blocking":
        message += f"; Style Lint Gate: {style_lint_gate_message(lint_gate)}"
    return [message]


def _promotion_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    scene_id = str(task.get("scene_id") or "")
    manifest_path = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    payload, error = _read_optional_json(manifest_path)
    if error:
        return [error]
    if not payload:
        return [f"promotion manifest is missing or empty: {_rel(manifest_path, root)}"]
    errors: list[str] = []
    if payload.get("allow_unreviewed") is True:
        errors.append("promotion manifest uses allow_unreviewed=true; debug review bypass is forbidden for formal Skill hosts")
    if payload.get("allow_review_notes") is True:
        errors.append("promotion manifest uses allow_review_notes=true; pass_with_notes must be revised and re-reviewed")
    candidate_value = str(payload.get("candidate") or "")
    if not candidate_value:
        errors.append("promotion manifest does not record candidate path")
        return errors
    candidate = _resolve_project_path(root, candidate_value)
    errors.extend(_candidate_generation_gate_errors(root, task, candidate))
    errors.extend(_candidate_review_gate_errors(root, task, candidate))
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    if draft.exists() and not final_body_from_draft_path(draft):
        errors.append(f"promoted draft has no cleaned deliverable body: {_rel(draft, root)}")
    return errors


def _static_review_gate_errors(root: Path, scene_id: str) -> list[str]:
    path = root / "reviews" / f"{scene_id}-review.md"
    conclusion = _static_review_conclusion(path)
    if conclusion == "pass":
        return []
    return [f"static review conclusion must be pass; got {conclusion or 'missing'} at {_rel(path, root)}"]


def _state_patch_gate_errors(root: Path, scene_id: str) -> list[str]:
    path = root / "characters" / "state_patches" / f"{scene_id}_state_patch.json"
    payload, error = _read_optional_json(path)
    if error:
        return [error]
    if not payload:
        return [f"state patch JSON is missing or empty: {_rel(path, root)}"]
    errors: list[str] = []
    if str(payload.get("schema") or "") != "literary-engineering-workbench/character-state-patch/v0.1":
        errors.append("state patch JSON has wrong or missing schema")
    if str(payload.get("scene_id") or "") not in {"", scene_id}:
        errors.append(f"state patch scene_id mismatch: {payload.get('scene_id')}")
    if str(payload.get("status") or "").strip().lower() not in {"pending_human_approval", "candidate", "reviewed", "approved"}:
        errors.append("state patch status must remain candidate/review/approval-scoped")
    return errors


def _candidate_path_for_task(root: Path, task: dict[str, object]) -> Path:
    candidates = [
        *[str(item) for item in task.get("submitted_artifacts") or []],
        *[str(item) for item in task.get("expected_outputs") or []],
        *[str(item) for item in task.get("source_paths") or []],
    ]
    for item in candidates:
        normalized = item.replace("\\", "/")
        if not normalized.endswith(".md"):
            continue
        if normalized.endswith(".agent_tasks.md") or normalized.endswith(".prompt.md"):
            continue
        if "/drafts/candidates/" in f"/{normalized}" or "/drafts/revisions/" in f"/{normalized}":
            return _resolve_project_path(root, item)
    scene_id = str(task.get("scene_id") or "scene")
    return root / "drafts" / "candidates" / f"{scene_id}-platform-agent.md"


def _scene_path_for_task(root: Path, task: dict[str, object]) -> Path:
    scene = str(task.get("scene") or "")
    if scene:
        return _resolve_project_path(root, scene)
    scene_id = str(task.get("scene_id") or "scene_0001")
    return root / "scenes" / f"{scene_id}.yaml"


def _static_review_conclusion(path: Path) -> str:
    text = _read_text(path)
    match = re.search(r"(?m)^-\s*结论：\s*`?([^`\s]+)`?\s*$", text)
    return match.group(1).strip().lower() if match else ""


def _read_optional_json(path: Path) -> tuple[dict[str, object], str]:
    if not path.exists():
        return {}, f"JSON file missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {_rel(path, path.parent)} ({exc.msg})"
    except OSError as exc:
        return {}, str(exc)
    if not isinstance(payload, dict):
        return {}, f"JSON root is not an object: {path}"
    return payload, ""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def _load_task(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"task not found: {path}")
    payload = _read_json(path)
    if payload.get("schema") != TASK_SCHEMA:
        raise ValueError(f"not an agent task registry file: {path}")
    return payload


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {path}") from exc
    return payload if isinstance(payload, dict) else {}


def _append_event(root: Path, event_type: str, task_id: str, data: dict[str, object]) -> None:
    path = _events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": EVENT_SCHEMA,
        "event_type": event_type,
        "task_id": task_id,
        "created_at": _now(),
        "data": data,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    events: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = {"schema": EVENT_SCHEMA, "event_type": "invalid", "task_id": "", "created_at": "", "data": {"raw": line}}
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _render_events_markdown(events: list[dict[str, object]]) -> str:
    lines = [
        "# Workflow Events",
        "",
        f"- events: {len(events)}",
        "",
        "| 时间 | 事件 | task_id | 数据 |",
        "| --- | --- | --- | --- |",
    ]
    for event in events:
        data = json.dumps(event.get("data") or {}, ensure_ascii=False)
        lines.append(f"| {event.get('created_at', '')} | {event.get('event_type', '')} | {event.get('task_id', '')} | `{data}` |")
    return "\n".join(lines).rstrip() + "\n"


def _task_json_path(root: Path, task_id: str) -> Path:
    return root / "workflow" / "tasks" / f"{task_id}.task.json"


def _task_markdown_path(root: Path, task_id: str) -> Path:
    return root / "workflow" / "tasks" / f"{task_id}.agent_tasks.md"


def _submission_path(root: Path, task_id: str) -> Path:
    return root / "workflow" / "tasks" / f"{task_id}.submission.json"


def _events_path(root: Path) -> Path:
    return root / "workflow" / "events" / "task_events.jsonl"


def _task_id(route: str, scene_id: str, current_state: str) -> str:
    return _slug(f"{route}__{scene_id}__{current_state}")


def _slug(value: str) -> str:
    text = value.strip().lower().replace("_", "-")
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "task"


def _resolve_project_path(root: Path, value: Path | str) -> Path:
    path = value if isinstance(value, Path) else Path(str(value))
    return path if path.is_absolute() else root / path


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _normalize_route(route: str) -> str:
    return route.strip().lower().replace("_", "-")


def _normalize_rel(value: str | Path) -> str:
    return Path(str(value)).as_posix()


def _project_scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)\s*$", text)
    if not match:
        return ""
    value = match.group(1).strip()
    if value in {"null", "[]", "{}"}:
        return ""
    return value.strip("\"'")


def _project_int(text: str, key: str) -> int:
    return _to_int(_project_scalar(text, key))


def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).replace(",", "").replace("_", "").strip())
    except (TypeError, ValueError):
        return 0


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
