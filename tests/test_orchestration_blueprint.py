import unittest

from literary_engineering_workbench.orchestration_blueprint import build_orchestration_blueprint

from helpers import TempProjectMixin


class OrchestrationBlueprintTests(TempProjectMixin, unittest.TestCase):
    def test_builds_platform_blueprint(self):
        project = self.make_project()
        result = build_orchestration_blueprint(project)
        self.assertTrue(result.markdown_path.exists())
        self.assertTrue(result.json_path.exists())
        self.assertGreaterEqual(result.platform_count, 3)
        self.assertGreater(result.node_count, 0)

    def test_rejects_unknown_platform(self):
        project = self.make_project()
        with self.assertRaises(ValueError):
            build_orchestration_blueprint(project, platforms=["unknown-platform"])


if __name__ == "__main__":
    unittest.main()
