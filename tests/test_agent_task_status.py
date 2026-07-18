import json
import unittest

from literary_engineering_workbench.agent_task_status import build_agent_task_status, build_route_audit
from literary_engineering_workbench.cli import build_parser

from helpers import TempProjectMixin, make_reviewed_passing_scene, write_platform_scene_review


class AgentTaskStatusTests(TempProjectMixin, unittest.TestCase):
    def test_scans_pending_and_completed_sidecars(self):
        project = self.make_project()
        task = project / "drafts" / "candidates" / "scene_0001-platform-agent.agent_tasks.md"
        task.parent.mkdir(parents=True, exist_ok=True)
        task.write_text(
            """# 平台 Agent 任务说明：platform scene generation scene_0001

## Source Artifacts

- `scenes/scene_0001.yaml`

## Tasks

[AGENT_TASK: 创建或覆盖 `drafts/candidates/scene_0001-platform-agent.md`。
创建或覆盖 `drafts/candidates/scene_0001-platform-agent.json`。]
""",
            encoding="utf-8",
        )

        pending = build_agent_task_status(project)
        self.assertEqual(pending.task_count, 1)
        self.assertEqual(pending.pending_count, 1)
        payload = json.loads(pending.json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["tasks"][0]["route"], "scene-development")
        self.assertEqual(len(payload["tasks"][0]["missing_expected_paths"]), 2)

        (project / "drafts" / "candidates" / "scene_0001-platform-agent.md").write_text("done", encoding="utf-8")
        (project / "drafts" / "candidates" / "scene_0001-platform-agent.json").write_text("{}", encoding="utf-8")
        complete = build_agent_task_status(project)

        self.assertEqual(complete.complete_count, 1)
        self.assertEqual(complete.missing_expected_count, 0)

    def test_route_audit_reports_pending_sidecars(self):
        project = self.make_project()
        task = project / "branches" / "scene_0001" / "branch_manifest.agent_tasks.md"
        task.parent.mkdir(parents=True, exist_ok=True)
        task.write_text(
            """# 平台 Agent 任务说明：branch review

## Source Artifacts

- `scenes/scene_0001.yaml`

## Tasks

[AGENT_TASK: 创建或覆盖 `branches/scene_0001/branch_selection.md`。]
""",
            encoding="utf-8",
        )

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertGreater(result.blocking_count, 0)
        self.assertTrue(any(gate["key"] == "scene-sidecars-handled" and gate["status"] == "fail" for gate in payload["gates"]))

    def test_route_audit_reports_unresolved_review_notes(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        write_platform_scene_review(project, conclusion="pass_with_notes")

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertTrue(any(gate["key"] == "scene-review-notes-resolved" and gate["status"] == "fail" for gate in payload["gates"]))

        revision_dir = project / "drafts" / "revisions"
        revision_dir.mkdir(parents=True, exist_ok=True)
        (revision_dir / "scene_0001_revision_report.md").write_text("waiver recorded", encoding="utf-8")
        (revision_dir / "scene_0001_revision.json").write_text("{}", encoding="utf-8")
        resolved = build_route_audit(project, route="scene-development")
        resolved_payload = json.loads(resolved.json_path.read_text(encoding="utf-8"))

        self.assertTrue(any(gate["key"] == "scene-review-notes-resolved" and gate["status"] == "pass" for gate in resolved_payload["gates"]))

    def test_cli_exposes_task_status_commands(self):
        help_text = build_parser().format_help()
        self.assertIn("agent-task-status", help_text)
        self.assertIn("route-audit", help_text)


if __name__ == "__main__":
    unittest.main()
