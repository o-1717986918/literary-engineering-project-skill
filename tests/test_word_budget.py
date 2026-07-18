import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from literary_engineering_workbench.branch_lab import build_branch_simulation
from literary_engineering_workbench.cli import main
from literary_engineering_workbench.generation_provider import generate_scene_candidate
from literary_engineering_workbench.longform_audit import build_longform_audit
from literary_engineering_workbench.scene_composer import build_scene_composition
from literary_engineering_workbench.word_budget import build_word_budget

from helpers import TempProjectMixin, make_reviewed_passing_scene


class WordBudgetTests(TempProjectMixin, unittest.TestCase):
    def test_build_word_budget_creates_budget_and_agent_task(self):
        project = self.make_project()

        result = build_word_budget(
            project,
            target_words=500000,
            volumes=5,
            genre="mystery",
            time_span="三年",
        )

        self.assertTrue(result.markdown_path.exists())
        self.assertTrue(result.json_path.exists())
        self.assertTrue(result.agent_tasks_path.exists())
        self.assertTrue(result.scene_inventory_tasks_path.exists())
        self.assertEqual(result.target_words, 500000)
        self.assertEqual(result.volume_count, 5)
        self.assertGreater(result.chapter_count, 80)
        self.assertGreater(result.scene_count, 250)
        self.assertEqual(result.status, "needs_expansion")

        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["target"]["target_words"], 500000)
        self.assertEqual(payload["totals"]["target_words"], 500000)
        self.assertEqual(len(payload["volume_budgets"]), 5)
        self.assertGreater(len(payload["chapter_budgets"]), 80)
        self.assertIn("scene_inventory_binding", payload)
        self.assertGreater(payload["scene_inventory_binding"]["missing_scene_count"], 200)

        tasks = result.agent_tasks_path.read_text(encoding="utf-8")
        self.assertIn("[AGENT_TASK:", tasks)
        self.assertIn("plot/candidates/outlines/word_budget_expansion.md", tasks)
        self.assertIn("剧情库存", tasks)
        scene_tasks = result.scene_inventory_tasks_path.read_text(encoding="utf-8")
        self.assertIn("word_budget_scene_inventory.md", scene_tasks)
        self.assertIn("扩场景", scene_tasks)

    def test_cli_word_budget_alias(self):
        project = self.make_project()
        out = io.StringIO()

        with redirect_stdout(out):
            code = main(
                [
                    "longform-budget",
                    str(project),
                    "--target-words",
                    "120000",
                    "--volumes",
                    "2",
                    "--genre",
                    "urban",
                ]
            )

        self.assertEqual(code, 0)
        self.assertIn("receiver: platform-agent", out.getvalue())
        self.assertIn("scene_inventory_tasks", out.getvalue())
        self.assertTrue((project / "plot" / "word_budget" / "word_budget.json").exists())
        self.assertTrue((project / "plot" / "word_budget" / "word_budget.agent_tasks.md").exists())
        self.assertTrue((project / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md").exists())

    def test_prompt_manifest_includes_word_budget_standard(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        _prepare_generation_ready(project)
        build_word_budget(project, target_words=120000, volumes=2, genre="general")

        result = generate_scene_candidate(
            project,
            scene=Path("scenes/scene_0001.yaml"),
            rebuild_context=True,
            provider="dry-run",
        )
        manifest = json.loads(result.prompt_manifest_path.read_text(encoding="utf-8"))

        self.assertTrue(manifest["generation_standards"]["word_budget_loaded"])
        self.assertEqual(manifest["generation_standards"]["word_budget_path"], "plot/word_budget/word_budget.json")
        self.assertIn("长篇字数预算标准", manifest["messages"][1]["content"])
        self.assertIn("plot/word_budget/word_budget.json", {item["path"] for item in manifest["sources"]})

    def test_longform_audit_reports_missing_and_underbuilt_budget(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)

        missing_budget = build_longform_audit(project, target_length=200000)
        missing_payload = json.loads(missing_budget.json_path.read_text(encoding="utf-8"))
        self.assertTrue(any(issue["category"] == "word_budget" for issue in missing_payload["issues"]))

        build_word_budget(project, target_words=200000, volumes=3, genre="mystery")
        audited = build_longform_audit(project, target_length=200000)
        payload = json.loads(audited.json_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["summary"]["word_budget_status"], "needs_expansion")
        self.assertGreater(payload["summary"]["word_budget_scene_count"], 0)
        self.assertTrue(any(issue["category"] == "scene_inventory" for issue in payload["issues"]))


def _prepare_generation_ready(project: Path):
    branch = build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=3)
    _select_branch(branch.selection_path, branch.recommended_branch)
    build_scene_composition(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True)


def _select_branch(path: Path, branch_id: str):
    path.write_text(
        f"""# Branch Selection：scene_0001

## 人工决定

- decision: selected
- selected_branch: {branch_id}
- reviewer: platform-agent-test
- selected_at: 2026-01-01T00:00:00Z
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
