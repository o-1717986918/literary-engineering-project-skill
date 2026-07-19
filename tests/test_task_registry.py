import json
import unittest
from pathlib import Path

from literary_engineering_workbench.agent_tasks import default_agent_completion_path, write_agent_completion_marker
from literary_engineering_workbench.approval import record_workflow_approval
from literary_engineering_workbench.asset_workshop import create_asset_candidate, promote_candidate_asset
from literary_engineering_workbench.canon_lint import build_canon_lint
from literary_engineering_workbench.chapter_pipeline import build_chapter_workspace
from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.context_packet import build_context_packet
from literary_engineering_workbench.export_package import build_export_package
from literary_engineering_workbench.longform_audit import build_longform_audit
from literary_engineering_workbench.platform_agent_tasks import (
    write_platform_asset_creation_task,
    write_platform_asset_review_task,
    write_platform_canon_review_task,
    write_platform_committee_task,
)
from literary_engineering_workbench.publish import publish_chapter
from literary_engineering_workbench.task_registry import (
    complete_task,
    issue_next_task,
    open_task,
    submit_task,
)
from literary_engineering_workbench.source_ingest import ingest_existing_work
from literary_engineering_workbench.style_compiler import StyleCompileOptions, compile_style_profile
from literary_engineering_workbench.platform_agent_tasks import write_platform_style_prompt_task
from literary_engineering_workbench.word_budget import build_word_budget

