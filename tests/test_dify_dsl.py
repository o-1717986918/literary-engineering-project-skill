import tempfile
import unittest
from pathlib import Path

from literary_engineering_workbench.cli import build_parser
from literary_engineering_workbench.dify_dsl import DifyDslOptions, build_dify_workflow_dsl, render_dify_workflow_dsl


class DifyDslTests(unittest.TestCase):
    def test_render_contains_workbench_http_contract(self):
        text = render_dify_workflow_dsl(
            DifyDslOptions(
                app_name="测试审稿台",
                api_base="http://host.docker.internal:8765",
            )
        )
        self.assertIn("kind: app", text)
        self.assertIn('version: "0.6.0"', text)
        self.assertIn("dependencies: []", text)
        self.assertIn("mode: workflow", text)
        self.assertIn("WORKBENCH_API_BASE", text)
        self.assertIn("WORKBENCH_API_TOKEN", text)
        self.assertIn("Authorization: Bearer", text)
        self.assertIn("type: http-request", text)
        self.assertIn("/director/chat", text)
        self.assertIn("/workflow/artifact", text)
        self.assertIn("project_root", text)
        self.assertIn("creative_direction", text)
        self.assertIn("auto_execute", text)
        self.assertIn("- default: auto", text)
        self.assertIn("- auto", text)
        self.assertIn("http-chat", text)

    def test_build_writes_dsl_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dify" / "workflow.yml"
            result = build_dify_workflow_dsl(DifyDslOptions(output=output))
            self.assertEqual(result.node_count, 4)
            self.assertEqual(result.endpoint_count, 2)
            self.assertTrue(result.output_path.exists())
            self.assertIn("Run creative director", result.output_path.read_text(encoding="utf-8"))

    def test_cli_exposes_dify_dsl_command(self):
        help_text = build_parser().format_help()
        self.assertIn("dify-dsl", help_text)


if __name__ == "__main__":
    unittest.main()
