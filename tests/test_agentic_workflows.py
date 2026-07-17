import json
import tempfile
import unittest
from pathlib import Path

from literary_engineering_workbench.agent_canon_review import review_canon_with_agent
from literary_engineering_workbench.agent_committee import run_agent_committee
from literary_engineering_workbench.agent_json_builder import plan_agent_patch
from literary_engineering_workbench.agent_scene_review import review_scene_with_agent
from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.demo_project import build_demo_project
from literary_engineering_workbench.style_compiler import StyleCompileOptions, compile_style_profile
from literary_engineering_workbench.style_prompt_agent import build_agent_style_prompt
from literary_engineering_workbench.style_prompt import (
    STYLE_PROMPT_MAX_DETAIL_CHARS,
    STYLE_PROMPT_MIN_DETAIL_CHARS,
    count_style_prompt_detail_chars,
)
from literary_engineering_workbench.workflow_runner import load_workflow_state, run_workflow

from helpers import TempProjectMixin, make_reviewed_passing_scene


class AgenticWorkflowTests(TempProjectMixin, unittest.TestCase):
    def test_agent_scene_and_canon_review_write_schema_outputs(self):
        project = self.make_project()
        draft = make_reviewed_passing_scene(project)

        scene_review = review_scene_with_agent(project, scene=Path("scenes/scene_0001.yaml"), draft=draft, provider="dry-run")
        canon_review = review_canon_with_agent(project, provider="dry-run")

        self.assertTrue(scene_review.report_path.exists())
        self.assertTrue(scene_review.json_path.exists())
        self.assertTrue(canon_review.report_path.exists())
        scene_payload = json.loads(scene_review.json_path.read_text(encoding="utf-8"))
        self.assertEqual(scene_payload["schema"], "literary-engineering-workbench/scene-review-agent/v1")
        self.assertIn(scene_payload["conclusion"], {"pass", "pass_with_notes", "revise_required", "reject"})

    def test_agent_patch_plan_and_committee(self):
        project = self.make_project()
        draft = make_reviewed_passing_scene(project)

        patch = plan_agent_patch(project, target="characters/linzhou.yaml", source=draft, provider="dry-run")
        committee = run_agent_committee(project, subject="scene-0001", source=draft, provider="dry-run")

        self.assertEqual(patch.status, "pass")
        self.assertTrue(patch.json_path.exists())
        self.assertTrue(committee.json_path.exists())
        payload = json.loads(committee.json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "literary-engineering-workbench/committee-review-agent/v1")
        self.assertEqual(committee.reviewer_count, 6)

    def test_agent_style_prompt_writes_llm_prompt(self):
        project = self.make_project()
        corpus = project / "corpus"
        corpus.mkdir()
        (corpus / "sample.txt").write_text("雨落旧城。灯影摇晃。人们沉默。", encoding="utf-8")
        compiled = compile_style_profile(
            StyleCompileOptions(
                corpus=corpus,
                output_dir=project / "style" / "demo-author",
                name="测试文风",
                author="公版示例",
                source_note="测试语料",
            )
        )

        result = build_agent_style_prompt(compiled.output_dir, provider="dry-run")

        self.assertTrue(result.output_path.exists())
        self.assertTrue(result.json_path.exists())
        prompt_text = result.output_path.read_text(encoding="utf-8")
        self.assertIn("LLM 文风约束提示词", prompt_text)
        detail_chars = count_style_prompt_detail_chars(prompt_text)
        self.assertGreaterEqual(detail_chars, STYLE_PROMPT_MIN_DETAIL_CHARS)
        self.assertLessEqual(detail_chars, STYLE_PROMPT_MAX_DETAIL_CHARS)

    def test_workflow_agent_review_records_artifacts(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)

        result = run_workflow(project, mode="scene-loop", scene=Path("scenes/scene_0001.yaml"), run_id="agent-review-run", agent_review=True, provider="dry-run")

        self.assertIn(result.status, {"completed", "completed_with_skips"})
        state = load_workflow_state(project, "agent-review-run")
        self.assertIn("agent_scene_review_task", state["artifacts"])
        self.assertIn("agent_committee_task", state["artifacts"])
        self.assertIn("[AGENT_TASK:", (project / state["artifacts"]["agent_scene_review_task"]).read_text(encoding="utf-8"))

    def test_demo_project_builds_full_agent_walkthrough(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / "demo"

        result = build_demo_project(target)

        self.assertTrue(result.report_path.exists())
        self.assertTrue(result.workflow_state and result.workflow_state.exists())
        self.assertEqual(len(result.asset_candidates), 3)
        for candidate in result.asset_candidates:
            self.assertTrue(candidate.exists())

    def test_cli_exposes_agentic_commands(self):
        help_text = build_parser().format_help()
        for command in [
            "agent-validate",
            "agent-repair",
            "agent-review-scene",
            "agent-canon-review",
            "agent-style-prompt",
            "agent-committee",
            "agent-create-character",
            "agent-create-world",
            "agent-create-outline",
            "demo-project",
        ]:
            self.assertIn(command, help_text)

    def test_cli_runs_agent_plan_patch(self):
        project = self.make_project()
        draft = make_reviewed_passing_scene(project)

        code = main(["agent-plan-patch", str(project), "--target", "characters/linzhou.yaml", "--source", str(draft), "--provider", "dry-run"])

        self.assertEqual(code, 0)
        self.assertTrue((project / "agents" / "patch_plans" / "characters-linzhou.yaml_patch_plan.agent_tasks.md").exists())


if __name__ == "__main__":
    unittest.main()