from helpers import TempProjectMixin, make_reviewed_passing_scene, write_formal_candidate_artifacts


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
        self.assertIn("memory/context_packets/scene_0001.trace.json", payload["expected_outputs"])
        self.assertEqual(payload["context_trace"], "memory/context_packets/scene_0001.trace.json")
        self.assertIn("task-submit", payload["submission_command"])

        task_text = result.task_markdown_path.read_text(encoding="utf-8")
        self.assertIn("[AGENT_TASK:", task_text)
        self.assertIn("创建或覆盖 `memory/context_packets/scene_0001.md`", task_text)
        self.assertIn("创建或覆盖 `memory/context_packets/scene_0001.trace.json`", task_text)

    def test_task_next_repairs_context_trace_when_packet_exists_without_trace(self):
        project = self.make_project()
        context = build_context_packet(project, scene=Path("scenes/scene_0001.yaml"), rebuild_index=True)
        context.trace_path.unlink()

        result = issue_next_task(project, route="scene-development")

        self.assertEqual(result.status, "issued")
        self.assertEqual(result.current_state, "context-trace")
        payload = json.loads(result.task_json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["prompt_asset_id"], "route.scene-development.context.trace.v1")
        self.assertIn("memory/context_packets/scene_0001.trace.json", payload["expected_outputs"])

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

    def test_task_next_supports_longform_planning_with_word_budget_task(self):
        project = self.make_project()

        result = issue_next_task(project, route="longform-planning")

        self.assertEqual(result.status, "issued")
        self.assertEqual(result.scene_id, "longform")
        self.assertEqual(result.current_state, "word-budget-file")
        payload = json.loads(result.task_json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["route"], "longform-planning")
        self.assertEqual(payload["prompt_asset_id"], "route.longform-planning.word-budget.prepare.v1")
        self.assertIn("word-budget", payload["command"])
        self.assertIn("plot/word_budget/word_budget.json", payload["expected_outputs"])
        self.assertIn("plot/word_budget/scene_inventory_expansion.agent_tasks.md", payload["expected_outputs"])

        task_text = result.task_markdown_path.read_text(encoding="utf-8")
        self.assertIn("docs/modules/longform-word-budget.md", task_text)
        self.assertIn("不得只手写文件后跳到下一步", task_text)

    def test_task_next_moves_to_longform_budget_agent_task_after_budget_scaffold(self):
        project = self.make_project()
        build_word_budget(project, target_words=120000, volumes=2, genre="general")

        result = issue_next_task(project, route="longform-planning")

        self.assertEqual(result.current_state, "budget-agent-task")
        payload = json.loads(result.task_json_path.read_text(encoding="utf-8"))
        self.assertIn("plot/candidates/outlines/word_budget_expansion.md", payload["expected_outputs"])
        self.assertIn("reviews/word_budget/word_budget_review.md", payload["expected_outputs"])
        self.assertIn("plot/word_budget/word_budget.agent_completion.json", payload["expected_outputs"])

    def test_longform_task_complete_blocks_pass_with_notes_budget_review(self):
        project = self.make_project()
        result = build_word_budget(project, target_words=120000, volumes=2, genre="general")
        outline = project / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"
        outline.write_text("# 预算化大纲候选\n\n- 测试候选。\n", encoding="utf-8")
        _write_longform_review(project, "word_budget_review", "pass_with_notes")
        write_agent_completion_marker(result.agent_tasks_path, root=project, handled_by="platform-agent-test")

        issued = issue_next_task(project, route="longform-planning")

        self.assertEqual(issued.current_state, "budget-review")
        with self.assertRaises(ValueError) as ctx:
            complete_task(project, issued.task_id)
        self.assertIn("word-budget review conclusion must be pass", str(ctx.exception))
        self.assertIn("pass_with_notes", str(ctx.exception))

    def test_longform_task_complete_blocks_missing_budget_candidate_even_with_marker(self):
        project = self.make_project()
        result = build_word_budget(project, target_words=120000, volumes=2, genre="general")
        _write_longform_review(project, "word_budget_review", "pass")
        write_agent_completion_marker(result.agent_tasks_path, root=project, handled_by="platform-agent-test")

        issued = issue_next_task(project, route="longform-planning")

        self.assertEqual(issued.current_state, "budget-agent-task")
        with self.assertRaises(FileNotFoundError) as ctx:
            complete_task(project, issued.task_id)
        self.assertIn("plot/candidates/outlines/word_budget_expansion.md", str(ctx.exception))

    def test_longform_task_reaches_scene_inventory_and_ready_after_required_artifacts(self):
        project = self.make_project()
        result = build_word_budget(project, target_words=120000, volumes=2, genre="general")
        outline = project / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"
        outline.write_text("# 预算化大纲候选\n\n- 测试候选。\n", encoding="utf-8")
        _write_longform_review(project, "word_budget_review", "pass")
        write_agent_completion_marker(result.agent_tasks_path, root=project, handled_by="platform-agent-test")

        next_task = issue_next_task(project, route="longform-planning")
        self.assertEqual(next_task.current_state, "scene-inventory-agent-task")

        inventory = project / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"
        inventory.write_text("# 分场景库存候选\n\n- 测试场景库存。\n", encoding="utf-8")
        _write_longform_review(project, "scene_inventory_review", "pass")
        write_agent_completion_marker(result.scene_inventory_tasks_path, root=project, handled_by="platform-agent-test")

        ready = issue_next_task(project, route="longform-planning")
        self.assertEqual(ready.status, "ready")
        self.assertEqual(ready.message, "longform-planning route is ready")

    def test_cli_exposes_task_registry_commands(self):
        help_text = build_parser().format_help()
        for command in ("task-next", "task-open", "task-submit", "task-complete", "workflow-advance", "workflow-events", "workflow-validate"):
            self.assertIn(command, help_text)

    def test_cli_task_next_runs(self):
        project = self.make_project()
        code = main(["task-next", str(project)])

        self.assertEqual(code, 0)
        task_dir = project / "workflow" / "tasks"
        self.assertTrue(any(task_dir.glob("*.task.json")))

    def test_cli_task_next_longform_runs(self):
        project = self.make_project()
        code = main(["task-next", str(project), "--route", "longform-planning"])

        self.assertEqual(code, 0)
        task_dir = project / "workflow" / "tasks"
        self.assertTrue(any(task_dir.glob("longform-planning-longform-word-budget-file.task.json")))

    def test_task_next_source_ingest_ready_without_imports(self):
        project = self.make_project()

        result = issue_next_task(project, route="source-ingest")

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.message, "source-ingest route has no pending imported source")

    def test_task_next_source_ingest_issues_extraction_task_for_import(self):
        project = self.make_project()
        ingest_existing_work(
            project,
            text="林舟在旧楼里发现档案。档案留下了一个组织编号。",
            title="旧楼档案",
            work_id="old-archive",
        )

        result = issue_next_task(project, route="source-ingest")

        self.assertEqual(result.status, "issued")
        self.assertEqual(result.scene_id, "old-archive")
        self.assertEqual(result.current_state, "extraction-agent-task")
        payload = json.loads(result.task_json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["route"], "source-ingest")
        self.assertIn("sources/imports/old-archive/extract_project_files.agent_completion.json", payload["expected_outputs"])
        self.assertIn("characters/candidates/extracted/old-archive_characters.md", payload["expected_outputs"])
        self.assertIn("reviews/source_ingest/old-archive_extraction_review.md", payload["expected_outputs"])

    def test_source_ingest_task_complete_blocks_missing_extraction_outputs(self):
        project = self.make_project()
        ingest_existing_work(
            project,
            text="林舟在旧楼里发现档案。档案留下了一个组织编号。",
            title="旧楼档案",
            work_id="old-archive",
        )
        issued = issue_next_task(project, route="source-ingest")

        with self.assertRaises(FileNotFoundError) as ctx:
            complete_task(project, issued.task_id)

        self.assertIn("characters/candidates/extracted/old-archive_characters.md", str(ctx.exception))

    def test_source_ingest_review_with_notes_blocks_ready(self):
        project = self.make_project()
        result = ingest_existing_work(
            project,
            text="林舟在旧楼里发现档案。档案留下了一个组织编号。",
            title="旧楼档案",
            work_id="old-archive",
        )
        _write_source_extraction_outputs(project, result.manifest_path, conclusion="pass_with_notes")
        write_agent_completion_marker(result.task_path, root=project, handled_by="platform-agent-test")

        issued = issue_next_task(project, route="source-ingest")

        self.assertEqual(issued.current_state, "extraction-review")
        with self.assertRaises(ValueError) as ctx:
            complete_task(project, issued.task_id)
        self.assertIn("source-ingest extraction review conclusion must be pass", str(ctx.exception))

    def test_source_ingest_route_ready_after_extraction_and_review(self):
        project = self.make_project()
        result = ingest_existing_work(
            project,
            text="林舟在旧楼里发现档案。档案留下了一个组织编号。",
            title="旧楼档案",
            work_id="old-archive",
        )
        _write_source_extraction_outputs(project, result.manifest_path, conclusion="pass")
        write_agent_completion_marker(result.task_path, root=project, handled_by="platform-agent-test")

        ready = issue_next_task(project, route="source-ingest")

        self.assertEqual(ready.status, "ready")

    def test_task_next_style_engineering_issues_prompt_task_for_profile(self):
        project = self.make_project()
        profile_dir = _compile_style_profile(project)

        result = issue_next_task(project, route="style-engineering")

        self.assertEqual(result.status, "issued")
        self.assertEqual(result.current_state, "style-prompt-task-file")
        payload = json.loads(result.task_json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["route"], "style-engineering")
        self.assertIn("style-prompt", payload["command"])
        self.assertIn("style/demo-author/style_prompt.agent_tasks.md", payload["expected_outputs"])
        self.assertIn("docs/modules/style-compiler.md", payload["required_reading"])

    def test_style_engineering_blocks_short_style_prompt(self):
        project = self.make_project()
        profile_dir = _compile_style_profile(project)
        task = write_platform_style_prompt_task(profile_dir)
        (profile_dir / "style_prompt.md").write_text("太短。\n", encoding="utf-8")
        (profile_dir / "style_prompt.agent.json").write_text("{}\n", encoding="utf-8")
        write_agent_completion_marker(task.task_path, root=project, handled_by="platform-agent-test")

        issued = issue_next_task(project, route="style-engineering")

        self.assertEqual(issued.current_state, "style-prompt-quality")
        with self.assertRaises(ValueError) as ctx:
            complete_task(project, issued.task_id)
        self.assertIn("style_prompt.md detail length must be 500-2500", str(ctx.exception))

    def test_style_engineering_route_ready_after_prompt_and_eval(self):
        project = self.make_project()
        profile_dir = _compile_style_profile(project)
        task = write_platform_style_prompt_task(profile_dir)
        _write_valid_style_prompt(profile_dir)
        write_agent_completion_marker(task.task_path, root=project, handled_by="platform-agent-test")
        eval_dir = profile_dir / "evaluation_results" / "back-translation"
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / "style_eval_ready.json").write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/style-eval/v0.1",
                    "mode": "back-translation",
                    "overall_score": 78,
                    "risk_level": "normal",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        ready = issue_next_task(project, route="style-engineering")

        self.assertEqual(ready.status, "ready")

    def test_style_engineering_requires_accepted_eval_after_prompt(self):
        project = self.make_project()
        profile_dir = _compile_style_profile(project)
        task = write_platform_style_prompt_task(profile_dir)
        _write_valid_style_prompt(profile_dir)
        write_agent_completion_marker(task.task_path, root=project, handled_by="platform-agent-test")

        issued = issue_next_task(project, route="style-engineering")

        self.assertEqual(issued.current_state, "style-eval-readiness")
        with self.assertRaises(ValueError) as ctx:
            complete_task(project, issued.task_id)
        self.assertIn("accepted style_eval_*.json missing", str(ctx.exception))

    def test_character_world_assets_route_starts_with_intake_task(self):
        project = self.make_project()

        issued = issue_next_task(project, route="character-and-world-assets")

        self.assertEqual(issued.status, "issued")
        self.assertEqual(issued.scene_id, "asset-intake")
        self.assertEqual(issued.current_state, "asset-intake")
        payload = json.loads(issued.task_json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["route"], "character-and-world-assets")
        self.assertIn("asset-create", payload["command"])
        with self.assertRaises(ValueError) as ctx:
            complete_task(project, issued.task_id)
        self.assertIn("no candidate asset or asset creation sidecar exists", str(ctx.exception))

    def test_character_world_assets_moves_from_creation_to_review_task(self):
        project = self.make_project()
        candidate = create_asset_candidate(project, asset_type="character", brief="谨慎调查者", target_id="linzhou", provider="dry-run")
        task = write_platform_asset_creation_task(
            project,
            asset_type="character",
            brief="谨慎调查者",
            target_id="linzhou",
            candidate_path=candidate.candidate_path,
            report_path=candidate.report_path,
        )
        write_agent_completion_marker(task.task_path, root=project, handled_by="platform-agent-test")

        issued = issue_next_task(project, route="character-and-world-assets")

        self.assertEqual(issued.current_state, "asset-review-task-file")
        self.assertIn(candidate.candidate_id.lower(), issued.task_id)
        payload = json.loads(issued.task_json_path.read_text(encoding="utf-8"))
        self.assertIn("review-candidate-asset", payload["command"])

    def test_character_world_assets_blocks_unreviewed_asset_review(self):
        project = self.make_project()
        candidate = create_asset_candidate(project, asset_type="character", brief="谨慎调查者", target_id="linzhou", provider="dry-run")
        creation = write_platform_asset_creation_task(
            project,
            asset_type="character",
            brief="谨慎调查者",
            target_id="linzhou",
            candidate_path=candidate.candidate_path,
            report_path=candidate.report_path,
        )
        write_agent_completion_marker(creation.task_path, root=project, handled_by="platform-agent-test")
        review = write_platform_asset_review_task(project, candidate_path=candidate.candidate_path)
        write_agent_completion_marker(review.task_path, root=project, handled_by="platform-agent-test")

        issued = issue_next_task(project, route="character-and-world-assets")

        self.assertEqual(issued.current_state, "asset-review-agent-task")
        with self.assertRaises(FileNotFoundError):
            complete_task(project, issued.task_id)

    def test_character_world_assets_requires_approval_before_promotion(self):
        project = self.make_project()
        candidate = create_asset_candidate(project, asset_type="character", brief="谨慎调查者", target_id="linzhou", provider="dry-run")
        _write_asset_creation_completion(project, candidate)
        review = write_platform_asset_review_task(project, candidate_path=candidate.candidate_path)
        _write_clean_asset_review(project, candidate.candidate_id, candidate.candidate_path)
        write_agent_completion_marker(review.task_path, root=project, handled_by="platform-agent-test")

        issued = issue_next_task(project, route="character-and-world-assets")

        self.assertEqual(issued.current_state, "asset-approval")
        with self.assertRaises(FileNotFoundError) as ctx:
            complete_task(project, issued.task_id)
        self.assertIn("workflow/approvals/index.jsonl", str(ctx.exception))

    def test_character_world_assets_route_ready_after_promotion(self):
        project = self.make_project()
        candidate = create_asset_candidate(project, asset_type="character", brief="谨慎调查者", target_id="linzhou", provider="dry-run")
        _write_asset_creation_completion(project, candidate)
        review = write_platform_asset_review_task(project, candidate_path=candidate.candidate_path)
        _write_clean_asset_review(project, candidate.candidate_id, candidate.candidate_path)
        write_agent_completion_marker(review.task_path, root=project, handled_by="platform-agent-test")
        record_workflow_approval(project, candidate.candidate_id, "approve", actor="tester")
        promote_candidate_asset(project, candidate.candidate_path, group="character", approval_run_id=candidate.candidate_id)

        ready = issue_next_task(project, route="character-and-world-assets")

        self.assertEqual(ready.status, "ready")

    def test_review_audit_route_starts_with_canon_lint_task(self):
        project = self.make_project()

        issued = issue_next_task(project, route="review-and-audit")

        self.assertEqual(issued.status, "issued")
        self.assertEqual(issued.current_state, "canon-lint-file")
        payload = json.loads(issued.task_json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["route"], "review-and-audit")
        self.assertIn("canon-lint", payload["command"])
        self.assertIn("reviews/canon_lint.json", payload["expected_outputs"])

    def test_review_audit_blocks_pass_with_notes_canon_review(self):
        project = self.make_project()
        build_canon_lint(project)
        task = write_platform_canon_review_task(project)
        _write_canon_review(project, conclusion="pass_with_notes", warnings=["仍有待解释的角色状态风险。"])
        write_agent_completion_marker(task.task_path, root=project, handled_by="platform-agent-test")

        issued = issue_next_task(project, route="review-and-audit")

        self.assertEqual(issued.current_state, "canon-review-pass")
        with self.assertRaises(ValueError) as ctx:
            complete_task(project, issued.task_id)
        self.assertIn("canon review conclusion must be pass", str(ctx.exception))

    def test_review_audit_route_ready_after_clean_committee(self):
        project = self.make_project()
        build_canon_lint(project)
        canon_task = write_platform_canon_review_task(project)
        _write_canon_review(project, conclusion="pass")
        write_agent_completion_marker(canon_task.task_path, root=project, handled_by="platform-agent-test")
        build_longform_audit(project)
        committee_task = write_platform_committee_task(project, subject="project-final-audit", source=project / "reviews" / "agent" / "canon_review.md")
        _write_committee_review(project, final_recommendation="approve")
        write_agent_completion_marker(committee_task.task_path, root=project, handled_by="platform-agent-test")

        ready = issue_next_task(project, route="review-and-audit")

        self.assertEqual(ready.status, "ready")

    def test_export_release_route_issues_chapter_workspace_task(self):
        project = self.make_project()

        issued = issue_next_task(project, route="export-and-release")

        self.assertEqual(issued.status, "issued")
        self.assertEqual(issued.scene_id, "chapter_0001")
        self.assertEqual(issued.current_state, "chapter-workspace")
        payload = json.loads(issued.task_json_path.read_text(encoding="utf-8"))
        self.assertIn("chapter-workspace", payload["command"])
        self.assertIn("plot/chapters/chapter_0001.json", payload["expected_outputs"])

    def test_export_release_blocks_include_blocked_export_manifest(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        build_chapter_workspace(project, chapter_id="chapter_0001")
        build_export_package(project, chapter_id="chapter_0001", include_blocked=True)

        issued = issue_next_task(project, route="export-and-release")

        self.assertEqual(issued.current_state, "export-package")
        with self.assertRaises(ValueError) as ctx:
            complete_task(project, issued.task_id)
        self.assertIn("include_blocked", str(ctx.exception))

    def test_export_release_route_ready_after_approved_publish(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        build_chapter_workspace(project, chapter_id="chapter_0001")
        build_export_package(project, chapter_id="chapter_0001", formats="md,docx")
        record_workflow_approval(project, "release-chapter_0001", "approve", actor="tester")
        publish_chapter(
            project,
            chapter_id="chapter_0001",
            release_id="formal-release",
            approval_run_id="release-chapter_0001",
            export_formats="md,docx",
        )

        ready = issue_next_task(project, route="export-and-release")

        self.assertEqual(ready.status, "ready")


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
        "new_character_register": {
            "schema": "literary-engineering-workbench/new-character-register/v0.1",
            "status": "none",
            "introduced": [],
            "ephemeral_waivers": [],
            "blocking_issues": [],
        },
        "source_paths": [
            "scenes/scene_0001.yaml",
            rel_candidate,
            "memory/context_packets/scene_0001.md",
            "memory/context_packets/scene_0001.trace.json",
        ],
        "agent_confidence": "platform-test",
        "next_gate": "promote_candidate",
    }
    review_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_md.write_text(f"# 候选审查\n\n- 结论：`{conclusion}`\n", encoding="utf-8")
    review_task.write_text("# 平台 Agent 任务说明：fixture candidate review\n", encoding="utf-8")
    write_agent_completion_marker(review_task, root=project, handled_by="platform-agent-test")
    return review_json, review_md, review_task


def _write_longform_review(project: Path, name: str, conclusion: str) -> Path:
    review_dir = project / "reviews" / "word_budget"
    review_dir.mkdir(parents=True, exist_ok=True)
    path = review_dir / f"{name}.md"
    path.write_text(f"# Longform Review\n\n- 结论：`{conclusion}`\n", encoding="utf-8")
    return path


def _write_source_extraction_outputs(project: Path, manifest_path: Path, *, conclusion: str) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs = manifest["candidate_outputs"]
    for key, rel in outputs.items():
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if key == "review":
            path.write_text(f"# Source Ingest Review\n\n- 结论：`{conclusion}`\n", encoding="utf-8")
        else:
            path.write_text(f"# {key}\n\n- evidence_refs: chunk_0001\n- confidence: test\n", encoding="utf-8")


def _compile_style_profile(project: Path) -> Path:
    corpus = project / "corpus"
    corpus.mkdir(exist_ok=True)
    (corpus / "sample.txt").write_text(
        "雨落在旧城。人们沉默地走过桥。灯影在河面上摇晃。"
        "林舟没有解释，只把信折好，放进旧书里。",
        encoding="utf-8",
    )
    return compile_style_profile(
        StyleCompileOptions(
            corpus=corpus,
            output_dir=project / "style" / "demo-author",
            name="测试文风",
            author="测试作者",
            source_note="测试语料",
        )
    ).output_dir


def _write_valid_style_prompt(profile_dir: Path) -> None:
    text = """# LLM 文风约束提示词

## 使用身份与适用边界

你是长篇虚构文本生成 LLM。本文风只约束表达层，不确认 canon，不新增人物事实，不替剧情解决因果问题。文风优先级高于普通润色建议，但低于用户明确要求、世界规则、人物事实和安全边界。

## 核心风格机制

风格来自叙述距离、信息分配、句法重心、意象回环和心理呈现，不来自复用高频词。每个段落必须承担推进事件、暴露关系、改变注意力或加深主题中的一种功能。

## 叙述距离与视角

叙述距离保持稳定。人物的判断通过迟疑、回避、误判、沉默、动作折返和对白遮掩呈现，少写解释性心理标签。

## 句法与节奏

句法跟随人物注意力和场景压力变化。紧张处可以短，但不能连续碎句；舒缓处可以长，但逗号必须承接未完成动作、感知、心理或因果关系。

## 标点节奏

中文正文使用全角标点。句号用于真实语义、镜头或心理落点；逗号用于未完成关系；分号用于层级并列。原则上不用破折号，不能用破折号替代转折。

## 意象与感官调度

意象从场景物理空间和人物处境中生长，重复意象必须带来关系或认知变化。感官描写优先服务行动和信息差。

## 心理呈现与行为因果

心理变化通过行为、背景故事的隐性影响、选择、停顿、回避和误判表现。不要把背景故事直接讲成说明段。

## 对白与语气

对白要有信息差和关系压力。角色说话应带目标、遮掩、误会或试探，不能朗读设定。

## AI腔控制

机械“不是……而是……”“并非……而是……”以及“不是……——是……”是核心禁区，不判断为合理修辞。器官轮岗、万能占位、比喻依赖、抽象总结、模板转折和景物强制同步按约 2% 叙事单元密度控制。

## 禁止倾向

不得摘抄原文，不得把风格简化为几个固定词，不得把候选事实写成 canon，不得用密集句号、破折号或金句收尾伪装文学性。

## 输出自检

检查叙述距离是否稳定，意象是否服务人物状态，标点是否服务节奏，AI腔风险是否低于密度门禁，文本是否仍服从项目事实。
"""
    (profile_dir / "style_prompt.md").write_text(text, encoding="utf-8")
    (profile_dir / "style_prompt.agent.json").write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/style-prompt-agent/v1",
                "prompt_markdown": "style_prompt.md",
                "constraints": ["测试可挂载文风约束"],
                "source_paths": ["style-profile.md", "style_metrics.json"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_asset_creation_completion(project: Path, candidate) -> None:
    task = write_platform_asset_creation_task(
        project,
        asset_type="character",
        brief="谨慎调查者",
        target_id="linzhou",
        candidate_path=candidate.candidate_path,
        report_path=candidate.report_path,
    )
    write_agent_completion_marker(task.task_path, root=project, handled_by="platform-agent-test")


def _write_clean_asset_review(project: Path, candidate_id: str, candidate_path: Path) -> None:
    review_dir = project / "reviews" / "assets"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_json = review_dir / f"{candidate_id}_review.json"
    review_md = review_dir / f"{candidate_id}_review.md"
    review_json.write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/candidate-asset-review/v0.1",
                "candidate": _rel(project, candidate_path),
                "candidate_id": candidate_id,
                "asset_type": "character",
                "status": "pass",
                "blocking_issues": [],
                "warnings": [],
                "revision_actions": [],
                "promotion_risks": [],
                "reviewed_at": "2026-07-18T00:00:00+00:00",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    review_md.write_text("# Candidate Asset Review\n\n- Status：`pass`\n", encoding="utf-8")


def _write_canon_review(project: Path, *, conclusion: str, warnings: list[str] | None = None) -> None:
    review_dir = project / "reviews" / "agent"
    review_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/canon-review-agent/v1",
        "conclusion": conclusion,
        "summary": "平台 Agent canon review fixture。",
        "blocking_issues": [],
        "warnings": warnings or [],
        "unresolved_facts": [],
        "timeline_risks": [],
        "source_paths": ["reviews/canon_lint.md", "reviews/canon_lint.json", "canon/", "characters/", "scenes/", "plot/"],
        "recommendations": [] if conclusion == "pass" and not warnings else ["先解决 notes 后再进入导出。"],
        "next_gate": "committee_review",
    }
    (review_dir / "canon_review.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (review_dir / "canon_review.md").write_text(f"# Canon Review\n\n- 结论：`{conclusion}`\n", encoding="utf-8")


def _write_committee_review(project: Path, *, final_recommendation: str, action_items: list[str] | None = None) -> None:
    review_dir = project / "reviews" / "agent"
    review_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/committee-review-agent/v1",
        "subject": "project-final-audit",
        "final_recommendation": final_recommendation,
        "reviewers": [
            {"reviewer_id": "chief-editor", "stance": "approve", "findings": [], "recommendations": [], "source_paths": []},
            {"reviewer_id": "canon-auditor", "stance": "approve", "findings": [], "recommendations": [], "source_paths": []},
        ],
        "disagreements": [],
        "action_items": action_items or [],
        "source_paths": ["reviews/agent/canon_review.json", "reviews/longform/longform_audit.json"],
        "minority_opinions": [],
    }
    (review_dir / "committee_project-final-audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (review_dir / "committee_project-final-audit.md").write_text(
        f"# Committee Review\n\n- Final Recommendation：`{final_recommendation}`\n",
        encoding="utf-8",
    )


def _rel(project: Path, value: Path | str) -> str:
    path = value if isinstance(value, Path) else Path(value)
    if path.is_absolute():
        return path.resolve().relative_to(project.resolve()).as_posix()
    return path.as_posix()


if __name__ == "__main__":
    unittest.main()
