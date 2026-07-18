import json
import unittest
from pathlib import Path

from literary_engineering_workbench.agent_tasks import default_agent_completion_path, write_agent_completion_marker
from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.context_packet import build_context_packet
from literary_engineering_workbench.task_registry import (
    complete_task,
    issue_next_task,
    open_task,
    submit_task,
)

from helpers import TempProjectMixin, write_formal_candidate_artifacts


class TaskRegistryTests(TempProjectMixin, unittest.TestCase):
    def test_task_next_issues_context_task_for_first_blocked_scene(self):
        project = self.make_project()

        result = issue_next_task(project, route="scene-development")

        self.assertEqual(result.status, "issued")
        self.assertEqual(result.scene_id, "scene_0001")
        self.assertEqual(result.current_state, "context-packet")
        self.assertTrue(result.task_json_path.exists())
        self.assertTrue(result.task_markdown_path.exists())

        payload = json.loads(result.task_json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "literary-engineering-workbench/agent-task/v1")
        self.assertEqual(payload["route"], "scene-development")
        self.assertEqual(payload["prompt_asset_id"], "route.scene-development.context.v1")
        self.assertIn("memory/context_packets/scene_0001.md", payload["expected_outputs"])
        self.assertIn("task-submit", payload["submission_command"])

        task_text = result.task_markdown_path.read_text(encoding="utf-8")
        self.assertIn("[AGENT_TASK:", task_text)
        self.assertIn("创建或覆盖 `memory/context_packets/scene_0001.md`", task_text)

    def test_task_open_marks_task_opened(self):
        project = self.make_project()
        issued = issue_next_task(project)

        opened = open_task(project, issued.task_id)

        self.assertEqual(opened.status, "opened")
        payload = json.loads(opened.task_json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "opened")
        self.assertIn("opened_at", payload)

    def test_task_submit_records_existing_artifact(self):
        project = self.make_project()
        issued = issue_next_task(project)
        context = build_context_packet(project, scene=Path("scenes/scene_0001.yaml"), rebuild_index=True)

        submitted = submit_task(project, issued.task_id, [context.output_path])

        self.assertEqual(submitted.status, "submitted")
        self.assertTrue(submitted.submission_path.exists())
        payload = json.loads(submitted.submission_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["task_id"], issued.task_id)
        self.assertIn("memory/context_packets/scene_0001.md", payload["artifacts"])

    def test_task_submit_rejects_missing_artifact(self):
        project = self.make_project()
        issued = issue_next_task(project)

        with self.assertRaises(FileNotFoundError):
            submit_task(project, issued.task_id, ["memory/context_packets/missing.md"])

    def test_task_complete_blocks_missing_expected_output(self):
        project = self.make_project()
        issued = issue_next_task(project)

        with self.assertRaises(FileNotFoundError):
            complete_task(project, issued.task_id)

        payload = json.loads(issued.task_json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["validation"]["status"], "fail")

    def test_task_complete_writes_completion_marker_and_events(self):
        project = self.make_project()
        issued = issue_next_task(project)
        context = build_context_packet(project, scene=Path("scenes/scene_0001.yaml"), rebuild_index=True)
        submit_task(project, issued.task_id, [context.output_path])

        completed = complete_task(project, issued.task_id, handled_by="platform-agent-test")

        self.assertEqual(completed.status, "complete")
        marker = default_agent_completion_path(completed.task_markdown_path)
        self.assertTrue(marker.exists())
        marker_payload = json.loads(marker.read_text(encoding="utf-8"))
        self.assertEqual(marker_payload["status"], "complete")
        self.assertTrue(marker_payload["expected_artifacts_checked"])

        events = project / "workflow" / "events" / "task_events.jsonl"
        self.assertTrue(events.exists())
        text = events.read_text(encoding="utf-8")
        self.assertIn("task_issued", text)
        self.assertIn("task_submitted", text)
        self.assertIn("task_completed", text)

    def test_task_complete_blocks_handwritten_composition_without_cli_provenance(self):
        project = self.make_project()
        composition_dir = project / "drafts" / "compositions"
        composition_dir.mkdir(parents=True, exist_ok=True)
        json_path = composition_dir / "scene_0001_composition.json"
        md_path = composition_dir / "scene_0001_composition.md"
        task_path = composition_dir / "scene_0001_composition.agent_tasks.md"
        json_path.write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/scene-composition/v0.1",
                    "scene_id": "scene_0001",
                    "selection_source": "selection",
                    "selected_branch": "branch_a",
                    "ready_for_generation": True,
                    "flow_gate": {"ready_for_generation": True},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        md_path.write_text("# composition\n", encoding="utf-8")
        task_path.write_text("# task\n", encoding="utf-8")
        task = _write_registry_task(
            project,
            "composition-json",
            [md_path, json_path, task_path],
        )

        with self.assertRaises(ValueError) as ctx:
            complete_task(project, task["task_id"])

        self.assertIn("formal_cli_provenance.created_by=compose-scene", str(ctx.exception))

    def test_task_complete_blocks_candidate_without_generation_provenance(self):
        project = self.make_project()
        candidate = project / "drafts" / "candidates" / "scene_0001-platform-agent.md"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("## 正文候选\n\n林舟走进楼道。\n", encoding="utf-8")
        task = _write_registry_task(project, "candidate-generation-provenance", [candidate])

        with self.assertRaises(ValueError) as ctx:
            complete_task(project, task["task_id"])

        self.assertIn("formal candidate generation files are missing", str(ctx.exception))

    def test_task_complete_blocks_candidate_generation_with_style_lint_violation(self):
        project = self.make_project()
        candidate = project / "drafts" / "candidates" / "scene_0001-platform-agent.md"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(
            """# Candidate

## 正文候选

不是C营的——是那个E营的年轻人。他把袖章塞进衣袋，转身上楼。

## 状态变化候选

### 新增事实候选

- E营袖章成为候选线索。
""",
            encoding="utf-8",
        )
        write_formal_candidate_artifacts(project, candidate)
        task = _write_registry_task(
            project,
            "candidate-generation-provenance",
            [
                candidate,
                candidate.with_suffix(".json"),
                candidate.with_suffix(".prompt.json"),
                candidate.with_suffix(".agent_tasks.md"),
                candidate.with_suffix(".agent_completion.json"),
            ],
        )

        with self.assertRaises(ValueError) as ctx:
            complete_task(project, task["task_id"])

        self.assertIn("Style Lint Gate", str(ctx.exception))
        self.assertIn("mechanical-contrast-frame", str(ctx.exception))

    def test_task_complete_blocks_candidate_review_with_notes(self):
        project = self.make_project()
        candidate = project / "drafts" / "candidates" / "scene_0001-platform-agent.md"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(
            """# Candidate

## 正文候选

林舟到了楼上。门半开着。桌上有一页纸，被杯子压住。

## 状态变化候选

### 新增事实候选

- 林舟发现纸页线索。
""",
            encoding="utf-8",
        )
        write_formal_candidate_artifacts(project, candidate)
        review_json, review_md, review_task = _write_candidate_review(project, candidate, conclusion="pass_with_notes")
        task = _write_registry_task(
            project,
            "candidate-review",
            [
                review_json,
                review_md,
                review_task,
                review_task.with_name("scene_0001_scene_review.agent_completion.json"),
            ],
            source_paths=[candidate, candidate.with_suffix(".json"), "memory/context_packets/scene_0001.md"],
        )

        with self.assertRaises(ValueError) as ctx:
            complete_task(project, task["task_id"])

        self.assertIn("pass_with_notes", str(ctx.exception))

    def test_task_complete_blocks_word_budget_without_agent_sidecar_completion(self):
        project = self.make_project()
        scene_path = project / "scenes" / "scene_0001.yaml"
        scene_path.write_text(scene_path.read_text(encoding="utf-8").replace('chapter_id: ""', "chapter_id: chapter_0001"), encoding="utf-8")
        from literary_engineering_workbench.word_budget import build_word_budget

        result = build_word_budget(project, target_words=120000, volumes=2, genre="general")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        payload["status"] = "pass"
        payload["issues"] = []
        result.json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        task = _write_registry_task(project, "scene-word-budget-contract", [result.json_path])

        with self.assertRaises(ValueError) as ctx:
            complete_task(project, task["task_id"])

        self.assertIn("word-budget platform-agent task", str(ctx.exception))

    def test_task_complete_blocks_static_review_without_clean_pass(self):
        project = self.make_project()
        review = project / "reviews" / "scene_0001-review.md"
        review.parent.mkdir(parents=True, exist_ok=True)
        review.write_text("# 静态审查\n\n- 结论：`revise_required`\n", encoding="utf-8")
        task = _write_registry_task(project, "static-review", [review])

        with self.assertRaises(ValueError) as ctx:
            complete_task(project, task["task_id"])

        self.assertIn("static review conclusion must be pass", str(ctx.exception))

    def test_task_complete_blocks_invalid_state_patch_json(self):
        project = self.make_project()
        patch = project / "characters" / "state_patches" / "scene_0001_state_patch.json"
        patch.parent.mkdir(parents=True, exist_ok=True)
        patch.write_text("{ invalid", encoding="utf-8")
        task = _write_registry_task(project, "state-patch-json", [patch])

        with self.assertRaises(ValueError) as ctx:
            complete_task(project, task["task_id"])

        self.assertIn("invalid JSON", str(ctx.exception))

    def test_task_next_moves_to_roleplay_after_context_completion(self):
        project = self.make_project()
        issued = issue_next_task(project)
        context = build_context_packet(project, scene=Path("scenes/scene_0001.yaml"), rebuild_index=True)
        submit_task(project, issued.task_id, [context.output_path])
        complete_task(project, issued.task_id)

        next_task = issue_next_task(project)

        self.assertEqual(next_task.current_state, "roleplay-simulation")
        payload = json.loads(next_task.task_json_path.read_text(encoding="utf-8"))
        self.assertIn("simulate-scene", payload["command"])
        self.assertIn("branches/scene_0001/roleplay_simulation.agent_tasks.md", payload["expected_outputs"])

    def test_cli_exposes_task_registry_commands(self):
        help_text = build_parser().format_help()
        for command in ("task-next", "task-open", "task-submit", "task-complete", "workflow-advance", "workflow-events"):
            self.assertIn(command, help_text)

    def test_cli_task_next_runs(self):
        project = self.make_project()
        code = main(["task-next", str(project)])

        self.assertEqual(code, 0)
        task_dir = project / "workflow" / "tasks"
        self.assertTrue(any(task_dir.glob("*.task.json")))

