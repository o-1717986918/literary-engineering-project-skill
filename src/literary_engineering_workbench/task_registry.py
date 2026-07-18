"""CLI-mediated task registry for formal platform-agent work."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .agent_tasks import agent_task_completion_status, default_agent_completion_path, write_agent_completion_marker
from .anti_ai_style import style_lint_gate, style_lint_gate_message
from .candidate_promotion import candidate_generation_gate, candidate_review_gate
from .draft_text import final_body_from_draft_path
from .flow_gates import FlowGateError, branch_selection_status, ensure_composition_ready_for_generation
from .word_budget import ensure_scene_word_budget_ready, word_budget_adherence_for_body
from .workflow_state import build_workflow_state


TASK_SCHEMA = "literary-engineering-workbench/agent-task/v1"
SUBMISSION_SCHEMA = "literary-engineering-workbench/agent-submission/v1"
EVENT_SCHEMA = "literary-engineering-workbench/workflow-event/v1"
SUPPORTED_ROUTES = {"scene-development"}


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
        raise ValueError(f"task registry currently supports only scene-development, got: {normalized_route}")
    state_payload = _workflow_payload(root, normalized_route)
    scene_state = _select_scene_state(root, state_payload, scene)
    if scene_state is None:
        return TaskRegistryResult(
            project_root=root,
            task_id="",
            task_json_path=None,
            task_markdown_path=None,
            status="ready",
            route=normalized_route,
            scene_id="",
            current_state="ready",
            message="no pending scene-development task found",
        )
    scene_id = str(scene_state.get("scene_id") or "")
    current_state = str(scene_state.get("current_step") or "")
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
            message=f"scene {scene_id or 'n/a'} is ready",
        )

    task = _build_task_payload(root, normalized_route, scene_state)
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
                scene_id=scene_id,
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

    gate_errors, gate_notes = _state_gate_validation(root, task)
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
    state = build_workflow_state(root, route=str(task.get("route") or "scene-development"))
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
