import unittest
from pathlib import Path

from literary_engineering_workbench.anti_ai_style import lint_ai_style
from literary_engineering_workbench.punctuation_standard import lint_punctuation
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

    def test_punctuation_standard_flags_corner_quote_mixing(self):
        project = self.make_project()
        draft = make_passing_scene(project)
        text = draft.read_text(encoding="utf-8")
        text = text.replace(
            "林舟站在旧楼门口，听见楼道深处的电流声断断续续。",
            "林舟站在旧楼门口，听见楼道深处有人说：「别再往前走。」",
        )
        draft.write_text(text, encoding="utf-8")

        review = review_scene_draft(project, draft)
        report = review.report_path.read_text(encoding="utf-8")

        self.assertEqual(review.conclusion, "revise_required")
        self.assertIn("corner-quotes-in-horizontal-prose", report)
        self.assertIn("横排文学正文直接引语", report)

    def test_punctuation_lint_flags_literary_rhythm_problems(self):
        text = (
            "林舟停下。雨声贴着窗。灯影落在墙上。门缝慢慢打开。风从楼道灌进来。"
            "信纸滑到地上。没人说话。电流声又响。钥匙在掌心发冷。脚步停在门外。"
            "但是，他没有立刻回头。然而，灯先灭了。于是，他把信塞进口袋。然后，他听见门锁轻响。"
            "她说——这不是第一次——也不会是最后一次——你最好现在就走——别问原因。"
        )

        rules = {issue.rule for issue in lint_punctuation(text)}

        self.assertIn("staccato-period-overuse", rules)
        self.assertIn("mechanical-transition-overuse", rules)
        self.assertIn("dash-overuse", rules)

    def test_review_flags_ai_trace_patterns(self):
        project = self.make_project()
        draft = make_passing_scene(project)
        text = draft.read_text(encoding="utf-8")
        ai_body = (
            "林舟站在门口。这不是一次普通的停电，而是一场被隐藏的试探。"
            "他知道自己不是为了答案而来，而是为了真相本身。"
            "她明白这不是命运的偶然，而是某种意义上的回声。"
            "他意识到这一刻不是结束，而是开始。"
        )
        text = text.replace(
            "林舟站在旧楼门口，听见楼道深处的电流声断断续续。",
            ai_body,
        )
        draft.write_text(text, encoding="utf-8")

        review = review_scene_draft(project, draft)
        report = review.report_path.read_text(encoding="utf-8")

        self.assertEqual(review.conclusion, "revise_required")
        self.assertIn("AI Trace Reduction Test", report)
        self.assertIn("机械对照/否定纠偏句式", report)
        self.assertIn("不得用脚本", report)

    def test_ai_trace_flags_dash_contrast_without_prescribing_regex_cleanup(self):
        text = "不是C营的——是那个E营的年轻人，他把袖章藏在雨衣里面。"

        issues = lint_ai_style(text)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "mechanical-contrast-frame")
        self.assertEqual(issues[0].severity, "low")
        self.assertIn("可保留", issues[0].message)
        self.assertIn("不得用脚本", issues[0].message)


if __name__ == "__main__":
    unittest.main()
