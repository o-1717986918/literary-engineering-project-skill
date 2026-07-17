import json
import unittest

from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.style_compiler import StyleCompileOptions, compile_style_profile
from literary_engineering_workbench.style_prompt import build_style_prompt
from literary_engineering_workbench.style_prompt_eval import run_style_prompt_eval

from helpers import TempProjectMixin


class StylePromptTests(TempProjectMixin, unittest.TestCase):
    def test_build_style_prompt_from_compiled_profile(self):
        project = self.make_project()
        profile_dir = self._compile_profile(project)

        result = build_style_prompt(profile_dir, provider="dry-run")

        self.assertTrue(result.output_path.exists())
        self.assertTrue(result.manifest_path.exists())
        text = result.output_path.read_text(encoding="utf-8")
        self.assertIn("LLM 文风约束提示词", text)
        self.assertIn("## 核心风格机制", text)
        self.assertIn("## 输出自检", text)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["provider"], "dry-run")
        self.assertEqual(manifest["messages"][0]["role"], "system")
        self.assertIn("供另一个 LLM 写作时直接使用", manifest["messages"][0]["content"])

    def test_cli_exposes_and_runs_style_prompt(self):
        project = self.make_project()
        profile_dir = self._compile_profile(project)

        self.assertIn("style-prompt", build_parser().format_help())
        code = main(["style-prompt", str(profile_dir), "--provider", "dry-run"])

        self.assertEqual(code, 0)
        self.assertTrue((profile_dir / "style_prompt.agent_tasks.md").exists())

    def test_style_prompt_eval_generates_candidate_and_scores_effectiveness(self):
        project = self.make_project()
        profile_dir = self._compile_profile(project)
        build_style_prompt(profile_dir, provider="dry-run")
        reference = project / "reference.txt"
        reference.write_text(
            "雨落在旧城的石桥上。林舟沿着河岸慢慢走，灯影在水里碎成一片。",
            encoding="utf-8",
        )
        task_input = project / "english.txt"
        task_input.write_text("Rain falls on the old city bridge. Lin Zhou walks along the river.", encoding="utf-8")

        result = run_style_prompt_eval(
            profile_dir,
            reference=reference,
            task_input=task_input,
            mode="back-translation",
            provider="dry-run",
        )

        self.assertTrue(result.candidate_path.exists())
        self.assertTrue(result.prompt_manifest_path.exists())
        self.assertTrue(result.report_path.exists())
        self.assertTrue(result.metrics_path.exists())
        self.assertIn("雨落在旧城", result.candidate_path.read_text(encoding="utf-8"))
        manifest = json.loads(result.prompt_manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["mode"], "back-translation")
        self.assertIn("style_prompt.md", manifest["style_prompt"])

    def test_cli_exposes_and_runs_style_prompt_eval(self):
        project = self.make_project()
        profile_dir = self._compile_profile(project)
        build_style_prompt(profile_dir, provider="dry-run")
        reference = project / "reference.txt"
        reference.write_text("雨落旧城。灯影摇晃。人们沉默。", encoding="utf-8")
        task_input = project / "english.txt"
        task_input.write_text("Rain falls in the old city.", encoding="utf-8")

        self.assertIn("style-prompt-eval", build_parser().format_help())
        code = main(
            [
                "style-prompt-eval",
                str(profile_dir),
                "--reference",
                str(reference),
                "--input",
                str(task_input),
                "--provider",
                "dry-run",
            ]
        )

        self.assertEqual(code, 0)
        self.assertTrue((profile_dir / "evaluation_results" / "back-translation").exists())
        self.assertTrue((profile_dir / "evaluation_results" / "back-translation" / "platform_agent_candidate.agent_tasks.md").exists())

    def _compile_profile(self, project):
        corpus = project / "corpus"
        corpus.mkdir()
        (corpus / "sample.txt").write_text(
            "雨落在旧城。人们沉默地走过桥。灯影在河面上摇晃。",
            encoding="utf-8",
        )
        return compile_style_profile(
            StyleCompileOptions(
                corpus=corpus,
                output_dir=project / "style" / "demo-author",
                name="测试文风",
                author="公版示例",
                source_note="测试语料",
            )
        ).output_dir


if __name__ == "__main__":
    unittest.main()
