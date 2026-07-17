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

    def test_punctuation_standard_gate_flags_mixed_punctuation(self):
        project = self.make_project()
        draft = make_passing_scene(project)
        text = draft.read_text(encoding="utf-8")
        text = text.replace("林舟站在旧楼门口，听见楼道深处的电流声断断续续。", "林舟站在旧楼门口,听见楼道深处的电流声断断续续...")
        draft.write_text(text, encoding="utf-8")

        review = review_scene_draft(project, draft)

        self.assertEqual(review.conclusion, "revise_required")
        report = review.report_path.read_text(encoding="utf-8")
        self.assertIn("Punctuation Standard Test", report)
        self.assertIn("中文句子中混入英文标点", report)


if __name__ == "__main__":
    unittest.main()
