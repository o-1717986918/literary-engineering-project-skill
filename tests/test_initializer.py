import unittest

from literary_engineering_workbench.init_project import InitOptions, init_work_project

from helpers import TempProjectMixin


class InitProjectTests(TempProjectMixin, unittest.TestCase):
    def test_init_creates_expected_files(self):
        project = self.make_project()
        self.assertTrue((project / "project.yaml").exists())
        self.assertTrue((project / "AGENTS.md").exists())
        self.assertTrue((project / "agentread.yaml").exists())
        self.assertTrue((project / "scenes" / "scene_0001.yaml").exists())
        self.assertTrue((project / "workflow" / "runs" / "README.md").exists())
        self.assertTrue((project / "agents" / "runs" / "README.md").exists())
        self.assertTrue((project / "releases" / "README.md").exists())
        self.assertTrue((project / "characters" / "state_patches" / "README.md").exists())
        self.assertTrue((project / "prompts" / "scene_generation_system.md").exists())
        self.assertTrue((project / "prompts" / "scene_generation_user.md").exists())
        template = (project / "characters" / "_template.yaml").read_text(encoding="utf-8")
        self.assertIn("background_story:", template)
        self.assertIn("reveal_policy: implicit_only", template)

    def test_refuses_non_empty_directory(self):
        project = self.make_project()
        with self.assertRaises(FileExistsError):
            init_work_project(InitOptions(target=project, title="重复初始化"))


if __name__ == "__main__":
    unittest.main()
