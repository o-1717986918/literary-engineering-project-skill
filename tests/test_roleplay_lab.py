import unittest
from pathlib import Path

from literary_engineering_workbench.roleplay_lab import build_roleplay_simulation

from helpers import TempProjectMixin, add_character


class RoleplayLabTests(TempProjectMixin, unittest.TestCase):
    def test_build_roleplay_simulation(self):
        project = self.make_project()
        add_character(project)
        result = build_roleplay_simulation(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True)
        self.assertEqual(result.character_count, 1)
        self.assertTrue(result.output_path.exists())
        text = result.output_path.read_text(encoding="utf-8")
        self.assertIn("Character Agent", text)
        self.assertIn("内部背景故事", text)
        self.assertIn("不得直白输出", text)
        self.assertNotIn("[AGENT_TASK:", text)

    def test_agent_mode_writes_executable_task_directives(self):
        project = self.make_project()
        add_character(project)
        result = build_roleplay_simulation(
            project,
            scene=Path("scenes/scene_0001.yaml"),
            rebuild_context=True,
            agent_mode=True,
        )

        text = result.output_path.read_text(encoding="utf-8")
        self.assertNotIn("[AGENT_TASK:", text)
        self.assertIsNotNone(result.agent_tasks_path)
        assert result.agent_tasks_path is not None
        tasks = result.agent_tasks_path.read_text(encoding="utf-8")
        self.assertIn("[AGENT_TASK:", tasks)
        self.assertIn("读取 `characters/linzhou.yaml`", tasks)
        self.assertIn("World Agent", tasks)
        self.assertIn("Director Agent", tasks)
        self.assertIn("不是外部 LLM prompt", tasks)
        self.assertIn("平台 Agent 执行门禁", text)
        self.assertIn("读取回执", text)
        self.assertIn("写回边界", text)


if __name__ == "__main__":
    unittest.main()
