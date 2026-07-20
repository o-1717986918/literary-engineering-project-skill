import unittest

from literary_engineering_workbench.task_registry import complete_task, issue_next_task, open_task
from literary_engineering_workbench.workflow_activity import build_task_package_summary, build_workflow_activity

from helpers import TempProjectMixin


class WorkflowActivityTests(TempProjectMixin, unittest.TestCase):
    def test_activity_highlights_issued_opened_and_blocked_task(self):
        project = self.make_project()
        issued = issue_next_task(project, route="scene-development")

        activity = build_workflow_activity(project)

        self.assertEqual(activity["schema"], "literary-engineering-workbench/workflow-activity/v0.1")
        self.assertEqual(activity["active_task"]["task_id"], issued.task_id)
        self.assertEqual(activity["active_task"]["stage"], "issued")
        self.assertEqual(activity["active_task"]["waiting_for"], "agent")
        self.assertTrue(any(lane["route"] == "scene-development" and lane["active"] for lane in activity["route_lanes"]))
        self.assertTrue(any(event["event_type"] == "task_issued" for event in activity["timeline"]))

        open_task(project, issued.task_id)
        activity = build_workflow_activity(project)
        self.assertEqual(activity["active_task"]["task_id"], issued.task_id)
        self.assertEqual(activity["active_task"]["stage"], "waiting_agent")

        with self.assertRaises(FileNotFoundError):
            complete_task(project, issued.task_id)
        activity = build_workflow_activity(project)
        self.assertEqual(activity["active_task"]["task_id"], issued.task_id)
        self.assertEqual(activity["active_task"]["stage"], "blocked")
        self.assertIn("missing expected outputs", activity["active_task"]["suggested_action"])

    def test_task_package_summary_wraps_task_without_raw_json_first(self):
        project = self.make_project()
        issued = issue_next_task(project, route="scene-development")

        package = build_task_package_summary(project, issued.task_id)

        self.assertEqual(package["schema"], "literary-engineering-workbench/task-package-summary/v0.1")
        self.assertEqual(package["task"]["task_id"], issued.task_id)
        self.assertIn("purpose", package["sections"])
        self.assertIn("expected_outputs", package["sections"])
        self.assertIn("raw_evidence", package)
        self.assertIn("task_markdown", package["raw_evidence"])


if __name__ == "__main__":
    unittest.main()
