import json
import unittest
from pathlib import Path
from unittest.mock import patch

from literary_engineering_workbench.approval import record_workflow_approval
from literary_engineering_workbench.character_state_apply import apply_character_state_patch
from literary_engineering_workbench.character_state_evolver import build_character_state_patch
from literary_engineering_workbench.cli import build_parser, main

from helpers import TempProjectMixin, add_character, make_passing_scene


class CharacterStateApplyTests(TempProjectMixin, unittest.TestCase):
    def test_apply_requires_approval_by_default(self):
        project = self.make_project()
        add_character(project)
        draft = make_passing_scene(project)
        patch = build_character_state_patch(project, scene=Path("scenes/scene_0001.yaml"), source=draft)

        with self.assertRaises(RuntimeError):
            apply_character_state_patch(project, patch=patch.json_path)

    def test_apply_approved_state_patch_to_character_file(self):
        project = self.make_project()
        character_file = add_character(project)
        draft = make_passing_scene(project)
        patch = build_character_state_patch(project, scene=Path("scenes/scene_0001.yaml"), source=draft)
        record_workflow_approval(project, "state-run", "approve", actor="tester", notes="人物变化可写回。")

        result = apply_character_state_patch(project, patch=patch.json_path, approval_run_id="state-run")

        self.assertEqual(result.status, "applied")
        self.assertEqual(result.applied_character_count, 1)
        self.assertGreaterEqual(result.update_count, 2)
        self.assertTrue(result.manifest_path.exists())
        self.assertTrue(result.report_path.exists())

        text = character_file.read_text(encoding="utf-8")
        self.assertIn("林舟从旁观转为主动调查", text)
        self.assertIn("林舟开始隐瞒自己的行动计划", text)
        self.assertIn("state_patch:characters/state_patches/scene_0001_state_patch.json", text)

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["approval"]["run_id"], "state-run")

    def test_cli_exposes_and_runs_state_apply(self):
        project = self.make_project()
        add_character(project)
        draft = make_passing_scene(project)
        state_patch = build_character_state_patch(project, scene=Path("scenes/scene_0001.yaml"), source=draft)

        self.assertIn("state-apply", build_parser().format_help())
        blocked = main(["state-apply", str(project), "--patch", str(state_patch.json_path), "--allow-unapproved"])
        self.assertEqual(blocked, 2)

        with patch.dict("os.environ", {"LEW_MAINTAINER_MODE": "1"}):
            code = main(["state-apply", str(project), "--patch", str(state_patch.json_path), "--allow-unapproved"])

        self.assertEqual(code, 0)
        self.assertTrue((project / "characters" / "state_patches" / "scene_0001_state_apply.md").exists())


if __name__ == "__main__":
    unittest.main()
