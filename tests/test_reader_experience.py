import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from literary_engineering_workbench.agent_tasks import write_agent_completion_marker
from literary_engineering_workbench.cli import main
from literary_engineering_workbench.reader_experience import (
    build_chapter_obligation_tasks,
    ensure_reader_experience_ready,
    reader_experience_adherence_for_body,
    reader_experience_contract,
)
from literary_engineering_workbench.word_budget import build_word_budget

from helpers import TempProjectMixin, write_ready_chapter_obligation


class ReaderExperienceTests(TempProjectMixin, unittest.TestCase):
    def test_chapter_obligation_tasks_create_scaffold_and_sidecar(self):
        project = self.make_project()
        _assign_scene_to_chapter(project)
        build_word_budget(project, target_words=120000, volumes=2, genre="general")

        result = build_chapter_obligation_tasks(project, chapter_id="chapter_0001")

        self.assertTrue(result.markdown_path.exists())
        self.assertTrue(result.json_path.exists())
        self.assertTrue(result.agent_tasks_path.exists())
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "literary-engineering-workbench/chapter-obligation-contract/v1")
        self.assertEqual(payload["status"], "needs_agent")
        self.assertEqual(payload["count_unit"], "chinese_content_chars_including_chinese_punctuation")
        self.assertEqual(payload["machine_count_unit"], "machine_nonspace_chars")
        self.assertTrue(payload["reader_experience_by_scene"])
        task_text = result.agent_tasks_path.read_text(encoding="utf-8")
        self.assertIn("[AGENT_TASK:", task_text)
        self.assertIn("读者体验", task_text)

    def test_reader_experience_blocks_until_platform_agent_contract_is_complete(self):
        project = self.make_project()
        scene_path = _assign_scene_to_chapter(project)
        budget = build_word_budget(project, target_words=120000, volumes=2, genre="general")
        _mark_budget_pass(project, budget)

        blocked = reader_experience_contract(project, scene_path)
        self.assertEqual(blocked["status"], "blocked")
        with self.assertRaisesRegex(ValueError, "reader-experience contract"):
            ensure_reader_experience_ready(project, scene_path)

        write_ready_chapter_obligation(project, chapter_id="chapter_0001", scene_id="scene_0001")
        ready = ensure_reader_experience_ready(project, scene_path)
        self.assertEqual(ready["status"], "pass")
        self.assertEqual(ready["reader_experience"]["reader_question"], "林舟能否确认旧楼线索的真实来源？")

        adherence = reader_experience_adherence_for_body(project, scene_path, "林舟走进旧楼。门内有新的脚印。")
        self.assertEqual(adherence["status"], "pass")
        self.assertTrue(adherence["requires_platform_agent_semantic_review"])
        self.assertTrue(adherence["clean_body_present"])

    def test_cli_chapter_obligation_outputs_visible_agent_task_notice(self):
        project = self.make_project()
        _assign_scene_to_chapter(project)
        build_word_budget(project, target_words=120000, volumes=2, genre="general")
        out = io.StringIO()

        with redirect_stdout(out):
            code = main(["chapter-obligation", str(project), "--chapter-id", "chapter_0001"])

        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("chapter_obligation:", text)
        self.assertIn("agent_tasks_pending:", text)
        self.assertIn("receiver: platform-agent", text)
        self.assertTrue((project / "plot" / "chapter_obligations" / "chapter_0001.agent_tasks.md").exists())


def _assign_scene_to_chapter(project: Path) -> Path:
    scene_path = project / "scenes" / "scene_0001.yaml"
    scene_path.write_text(
        scene_path.read_text(encoding="utf-8").replace('chapter_id: ""', "chapter_id: chapter_0001"),
        encoding="utf-8",
    )
    return scene_path


def _mark_budget_pass(project: Path, budget) -> None:
    payload = json.loads(budget.json_path.read_text(encoding="utf-8"))
    payload["status"] = "pass"
    payload["issues"] = []
    budget.json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review = project / "reviews" / "word_budget" / "word_budget_review.md"
    review.parent.mkdir(parents=True, exist_ok=True)
    review.write_text("# Word Budget Review\n\n- 结论：`pass`\n", encoding="utf-8")
    write_agent_completion_marker(budget.agent_tasks_path, root=project, handled_by="platform-agent-test")


if __name__ == "__main__":
    unittest.main()
