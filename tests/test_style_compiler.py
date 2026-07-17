import unittest

from literary_engineering_workbench.style_compiler import StyleCompileOptions, compile_style_profile

from helpers import TempProjectMixin


class StyleCompilerTests(TempProjectMixin, unittest.TestCase):
    def test_analyze_and_compile_style_profile(self):
        project = self.make_project()
        corpus = project / "corpus"
        corpus.mkdir()
        (corpus / "sample.txt").write_text("雨落在旧城。人们沉默地走过桥。灯影在河面上摇晃。", encoding="utf-8")

        result = compile_style_profile(
            StyleCompileOptions(
                corpus=corpus,
                output_dir=project / "style" / "demo-author",
                name="测试文风",
                author="公版示例",
                source_note="测试语料",
            )
        )

        self.assertEqual(result.source_count, 1)
        self.assertTrue(result.profile_path.exists())
        self.assertTrue(result.metrics_path.exists())
        self.assertTrue((result.evaluation_dir / "back_translation.md").exists())


if __name__ == "__main__":
    unittest.main()
