import io
import json
import unittest
from contextlib import redirect_stdout

from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.prompt_registry import (
    render_prompt_preview,
    resolve_prompt_asset,
    validate_prompt_registry,
)
from literary_engineering_workbench.task_registry import issue_next_task, open_task

from helpers import TempProjectMixin


class PromptRegistryTests(TempProjectMixin, unittest.TestCase):
    def test_prompt_registry_validates_builtin_assets_and_task_ids(self):
        result = validate_prompt_registry()

        self.assertTrue(result.ok, result.errors)
        self.assertGreaterEqual(len(result.assets), 7)
        self.assertGreaterEqual(len(result.task_prompt_ids), 50)

    def test_prompt_preview_resolves_wildcard_route_asset(self):
        preview = resolve_prompt_asset("route.export-release.publish.v1")

        self.assertIsNotNone(preview.asset)
        assert preview.asset is not None
        self.assertFalse(preview.exact)
        self.assertEqual(preview.asset.match, "route.export-release.*.v1")
        text = render_prompt_preview(preview)
        self.assertIn("Export And Release Route Prompt", text)
        self.assertIn("Preserve provenance", text)

    def test_task_open_includes_resolved_prompt_asset(self):
        project = self.make_project()
        issued = issue_next_task(project, route="scene-development")

        opened = open_task(project, issued.task_id)

        text = opened.task_markdown_path.read_text(encoding="utf-8")
        self.assertIn("## Prompt Asset", text)
        self.assertIn("requested_id: `route.scene-development.context.v1`", text)
        self.assertIn("resolved_id: `route.scene-development.*.v1`", text)
        self.assertIn("Scene Development Route Prompt", text)

    def test_cli_exposes_prompt_registry_commands(self):
        help_text = build_parser().format_help()

        self.assertIn("prompt-registry-list", help_text)
        self.assertIn("prompt-registry-validate", help_text)
        self.assertIn("prompt-preview", help_text)

    def test_cli_prompt_registry_validate_json(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["prompt-registry-validate", "--json"])

        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["status"], "pass")
        self.assertGreaterEqual(data["asset_count"], 7)


if __name__ == "__main__":
    unittest.main()
