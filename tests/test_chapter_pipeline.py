import unittest
from pathlib import Path

from literary_engineering_workbench.chapter_pipeline import build_chapter_workspace

from helpers import TempProjectMixin, make_reviewed_passing_scene


class ChapterPipelineTests(TempProjectMixin, unittest.TestCase):
    def test_builds_chapter_workspace_from_scene_artifacts(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        result = build_chapter_workspace(project, chapter_id="chapter_0001")
        self.assertEqual(result.scene_count, 1)
        self.assertEqual(result.ready_count, 1)
        self.assertEqual(result.blocked_count, 0)
        self.assertTrue(result.markdown_path.exists())
        self.assertTrue(result.json_path.exists())

    def test_missing_scene_path_fails(self):
        project = self.make_project()
        with self.assertRaises(FileNotFoundError):
            build_chapter_workspace(project, scenes=[Path("scenes/missing.yaml")])


if __name__ == "__main__":
    unittest.main()
