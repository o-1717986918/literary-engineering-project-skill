import json
import unittest

from literary_engineering_workbench.cli import build_parser
from literary_engineering_workbench.style_compiler import StyleCompileOptions, compile_style_profile
from literary_engineering_workbench.style_evaluator import StyleEvalOptions, evaluate_style

from helpers import TempProjectMixin


class StyleEvaluatorTests(TempProjectMixin, unittest.TestCase):
    def test_evaluate_style_candidate(self):
        project = self.make_project()
        profile_dir, reference, candidate = self._make_style_eval_fixture(project)

        result = evaluate_style(
            StyleEvalOptions(
                profile_dir=profile_dir,
                reference=reference,
                candidate=candidate,
                mode="back-translation",
            )
        )

        self.assertTrue(result.report_path.exists())
        self.assertTrue(result.metrics_path.exists())
        payload = json.loads(result.metrics_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["mode"], "back-translation")
        self.assertIn("overall_score", payload)
        self.assertIn("rhythm", payload["scores"])
        self.assertIn("Style Evaluation", result.report_path.read_text(encoding="utf-8"))

    def test_copy_risk_is_flagged(self):
        project = self.make_project()
        profile_dir, reference, candidate = self._make_style_eval_fixture(project, copied=True)

        result = evaluate_style(
            StyleEvalOptions(
                profile_dir=profile_dir,
                reference=reference,
                candidate=candidate,
                mode="outline-expansion",
            )
        )

        payload = json.loads(result.metrics_path.read_text(encoding="utf-8"))
        self.assertIn(payload["risk_level"], {"medium_copy_risk", "high_copy_risk"})
        self.assertGreater(payload["scores"]["originality_boundary"]["overlap_windows"], 0)

    def test_cli_exposes_style_eval(self):
        self.assertIn("style-eval", build_parser().format_help())

    def _make_style_eval_fixture(self, project, copied=False):
        corpus = project / "corpus"
        corpus.mkdir()
        reference_text = (
            "雨落在旧城的石桥上。林舟沿着河岸慢慢走，灯影在水里碎成一片。"
            "他想起那页残缺档案，知道沉默并不等于安全。"
        )
        (corpus / "sample.txt").write_text(reference_text, encoding="utf-8")
        compiled = compile_style_profile(
            StyleCompileOptions(
                corpus=corpus,
                output_dir=project / "style" / "demo-author",
                name="测试文风",
                author="公版示例",
                source_note="测试语料",
            )
        )
        reference = project / "reference.txt"
        reference.write_text(reference_text, encoding="utf-8")
        candidate = project / "candidate.txt"
        candidate.write_text(
            reference_text if copied else (
                "夜雨落进旧城。林舟在桥边停下，水面映着摇晃的灯。"
                "他记得那份残缺记录，也明白安静有时只是危险换了说法。"
            ),
            encoding="utf-8",
        )
        return compiled.output_dir, reference, candidate


if __name__ == "__main__":
    unittest.main()
