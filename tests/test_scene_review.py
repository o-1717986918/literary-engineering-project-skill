import unittest
from pathlib import Path

from literary_engineering_workbench.review_ci import review_scene_draft
from literary_engineering_workbench.scene_draft import build_scene_draft

from helpers import TempProjectMixin, make_passing_scene


class SceneReviewTests(TempProjectMixin, unittest.TestCase):
    def test_draft_workspace_and_review(self):
        project = self.make_project()
        draft = make_passing_scene(project)
        review = review_scene_draft(project, draft)
        self.assertEqual(review.conclusion, "pass")
        self.assertEqual(review.issue_count, 0)
        self.assertTrue(review.report_path.exists())

    def test_empty_draft_is_rejected(self):
        project = self.make_project()
        draft = build_scene_draft(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True).draft_path
        self.assertIn("背景故事没有被直白交代", draft.read_text(encoding="utf-8"))
        review = review_scene_draft(project, draft)
        self.assertEqual(review.conclusion, "reject")
        self.assertGreater(review.issue_count, 0)


if __name__ == "__main__":
    unittest.main()
