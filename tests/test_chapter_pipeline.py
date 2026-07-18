import json
import re
import unittest
from pathlib import Path

from literary_engineering_workbench.chapter_pipeline import build_chapter_workspace
from literary_engineering_workbench.draft_text import count_delivery_chars

from helpers import TempProjectMixin, make_reviewed_passing_scene, make_static_reviewed_passing_scene


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

    def test_chapter_counts_clean_delivery_body_only(self):
        project = self.make_project()
        draft = make_reviewed_passing_scene(project)
        text = draft.read_text(encoding="utf-8")
        polluted = re.sub(
            r"(?s)## 正文草稿\s*.*?\n## 状态变化",
            "## 正文草稿\n\n正文一句。\n\nscene_id: scene_0001\n\n## 状态变化候选\n\n- canon 信息不应统计。\n\n## 状态变化",
            text,
        )
        draft.write_text(polluted, encoding="utf-8")

        result = build_chapter_workspace(project, chapter_id="chapter_0001")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["scenes"][0]["draft_chars"], count_delivery_chars("正文一句。"))
        self.assertEqual(payload["summary"]["draft_chars"], count_delivery_chars("正文一句。"))

    def test_static_review_without_platform_agent_review_is_not_ready(self):
        project = self.make_project()
        make_static_reviewed_passing_scene(project)
        result = build_chapter_workspace(project, chapter_id="chapter_0001", agent_review=True)
        self.assertEqual(result.ready_count, 0)
        self.assertEqual(result.blocked_count, 1)
        self.assertTrue((project / "reviews" / "agent" / "scene_0001_scene_review.agent_tasks.md").exists())

    def test_missing_scene_path_fails(self):
        project = self.make_project()
        with self.assertRaises(FileNotFoundError):
            build_chapter_workspace(project, scenes=[Path("scenes/missing.yaml")])


if __name__ == "__main__":
    unittest.main()
