import json
import unittest
from pathlib import Path

from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.context_packet import build_context_packet
from literary_engineering_workbench.task_registry import complete_task, issue_next_task, submit_task
from literary_engineering_workbench.workflow_contract import validate_workflow_contract

from helpers import TempProjectMixin


class WorkflowContractTests(TempProjectMixin, unittest.TestCase):
    def test_workflow_validate_passes_after_formal_context_task(self):
        project = self.make_project()
        issued = issue_next_task(project, route="scene-development")
        context = build_context_packet(project, scene=Path("scenes/scene_0001.yaml"), rebuild_index=True)
        submit_task(project, issued.task_id, [context.output_path, context.trace_path])
        complete_task(project, issued.task_id, handled_by="platform-agent-test")

        result = validate_workflow_contract(project, route="scene-development")

        self.assertEqual(result.status, "pass")
        self.assertEqual(result.error_count, 0)
        self.assertTrue(result.markdown_path.exists())
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "literary-engineering-workbench/workflow-contract-validation/v0.1")
        self.assertEqual(payload["status"], "pass")

    def test_workflow_validate_flags_downstream_pass_after_missing_upstream(self):
        project = self.make_project()
        branch_dir = project / "branches" / "scene_0001"
        branch_dir.mkdir(parents=True, exist_ok=True)
        (branch_dir / "branch_manifest.json").write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/branch-simulation/v0.1",
                    "scene_id": "scene_0001",
                    "formal_cli_provenance": {"created_by": "branch-simulate", "agent_tasks_requested": True},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        result = validate_workflow_contract(project, route="scene-development")

        self.assertEqual(result.status, "fail")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        messages = "\n".join(item["message"] for item in payload["errors"])
        self.assertIn("downstream step is pass", messages)

    def test_workflow_validate_flags_event_referencing_missing_task(self):
        project = self.make_project()
        events = project / "workflow" / "events" / "task_events.jsonl"
        events.parent.mkdir(parents=True, exist_ok=True)
        events.write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/workflow-event/v1",
                    "event_type": "task_completed",
                    "task_id": "ghost-task",
                    "created_at": "2026-07-19T00:00:00+00:00",
                    "data": {},
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        result = validate_workflow_contract(project, route="scene-development")

        self.assertEqual(result.status, "fail")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertIn("event references missing task", "\n".join(item["message"] for item in payload["errors"]))

    def test_cli_exposes_and_runs_workflow_validate(self):
        self.assertIn("workflow-validate", build_parser().format_help())
        project = self.make_project()

        code = main(["workflow-validate", str(project), "--route", "scene-development"])

        self.assertEqual(code, 0)
        self.assertTrue((project / "workflow" / "workflow_contract.json").exists())


if __name__ == "__main__":
    unittest.main()
