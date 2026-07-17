import json
import unittest
from pathlib import Path

from literary_engineering_workbench.character_state_evolver import build_character_state_patch
from literary_engineering_workbench.cli import build_parser, main

from helpers import TempProjectMixin, add_character, make_passing_scene


class CharacterStateEvolverTests(TempProjectMixin, unittest.TestCase):
    def test_build_character_state_patch_from_reviewable_draft(self):
        project = self.make_project()
        character_file = add_character(project)
        draft = make_passing_scene(project)
        before = character_file.read_text(encoding="utf-8")

        result = build_character_state_patch(project, scene=Path("scenes/scene_0001.yaml"), source=draft)

        self.assertEqual(result.scene_id, "scene_0001")
        self.assertEqual(result.character_count, 1)
        self.assertEqual(result.unresolved_count, 0)
        self.assertTrue(result.output_path.exists())
        self.assertTrue(result.json_path.exists())
        self.assertEqual(character_file.read_text(encoding="utf-8"), before)

        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "pending_human_approval")
        patch = payload["characters"][0]
        self.assertEqual(patch["character_id"], "linzhou")
        self.assertIn("主动调查", "\n".join(patch["proposed_updates"]["arc"]["candidate_changes"]))
        self.assertIn("隐瞒", "\n".join(patch["proposed_updates"]["relationships"]["candidate_changes"]))
        report = result.output_path.read_text(encoding="utf-8")
        self.assertIn("人物状态演化候选 Patch", report)
        self.assertIn("不会自动修改", report)
        self.assertIsNone(result.agent_tasks_path)

    def test_state_patch_finds_default_scene_draft(self):
        project = self.make_project()
        add_character(project)
        make_passing_scene(project)

        result = build_character_state_patch(project, scene=Path("scenes/scene_0001.yaml"))

        self.assertEqual(result.source_path, project / "drafts" / "scenes" / "scene_0001.md")

    def test_agent_tasks_sidecar_does_not_pollute_state_patch_json(self):
        project = self.make_project()
        add_character(project)
        draft = make_passing_scene(project)

        result = build_character_state_patch(
            project,
            scene=Path("scenes/scene_0001.yaml"),
            source=draft,
            agent_tasks=True,
        )

        self.assertIsNotNone(result.agent_tasks_path)
        assert result.agent_tasks_path is not None
        tasks = result.agent_tasks_path.read_text(encoding="utf-8")
        self.assertIn("[AGENT_TASK:", tasks)
        self.assertIn("审查状态变化依据", tasks)
        self.assertNotIn("[AGENT_TASK:", result.json_path.read_text(encoding="utf-8"))

    def test_cli_exposes_and_runs_state_evolve(self):
        project = self.make_project()
        add_character(project)
        make_passing_scene(project)

        self.assertIn("state-evolve", build_parser().format_help())
        code = main(["state-evolve", str(project), "--scene", "scenes/scene_0001.yaml"])

        self.assertEqual(code, 0)
        self.assertTrue((project / "characters" / "state_patches" / "scene_0001_state_patch.md").exists())


if __name__ == "__main__":
    unittest.main()
