import io
import json
import unittest
from contextlib import redirect_stdout

from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.protocol import (
    list_protocol_routes,
    render_protocol,
    resolve_protocol_route,
)


class ProtocolTests(unittest.TestCase):
    def test_route_aliases_resolve(self):
        self.assertEqual(resolve_protocol_route("scene-development").key, "scene-development")
        self.assertEqual(resolve_protocol_route("scene_development").key, "scene-development")
        self.assertEqual(resolve_protocol_route("export_and_release").key, "export-and-release")

    def test_render_protocol_contains_handoffs_and_gates(self):
        text = render_protocol(resolve_protocol_route("scene-development"))
        self.assertIn("Platform Agent Handoffs", text)
        self.assertIn(".agent_tasks.md", text)
        self.assertIn("Completion Gates", text)
        self.assertIn("Chinese punctuation", text)
        self.assertIn("Probe documented commands", text)
        self.assertIn("agent-review-scene is a sidecar generator", text)
        self.assertIn("scene_review.v1", text)

    def test_cli_exposes_protocol_command(self):
        help_text = build_parser().format_help()
        self.assertIn("protocol", help_text)

    def test_cli_lists_protocol_routes(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["protocol"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("Available Protocol Routes", text)
        self.assertIn("scene-development", text)

    def test_cli_outputs_protocol_json(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["protocol", "style_engineering", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["key"], "style-engineering")
        self.assertTrue(data["completion_gates"])

    def test_route_table_has_required_routes(self):
        keys = {route.key for route in list_protocol_routes()}
        self.assertTrue(
            {
                "project-director",
                "work-project-initialization",
                "style-engineering",
                "source-ingest",
                "longform-planning",
                "character-and-world-assets",
                "scene-development",
                "review-and-audit",
                "export-and-release",
                "optional-cli",
            }.issubset(keys)
        )


if __name__ == "__main__":
    unittest.main()
