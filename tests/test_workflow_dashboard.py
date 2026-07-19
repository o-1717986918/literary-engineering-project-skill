from contextlib import redirect_stdout
import io
import json
import unittest

from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.task_registry import issue_next_task
from literary_engineering_workbench.workflow_dashboard import build_workflow_dashboard

from helpers import TempProjectMixin


class WorkflowDashboardTests(TempProjectMixin, unittest.TestCase):
    def test_dashboard_builds_cross_route_outputs(self):
        project = self.make_project()
        issue_next_task(project, route="scene-development")

        result = build_workflow_dashboard(project)

        self.assertEqual(result.route_count, 7)
        self.assertTrue(result.json_path.exists())
        self.assertTrue(result.markdown_path.exists())
        self.assertTrue(result.html_path.exists())

        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "literary-engineering-workbench/workflow-dashboard/v0.1")
        self.assertEqual(payload["summary"]["route_count"], 7)
        self.assertGreaterEqual(payload["summary"]["blocking_count"], 1)
        self.assertGreaterEqual(payload["summary"]["next_action_count"], 1)
        self.assertIn("scene-development", {item["route"] for item in payload["route_audits"]})
        self.assertTrue(any(item["event_type"] == "task_issued" for item in payload["recent_events"]))

        html = result.html_path.read_text(encoding="utf-8")
        self.assertIn("Workflow Dashboard", html)
        self.assertIn("workflow-dashboard-data", html)
        self.assertIn("只读总控面板", html)

    def test_cli_exposes_and_runs_workflow_dashboard(self):
        project = self.make_project()
        self.assertIn("workflow-dashboard", build_parser().format_help())

        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["workflow-dashboard", str(project)])

        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("workflow_dashboard:", text)
        self.assertIn("html:", text)
        self.assertTrue((project / "workflow" / "dashboard" / "workflow_dashboard.json").exists())
        self.assertTrue((project / "workflow" / "dashboard" / "workflow_dashboard.html").exists())


if __name__ == "__main__":
    unittest.main()
