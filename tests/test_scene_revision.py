import json
import unittest
from pathlib import Path

from literary_engineering_workbench.cli import build_parser
from literary_engineering_workbench.scene_revision import build_scene_revision_task

from helpers import TempProjectMixin, make_reviewed_passing_scene, write_platform_scene_review


class SceneRevisionTests(TempProjectMixin, unittest.TestCase):
    def test_builds_platform_agent_scene_revision_task(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        write_platform_scene_review(project, conclusion="pass_with_notes")

        result = build_scene_revision_task(project, scene=Path("scenes/scene_0001.yaml"))

        self.assertTrue(result.task_path.exists())
        self.assertTrue(result.prompt_manifest_path.exists())
        self.assertFalse(result.expected_candidate_path.exists())
        text = result.task_path.read_text(encoding="utf-8")
        self.assertIn("[AGENT_TASK:", text)
        self.assertIn("reading receipt", text)
        self.assertIn("修订候选", text)
        self.assertIn("反规避", text)
        self.assertIn("负担证明", text)
        self.assertIn("pass_with_notes", result.prompt_manifest_path.read_text(encoding="utf-8"))

        manifest = json.loads(result.prompt_manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["scene_id"], "scene_0001")
        self.assertEqual(manifest["revision_inputs"]["agent_review_conclusion"], "pass_with_notes")
        self.assertEqual(manifest["revision_inputs"]["style_adherence"]["status"], "not_applicable")
        self.assertIn("word_budget", manifest["generation_standards"])
        self.assertIn("style_lint_before", manifest["generation_standards"])
        self.assertIn("anti_evasion", manifest["generation_standards"])

    def test_cli_exposes_revise_scene(self):
        self.assertIn("revise-scene", build_parser().format_help())


if __name__ == "__main__":
    unittest.main()
