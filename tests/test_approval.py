import json
import unittest

from literary_engineering_workbench.approval import build_approval_summary, record_workflow_approval
from literary_engineering_workbench.cli import build_parser

from helpers import TempProjectMixin


class ApprovalTests(TempProjectMixin, unittest.TestCase):
    def test_revise_records_index_and_followup_task(self):
        project = self.make_project()
        result = record_workflow_approval(project, "run-demo", "revise", actor="tester", notes="补足人物动机。")
        self.assertTrue(result.approval_path.exists())
        self.assertTrue(result.index_path.exists())
        self.assertIsNotNone(result.task_path)
        self.assertTrue(result.task_path.exists())

        index_record = json.loads(result.index_path.read_text(encoding="utf-8").strip())
        self.assertEqual(index_record["decision"], "revise")
        self.assertIn("workflow/tasks/", index_record["task_path"])
        self.assertIn("补足人物动机", result.task_path.read_text(encoding="utf-8"))

    def test_approve_does_not_create_followup_task(self):
        project = self.make_project()
        result = record_workflow_approval(project, "run-ok", "approve", actor="tester", notes="可进入候选。")
        self.assertIsNone(result.task_path)
        record = json.loads(result.index_path.read_text(encoding="utf-8").strip())
        self.assertEqual(record["task_path"], "")

    def test_build_approval_summary(self):
        project = self.make_project()
        record_workflow_approval(project, "run-demo", "reject", actor="tester", notes="重做。")
        result = build_approval_summary(project)
        self.assertEqual(result.record_count, 1)
        self.assertEqual(result.task_count, 1)
        self.assertTrue(result.output_path.exists())
        self.assertIn("run-demo", result.output_path.read_text(encoding="utf-8"))

    def test_cli_exposes_approval_summary(self):
        self.assertIn("approval-summary", build_parser().format_help())


if __name__ == "__main__":
    unittest.main()
