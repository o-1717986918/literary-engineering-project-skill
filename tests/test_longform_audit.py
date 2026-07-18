import json
import re
import unittest

from literary_engineering_workbench.draft_text import count_delivery_chars
from literary_engineering_workbench.longform_audit import build_longform_audit

from helpers import TempProjectMixin, add_character, make_reviewed_passing_scene


class LongformAuditTests(TempProjectMixin, unittest.TestCase):
    def test_builds_longform_audit_and_graph(self):
        project = self.make_project()
        add_character(project)
        make_reviewed_passing_scene(project)
        result = build_longform_audit(project, target_length=1000)
        self.assertTrue(result.markdown_path.exists())
        self.assertTrue(result.json_path.exists())
        self.assertTrue(result.graph_path.exists())
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        self.assertIn("nodes", graph)

    def test_longform_audit_counts_clean_delivery_body_only(self):
        project = self.make_project()
        add_character(project)
        draft = make_reviewed_passing_scene(project)
        text = draft.read_text(encoding="utf-8")
        polluted = re.sub(
            r"(?s)## 正文草稿\s*.*?\n## 状态变化",
            "## 正文草稿\n\n正文一句。\n\n场景编号：scene_0001\n\n## 状态变化候选\n\n- canon 信息不应统计。\n\n## 状态变化",
            text,
        )
        draft.write_text(polluted, encoding="utf-8")

        result = build_longform_audit(project, target_length=1000)
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["scenes"][0]["draft_chars"], count_delivery_chars("正文一句。"))
        self.assertEqual(payload["summary"]["draft_chars"], count_delivery_chars("正文一句。"))

    def test_missing_project_fails(self):
        project = self.make_project()
        with self.assertRaises(FileNotFoundError):
            build_longform_audit(project / "missing")


if __name__ == "__main__":
    unittest.main()
