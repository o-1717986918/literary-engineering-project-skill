"""Persistent formal-route state ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .agent_tasks import agent_task_completion_status
from .candidate_promotion import candidate_generation_gate, candidate_review_gate
from .flow_gates import branch_selection_status
from .word_budget import scene_word_budget_contract


@dataclass(frozen=True)
class WorkflowStateResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    route: str
    scene_count: int
    blocked_count: int
    ready_count: int
    next_action_count: int


def build_workflow_state(
    project_root: Path,
    *,
    route: str = "scene-development",
    output: Path | None = None,
    json_output: Path | None = None,
) -> WorkflowStateResult:
    """Write a persistent state ledger for the formal route."""

    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    normalized_route = _normalize_route(route) or "scene-development"
    scenes = _scene_states(root) if normalized_route in {"scene-development", "overall"} else []
    longform = _longform_state(root) if normalized_route in {"longform-planning", "overall"} else {}
    source_ingests = _source_ingest_states(root) if normalized_route in {"source-ingest", "overall"} else []
    longform_blocked = 1 if longform and longform.get("status") != "ready" else 0
    longform_ready = 1 if longform and longform.get("status") == "ready" else 0
    summary = {
        "route": normalized_route,
        "scene_count": len(scenes),
        "source_ingest_count": len(source_ingests),
        "ready_count": (
            sum(1 for scene in scenes if scene["status"] == "ready")
            + longform_ready
            + sum(1 for item in source_ingests if item["status"] == "ready")
        ),
        "blocked_count": (
            sum(1 for scene in scenes if scene["status"] != "ready")
            + longform_blocked
            + sum(1 for item in source_ingests if item["status"] != "ready")
        ),
        "next_action_count": (
            sum(1 for scene in scenes if scene.get("next_action"))
            + (1 if longform and longform.get("next_action") else 0)
            + sum(1 for item in source_ingests if item.get("next_action"))
        ),
        "longform_status": longform.get("status", "") if isinstance(longform, dict) else "",
    }
    payload = {
        "schema": "literary-engineering-workbench/formal-route-state/v1",
        "generated_at": _now(),
        "project_root": str(root),
        "route": normalized_route,
        "summary": summary,
        "scenes": scenes,
        "longform": longform,
        "source_ingests": source_ingests,
        "rules": [
            "This state ledger is advisory plus auditable; command-level gates remain authoritative.",
            "A step is pass only when the formal CLI artifact and its platform-agent completion marker both exist where required.",
            "Formal Skill hosts must not use allow/unreview/include-blocked debug flags to move the state forward.",
        ],
    }
    markdown_path = _resolve_output(root, output, "workflow", "route_state.md")
    json_path = _resolve_output(root, json_output, "workflow", "route_state.json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(payload), encoding="utf-8")
    return WorkflowStateResult(
        project_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
        route=normalized_route,
        scene_count=summary["scene_count"],
        blocked_count=summary["blocked_count"],
        ready_count=summary["ready_count"],
        next_action_count=summary["next_action_count"],
    )


def _scene_states(root: Path) -> list[dict[str, object]]:
    scenes = root / "scenes"
    if not scenes.exists():
        return []
    return [_scene_state(root, path) for path in sorted(scenes.glob("*.yaml")) if not path.name.startswith("_")]


def _longform_state(root: Path) -> dict[str, object]:
    steps = [
        _word_budget_file_step(root),
        _longform_task_step(
            "budget-agent-task",
            root,
            root / "plot" / "word_budget" / "word_budget.agent_tasks.md",
            [root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"],
            "complete word_budget.agent_tasks.md, budgeted outline candidate, and budget review",
        ),
        _longform_review_step(
            "budget-review",
            root / "reviews" / "word_budget" / "word_budget_review.md",
            "write a clean word-budget review with conclusion: pass",
        ),
        _longform_task_step(
            "scene-inventory-agent-task",
            root,
            root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md",
            [root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"],
            "complete scene_inventory_expansion.agent_tasks.md, scene inventory candidate, and review",
        ),
        _longform_review_step(
            "scene-inventory-review",
            root / "reviews" / "word_budget" / "scene_inventory_review.md",
            "write a clean scene inventory review with conclusion: pass",
        ),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "target_id": "longform",
        "scene_id": "longform",
        "scene": "project.yaml",
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _word_budget_file_step(root: Path) -> dict[str, object]:
    json_path = root / "plot" / "word_budget" / "word_budget.json"
    markdown_path = root / "plot" / "word_budget" / "word_budget.md"
    budget_task = root / "plot" / "word_budget" / "word_budget.agent_tasks.md"
    scene_task = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    required = [json_path, markdown_path, budget_task, scene_task]
    missing = [_rel(path, root) for path in required if not path.exists()]
    if missing:
        return {
            "key": "word-budget-file",
            "status": "missing",
            "path": _rel(json_path, root),
            "message": "missing " + ", ".join(missing),
            "next_action": "run word-budget / longform-budget to create budget JSON, report, and platform-agent sidecars",
        }
    payload = _read_json(json_path)
    if not payload or payload.get("schema") != "literary-engineering-workbench/word-budget/v1":
        return {
            "key": "word-budget-file",
            "status": "invalid",
            "path": _rel(json_path, root),
            "message": "word_budget.json is invalid or has wrong schema",
            "next_action": "rerun word-budget / longform-budget",
        }
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    return {
        "key": "word-budget-file",
        "status": "pass",
        "path": _rel(json_path, root),
        "message": f"word budget exists; status={payload.get('status', '')}",
        "target_words": totals.get("target_words", 0),
        "chapter_count": totals.get("chapter_count", 0),
        "scene_count": totals.get("scene_count", 0),
        "next_action": "",
    }


def _longform_review_step(key: str, path: Path, next_action: str) -> dict[str, object]:
    conclusion = _static_review_conclusion(path)
    return {
        "key": key,
        "status": "pass" if conclusion == "pass" else conclusion or "missing",
        "path": str(path),
        "message": f"conclusion={conclusion or 'missing'}",
        "next_action": "" if conclusion == "pass" else next_action,
    }


def _source_ingest_states(root: Path) -> list[dict[str, object]]:
    imports = root / "sources" / "imports"
    if not imports.exists():
        return []
    states: list[dict[str, object]] = []
    for manifest in sorted(imports.glob("*/source_manifest.json")):
        states.append(_source_ingest_state(root, manifest.parent))
    return states


def _source_ingest_state(root: Path, import_dir: Path) -> dict[str, object]:
    manifest_path = import_dir / "source_manifest.json"
    report_path = import_dir / "source_ingest.md"
    task_path = import_dir / "extract_project_files.agent_tasks.md"
    manifest = _read_json(manifest_path)
    work_id = str(manifest.get("work_id") or import_dir.name)
    candidate_outputs = _source_candidate_outputs(manifest)
    review_path = root / str(candidate_outputs.get("review") or f"reviews/source_ingest/{work_id}_extraction_review.md")
    candidate_paths = [root / rel for key, rel in candidate_outputs.items() if key != "review"]
    steps = [
        _source_manifest_step(root, manifest_path, report_path, task_path),
        _source_extraction_step(root, task_path, candidate_paths, review_path),
        _longform_review_step(
            "extraction-review",
            review_path,
            "write source-ingest extraction review with conclusion: pass",
        ),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "target_id": work_id,
        "work_id": work_id,
        "import_dir": _rel(import_dir, root),
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _source_manifest_step(root: Path, manifest_path: Path, report_path: Path, task_path: Path) -> dict[str, object]:
    missing = [_rel(path, root) for path in (manifest_path, report_path, task_path) if not path.exists()]
    if missing:
        return {
            "key": "source-manifest",
            "status": "missing",
            "path": _rel(manifest_path, root),
            "message": "missing " + ", ".join(missing),
            "next_action": "run source-ingest with source/text/title/work-id to create manifest, report, and extraction sidecar",
        }
    payload = _read_json(manifest_path)
    if payload.get("schema") != "literary-engineering-workbench/source-ingest/v1":
        return {
            "key": "source-manifest",
            "status": "invalid",
            "path": _rel(manifest_path, root),
            "message": "source_manifest.json is invalid or has wrong schema",
            "next_action": "rerun source-ingest or repair the manifest from source evidence",
        }
    return {
        "key": "source-manifest",
        "status": "pass",
        "path": _rel(manifest_path, root),
        "message": f"source manifest exists; chunks={payload.get('chunk_count', 0)}",
        "next_action": "",
    }


def _source_extraction_step(root: Path, task_path: Path, candidate_paths: list[Path], review_path: Path) -> dict[str, object]:
    state = agent_task_completion_status(task_path, root=root)
    required = [*candidate_paths, review_path]
    missing = [_rel(path, root) for path in required if not path.exists()]
    complete = state.get("complete") is True and not missing
    message = str(state.get("message") or "")
    if missing:
        message = (message + "; " if message else "") + "missing " + ", ".join(missing)
    return {
        "key": "extraction-agent-task",
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(task_path, root),
        "completion": state.get("completion", ""),
        "message": message,
        "next_action": "" if complete else "complete source extraction sidecar, extracted candidates, review report, and completion marker",
    }


def _source_candidate_outputs(manifest: dict[str, object]) -> dict[str, str]:
    outputs = manifest.get("candidate_outputs") if isinstance(manifest.get("candidate_outputs"), dict) else {}
    return {str(key): str(value) for key, value in outputs.items() if str(value).strip()}


def _scene_state(root: Path, scene_path: Path) -> dict[str, object]:
    scene_id = _scene_id(scene_path)
    candidate = _promotion_candidate_path(root, scene_id) or _latest_scene_candidate(root, scene_id)
    steps = [
        _file_step("context-packet", root / "memory" / "context_packets" / f"{scene_id}.md", "run context --scene scenes/{scene}.yaml".format(scene=scene_id)),
        _file_step("roleplay-simulation", root / "branches" / scene_id / "roleplay_simulation.md", "run simulate-scene --agent"),
        _task_step("roleplay-agent-task", root, root / "branches" / scene_id / "roleplay_simulation.agent_tasks.md", "complete roleplay_simulation.agent_tasks.md and marker"),
        _file_step("branch-manifest", root / "branches" / scene_id / "branch_manifest.json", "run branch-simulate --agent"),
        _task_step("branch-agent-task", root, root / "branches" / scene_id / "branch_manifest.agent_tasks.md", "complete branch_manifest.agent_tasks.md and marker"),
        _branch_selection_step(root / "branches" / scene_id / "branch_selection.md"),
        _file_step("composition-json", root / "drafts" / "compositions" / f"{scene_id}_composition.json", "run compose-scene --agent-tasks"),
        _task_step("composition-agent-task", root, root / "drafts" / "compositions" / f"{scene_id}_composition.agent_tasks.md", "complete scene composition sidecar and marker"),
        _word_budget_step(root, scene_path),
        _candidate_step(root, scene_id, candidate),
        _task_step("generation-agent-task", root, candidate.with_suffix(".agent_tasks.md") if candidate else root / "drafts" / "candidates" / f"{scene_id}-platform-agent.agent_tasks.md", "complete generation sidecar and marker"),
        _review_step(root, scene_id, candidate),
        _task_step("agent-review-task", root, root / "reviews" / "agent" / f"{scene_id}_scene_review.agent_tasks.md", "complete AgentReview sidecar and marker"),
        _file_step("promotion-manifest", root / "drafts" / "promotions" / f"{scene_id}_promotion.json", "run promote-candidate after exact candidate review"),
        _file_step("promoted-draft", root / "drafts" / "scenes" / f"{scene_id}.md", "promote a reviewed candidate into drafts/scenes"),
        _static_review_step(root, scene_id),
        _file_step("state-patch-json", root / "characters" / "state_patches" / f"{scene_id}_state_patch.json", "run state-evolve --agent-tasks"),
        _task_step("state-agent-task", root, root / "characters" / "state_patches" / f"{scene_id}_state_patch.agent_tasks.md", "complete state-evolve sidecar and marker"),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "scene_id": scene_id,
        "scene": _rel(scene_path, root),
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _file_step(key: str, path: Path, next_action: str) -> dict[str, object]:
    return {
        "key": key,
        "status": "pass" if path.exists() else "missing",
        "path": str(path),
        "message": "exists" if path.exists() else "missing",
        "next_action": "" if path.exists() else next_action,
    }


def _task_step(key: str, root: Path, path: Path, next_action: str) -> dict[str, object]:
    state = agent_task_completion_status(path, root=root)
    complete = state.get("complete") is True
    return {
        "key": key,
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(path, root),
        "completion": state.get("completion", ""),
        "message": state.get("message", ""),
        "next_action": "" if complete else next_action,
    }


def _longform_task_step(key: str, root: Path, path: Path, required_outputs: list[Path], next_action: str) -> dict[str, object]:
    state = agent_task_completion_status(path, root=root)
    missing = [_rel(item, root) for item in required_outputs if not item.exists()]
    complete = state.get("complete") is True and not missing
    message = str(state.get("message") or "")
    if missing:
        message = (message + "; " if message else "") + "missing " + ", ".join(missing)
    return {
        "key": key,
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(path, root),
        "completion": state.get("completion", ""),
        "message": message,
        "next_action": "" if complete else next_action,
    }


def _branch_selection_step(path: Path) -> dict[str, object]:
    state = branch_selection_status(path)
    return {
        "key": "branch-selection",
        "status": "pass" if state["status"] == "selected" else state["status"],
        "path": str(path),
        "message": state["message"],
        "selected_branch": state["selected_branch"],
        "next_action": "" if state["status"] == "selected" else "fill branch_selection.md with decision: selected and selected_branch",
    }


def _word_budget_step(root: Path, scene_path: Path) -> dict[str, object]:
    contract = scene_word_budget_contract(root, scene_path)
    status = str(contract.get("status") or "")
    passed = status in {"pass", "not_required"}
    return {
        "key": "scene-word-budget-contract",
        "status": "pass" if passed else status or "missing",
        "path": str(contract.get("budget_path") or ""),
        "message": contract.get("message", ""),
        "target_words": contract.get("target_words", 0),
        "min_words": contract.get("min_words", 0),
        "max_words": contract.get("max_words", 0),
        "next_action": "" if passed else "run word-budget, handle budget sidecars, review scene inventory, then retry generation",
    }


def _candidate_step(root: Path, scene_id: str, candidate: Path | None) -> dict[str, object]:
    if candidate is None:
        return {
            "key": "candidate-generation-provenance",
            "status": "missing",
            "path": "",
            "message": "no formal candidate found",
            "next_action": "run generate-scene, then have the main platform agent write candidate Markdown and manifest",
        }
    gate = candidate_generation_gate(root, scene_id, candidate)
    return {
        "key": "candidate-generation-provenance",
        "status": "pass" if gate.get("status") == "pass" else str(gate.get("status") or "missing"),
        "path": _rel(candidate, root),
        "message": gate.get("message", ""),
        "next_action": "" if gate.get("status") == "pass" else "complete generate-scene sidecar, candidate Markdown, manifest, prompt manifest, and completion marker",
    }


def _review_step(root: Path, scene_id: str, candidate: Path | None) -> dict[str, object]:
    if candidate is None:
        return {
            "key": "candidate-review",
            "status": "missing",
            "path": f"reviews/agent/{scene_id}_scene_review.json",
            "message": "no candidate to review",
            "next_action": "generate a formal candidate first",
        }
    gate = candidate_review_gate(root, scene_id, candidate)
    return {
        "key": "candidate-review",
        "status": "pass" if gate.get("status") == "pass" else str(gate.get("status") or "missing"),
        "path": str(gate.get("review") or ""),
        "message": gate.get("message", ""),
        "next_action": "" if gate.get("status") == "pass" else "run agent-review-scene --draft <candidate>, then write review JSON/MD and completion marker",
    }


def _static_review_step(root: Path, scene_id: str) -> dict[str, object]:
    path = root / "reviews" / f"{scene_id}-review.md"
    conclusion = _static_review_conclusion(path)
    return {
        "key": "static-review",
        "status": "pass" if conclusion == "pass" else conclusion or "missing",
        "path": _rel(path, root),
        "message": f"conclusion={conclusion or 'missing'}",
        "next_action": "" if conclusion == "pass" else "run review-scene on the promoted draft and resolve notes",
    }


def _promotion_candidate_path(root: Path, scene_id: str) -> Path | None:
    payload = _read_json(root / "drafts" / "promotions" / f"{scene_id}_promotion.json")
    candidate = str(payload.get("candidate") or "").strip()
    if not candidate:
        return None
    path = Path(candidate)
    return path if path.is_absolute() else root / path


def _latest_scene_candidate(root: Path, scene_id: str) -> Path | None:
    candidates: list[Path] = []
    for directory, pattern in (
        (root / "drafts" / "candidates", f"{scene_id}-*.md"),
        (root / "drafts" / "revisions", f"{scene_id}_revision.md"),
    ):
        if directory.exists():
            candidates.extend(path for path in directory.glob(pattern) if not path.name.endswith(".agent_tasks.md") and not path.name.endswith(".prompt.md"))
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def _static_review_conclusion(path: Path) -> str:
    text = _read(path)
    match = re.search(r"(?m)^-\s*结论：\s*`?([^`\s]+)`?\s*$", text)
    return match.group(1).strip().lower() if match else ""


def _scene_id(path: Path) -> str:
    text = _read(path)
    match = re.search(r"(?m)^\s*scene_id:\s*['\"]?([^'\"\n#]+)", text)
    if match:
        scene_id = match.group(1).strip().strip("\"'")
        if scene_id:
            return scene_id
    return path.stem


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _render_markdown(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    lines = [
        f"# Formal Route State：{payload['route']}",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 场景数：{summary['scene_count']}",
        f"- Ready：{summary['ready_count']}",
        f"- Blocked：{summary['blocked_count']}",
        f"- Next actions：{summary['next_action_count']}",
        "",
        "## Scene State",
        "",
        "| 场景 | 状态 | 当前步骤 | 下一步 |",
        "| --- | --- | --- | --- |",
    ]
    for scene in payload.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        lines.append(
            f"| {scene.get('scene_id', '')} | {scene.get('status', '')} | {scene.get('current_step', '')} | {scene.get('next_action', '')} |"
        )
    longform = payload.get("longform") if isinstance(payload.get("longform"), dict) else {}
    if longform:
        lines.extend(["", "## Longform State", ""])
        lines.append(
            f"- 状态：`{longform.get('status', '')}`；当前步骤：`{longform.get('current_step', '')}`；下一步：{longform.get('next_action', '') or 'n/a'}"
        )
        lines.extend(["", "| 步骤 | 状态 | 信息 |", "| --- | --- | --- |"])
        for step in longform.get("steps", []):
            if not isinstance(step, dict):
                continue
            lines.append(f"| {step.get('key', '')} | {step.get('status', '')} | {step.get('message', '')} |")
    source_ingests = payload.get("source_ingests") if isinstance(payload.get("source_ingests"), list) else []
    if source_ingests:
        lines.extend(["", "## Source Ingest State", "", "| work_id | 状态 | 当前步骤 | 下一步 |", "| --- | --- | --- | --- |"])
        for item in source_ingests:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item.get('work_id', '')} | {item.get('status', '')} | {item.get('current_step', '')} | {item.get('next_action', '')} |"
            )
    lines.extend(["", "## Details", ""])
    for scene in payload.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        lines.extend([f"### {scene.get('scene_id', '')}", ""])
        for step in scene.get("steps", []):
            if not isinstance(step, dict):
                continue
            lines.append(f"- `{step.get('key', '')}`：{step.get('status', '')}。{step.get('message', '')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _normalize_route(route: str) -> str:
    return route.strip().lower().replace("_", "-")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
