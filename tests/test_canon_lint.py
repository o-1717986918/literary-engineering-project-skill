import json
import unittest

from literary_engineering_workbench.canon_lint import build_canon_lint
from literary_engineering_workbench.cli import build_parser

from helpers import TempProjectMixin, add_character, make_passing_scene


class CanonLintTests(TempProjectMixin, unittest.TestCase):
    def test_initial_project_generates_warning_report(self):
        project = self.make_project()
        result = build_canon_lint(project)
        self.assertTrue(result.report_path.exists())
        self.assertTrue(result.json_path.exists())
        self.assertEqual(result.status, "pass_with_warnings")
        self.assertEqual(result.blocking_count, 0)

        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "literary-engineering-workbench/canon-lint/v0.1")
        self.assertGreater(payload["summary"]["warning_count"], 0)
        self.assertIn("Canon Lint Report", result.report_path.read_text(encoding="utf-8"))

    def test_unknown_scene_participant_blocks(self):
        project = self.make_project()
        add_character(project)
        scene = project / "scenes" / "scene_0001.yaml"
        text = scene.read_text(encoding="utf-8")
        text = text.replace('scene_id: ""', 'scene_id: "scene_0001"')
        text = text.replace('chapter_id: ""', 'chapter_id: "chapter_0001"')
        text = text.replace('location: ""', 'location: "旧楼"')
        text = text.replace("participants: []", "participants: [ghost]")
        scene.write_text(text, encoding="utf-8")

        result = build_canon_lint(project)
        self.assertEqual(result.status, "blocked")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        checks = {issue["check_id"] for issue in payload["issues"]}
        self.assertIn("scene-participant-unknown", checks)

    def test_draft_writeback_candidates_are_reported(self):
        project = self.make_project()
        add_character(project)
        make_passing_scene(project)
        result = build_canon_lint(project)
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        checks = [issue["check_id"] for issue in payload["issues"]]
        self.assertIn("draft-unconfirmed-candidate", checks)
        self.assertNotIn("character-background-story-missing", checks)

    def test_missing_character_background_story_warns(self):
        project = self.make_project()
        add_character(project)
        char_path = project / "characters" / "linzhou.yaml"
        text = char_path.read_text(encoding="utf-8")
        text = text.split("background_story:", 1)[0] + "speech_style:\n  rhythm: 短句，克制，少解释。\n"
        char_path.write_text(text, encoding="utf-8")

        result = build_canon_lint(project)
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        checks = [issue["check_id"] for issue in payload["issues"]]
        self.assertIn("character-background-story-missing", checks)

    def test_cli_exposes_canon_lint(self):
        self.assertIn("canon-lint", build_parser().format_help())


if __name__ == "__main__":
    unittest.main()