def _write_registry_task(
    project: Path,
    current_state: str,
    expected_outputs: list[Path | str],
    *,
    source_paths: list[Path | str] | None = None,
    scene_id: str = "scene_0001",
) -> dict[str, object]:
    task_id = f"test-{current_state}"
    task_dir = project / "workflow" / "tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_json = task_dir / f"{task_id}.task.json"
    task_md = task_dir / f"{task_id}.agent_tasks.md"
    task_md.write_text(f"# Test task {current_state}\n", encoding="utf-8")
    payload = {
        "schema": "literary-engineering-workbench/agent-task/v1",
        "task_id": task_id,
        "status": "submitted",
        "route": "scene-development",
        "scene_id": scene_id,
        "scene": f"scenes/{scene_id}.yaml",
        "current_state": current_state,
        "task_type": "test",
        "expected_outputs": [_rel(project, item) for item in expected_outputs],
        "source_paths": [_rel(project, item) for item in (source_paths or [])],
    }
    task_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _write_candidate_review(project: Path, candidate: Path, *, conclusion: str) -> tuple[Path, Path, Path]:
    review_dir = project / "reviews" / "agent"
    review_dir.mkdir(parents=True, exist_ok=True)
    rel_candidate = candidate.resolve().relative_to(project.resolve()).as_posix()
    review_json = review_dir / "scene_0001_scene_review.json"
    review_md = review_dir / "scene_0001_scene_review.md"
    review_task = review_dir / "scene_0001_scene_review.agent_tasks.md"
    has_notes = conclusion != "pass"
    payload = {
        "schema": "literary-engineering-workbench/scene-review-agent/v1",
        "scene_id": "scene_0001",
        "conclusion": conclusion,
        "summary": "测试候选审查。",
        "blocking_issues": [],
        "warnings": ["需局部修订。"] if has_notes else [],
        "revision_actions": ["按 notes 修改后重审。"] if has_notes else [],
        "character_logic": [{"character": "all", "assessment": "测试。"}],
        "canon_risks": [],
        "style_notes": ["风格 notes。"] if has_notes else [],
        "style_adherence": {
            "status": "not_applicable",
            "style_profile": "n/a",
            "evidence": [],
            "deviations": [],
            "revision_actions": [],
        },
        "word_budget_adherence": {
            "status": "not_required",
            "target_words": 0,
            "min_words": 0,
            "max_words": 0,
            "clean_body_words": 80,
            "narrative_load_satisfied": True,
            "message": "test project does not require longform budget",
        },
        "source_paths": [
            "scenes/scene_0001.yaml",
            rel_candidate,
            "memory/context_packets/scene_0001.md",
        ],
        "agent_confidence": "platform-test",
        "next_gate": "promote_candidate",
    }
    review_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_md.write_text(f"# 候选审查\n\n- 结论：`{conclusion}`\n", encoding="utf-8")
    review_task.write_text("# 平台 Agent 任务说明：fixture candidate review\n", encoding="utf-8")
    write_agent_completion_marker(review_task, root=project, handled_by="platform-agent-test")
    return review_json, review_md, review_task


def _rel(project: Path, value: Path | str) -> str:
    path = value if isinstance(value, Path) else Path(value)
    if path.is_absolute():
        return path.resolve().relative_to(project.resolve()).as_posix()
    return path.as_posix()


if __name__ == "__main__":
    unittest.main()
