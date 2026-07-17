"""Shared workflow gates for formal creative handoffs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


FORMAL_BRANCH_DECISIONS = {
    "select",
    "selected",
    "approve",
    "approved",
    "accept",
    "accepted",
    "merge",
    "merged",
    "hybrid",
}
PENDING_BRANCH_VALUES = {"", "none", "n/a", "pending", "todo", "待定"}


class FlowGateError(RuntimeError):
    """Raised when a workflow tries to cross a formal approval boundary."""


def branch_selection_status(path: Path) -> dict[str, str]:
    """Return a normalized status for a branch_selection.md file."""

    if not path.exists():
        return {
            "status": "missing",
            "decision": "",
            "selected_branch": "",
            "reviewer": "",
            "message": "branch_selection.md does not exist",
        }
    text = path.read_text(encoding="utf-8", errors="ignore")
    decision = _field(text, "decision").lower()
    selected = _field(text, "selected_branch")
    reviewer = _field(text, "reviewer")
    if selected.lower() in PENDING_BRANCH_VALUES:
        selected = ""
    if decision in PENDING_BRANCH_VALUES:
        decision = ""
    if selected and decision in FORMAL_BRANCH_DECISIONS:
        status = "selected"
        message = "formal branch selection is present"
    elif selected:
        status = "incomplete"
        message = "selected_branch is filled but decision is still pending or not formal"
    else:
        status = "pending"
        message = "selected_branch is empty"
    return {
        "status": status,
        "decision": decision,
        "selected_branch": selected,
        "reviewer": reviewer,
        "message": message,
    }


def selected_branch_from(path: Path) -> str:
    status = branch_selection_status(path)
    return status["selected_branch"] if status["status"] == "selected" else ""


def ensure_composition_ready_for_generation(
    root: Path,
    composition_path: Path | None,
    *,
    allow_unselected_composition: bool = False,
) -> dict[str, Any]:
    """Reject composition packets that have not crossed the branch-selection gate."""

    if composition_path is None:
        return {}
    json_path = composition_path if composition_path.suffix.lower() == ".json" else composition_path.with_suffix(".json")
    if not json_path.exists():
        raise FlowGateError(
            f"composition gate requires companion JSON before generation: {json_path}"
        )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    source = str(payload.get("selection_source") or "")
    selected = str(payload.get("selected_branch") or "")
    flow_gate = payload.get("flow_gate", {}) if isinstance(payload.get("flow_gate"), dict) else {}
    ready = flow_gate.get("ready_for_generation")
    if allow_unselected_composition:
        return payload
    if source != "selection" or ready is False:
        rel = _rel(composition_path, root)
        raise FlowGateError(
            "formal branch selection required before generate-scene: "
            f"{rel} has selection_source={source or 'missing'} selected_branch={selected or 'none'}. "
            "Fill branch_selection.md with decision: selected and selected_branch, then rebuild compose-scene. "
            "For internal experiments only, pass allow_unselected_composition=True or the CLI flag."
        )
    return payload


def _field(text: str, name: str) -> str:
    match = re.search(rf"(?mi)^\s*-?\s*{re.escape(name)}:\s*`?([^`\n#]*)`?\s*$", text)
    if not match:
        return ""
    return match.group(1).strip().strip("`").strip()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
