import json
import unittest

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

    def test_missing_project_fails(self):
        project = self.make_project()
        with self.assertRaises(FileNotFoundError):
            build_longform_audit(project / "missing")


if __name__ == "__main__":
    unittest.main()
