import json
import unittest
from pathlib import Path

from literary_engineering_workbench.branch_lab import build_branch_simulation
from literary_engineering_workbench.cli import main

from helpers import TempProjectMixin, add_character


class BranchLabTests(TempProjectMixin, unittest.TestCase):
    def test_build_branch_simulation_outputs_manifest_and_selection(self):
        project = self.make_project()
        add_character(project)
        _write_scene(project)

        result = build_branch_simulation(
            project,
            scene=Path("scenes/scene_0001.yaml"),
            rebuild_context=True,
            branch_count=3,
        )

        self.assertEqual(result.branch_count, 3)
        self.assertTrue(result.output_path.exists())
        self.assertTrue(result.manifest_path.exists())
        self.assertTrue(result.selection_path.exists())
        self.assertIn("branch_", result.recommended_branch)

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["scene_id"], "scene_0001")
        self.assertEqual(len(manifest["branches"]), 3)
        self.assertEqual(manifest["branches"][0]["scores"]["character_logic"], 5)
        self.assertIn("background_story", manifest["characters"][0])
        self.assertEqual(manifest["characters"][0]["background_story"]["reveal_policy"], "implicit_only")
        self.assertIn("不得直接讲述", "\n".join(manifest["branches"][0]["character_tests"]))
        self.assertIn("分支不是 canon", "\n".join(manifest["guardrails"]))
        self.assertIn("- decision: pending", result.selection_path.read_text(encoding="utf-8"))
        self.assertIsNone(result.agent_tasks_path)

    def test_branch_simulation_preserves_formal_selection_record(self):
        project = self.make_project()
        add_character(project)
        _write_scene(project)

        first = build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=3)
        first.selection_path.write_text(
            f"""# Branch Selection：scene_0001

## 人工决定

- decision: selected
- selected_branch: {first.recommended_branch}
- reviewer: platform-agent-test
- selected_at: 2026-01-01T00:00:00Z
""",
            encoding="utf-8",
        )
        second = build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=3)

        self.assertEqual(second.selection_path, first.selection_path)
        self.assertIn(f"selected_branch: {first.recommended_branch}", second.selection_path.read_text(encoding="utf-8"))

    def test_agent_tasks_sidecar_does_not_pollute_manifest(self):
        project = self.make_project()
        add_character(project)
        _write_scene(project)

        result = build_branch_simulation(
            project,
            scene=Path("scenes/scene_0001.yaml"),
            branch_count=3,
            agent_tasks=True,
        )

        self.assertIsNotNone(result.agent_tasks_path)
        assert result.agent_tasks_path is not None
        self.assertTrue(result.agent_tasks_path.exists())
        tasks = result.agent_tasks_path.read_text(encoding="utf-8")
        self.assertIn("[AGENT_TASK:", tasks)
        self.assertIn("不要自动接受 recommended_branch", tasks)
        manifest_text = result.manifest_path.read_text(encoding="utf-8")
        self.assertNotIn("[AGENT_TASK:", manifest_text)

    def test_missing_character_marks_branch_as_needs_detail(self):
        project = self.make_project()
        _write_scene(project, participants=["unknown"])

        result = build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=2)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

        statuses = {branch["status"] for branch in manifest["branches"]}
        self.assertEqual(statuses, {"needs_detail"})
        self.assertIn("缺少正式人物档案", "\n".join(manifest["branches"][0]["risks"]))

    def test_unknown_participant_with_other_characters_needs_detail(self):
        project = self.make_project()
        add_character(project)
        _write_scene(project, participants=["unknown"])

        result = build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=2)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

        statuses = {branch["status"] for branch in manifest["branches"]}
        self.assertEqual(statuses, {"needs_detail"})
        self.assertIn("participants 未匹配", "\n".join(manifest["branches"][0]["risks"]))

    def test_branch_count_range_is_validated(self):
        project = self.make_project()
        with self.assertRaises(ValueError):
            build_branch_simulation(project, branch_count=1)

    def test_cli_exposes_branch_simulate(self):
        with self.assertRaises(SystemExit) as raised:
            main(["branch-simulate", "--help"])
        self.assertEqual(raised.exception.code, 0)


def _write_scene(project: Path, participants=None):
    participants = participants if participants is not None else ["linzhou"]
    path = project / "scenes" / "scene_0001.yaml"
    path.write_text(
        """scene_id: scene_0001
chapter_id: chapter_0001
status: planned
location: 旧楼档案室
participants:
{participants}
input_state:
  canon_refs:
    - canon/facts.json
  character_states: []
  active_foreshadowing:
    - 残缺档案
scene_goal: 找到停电与档案之间的关系
conflict:
  external: 看守即将回到旧楼
  internal: 林舟担心牵连同伴
style_constraints:
  - 克制
output_state:
  new_facts: []
  character_changes: []
  relationship_changes: []
  foreshadowing_changes: []
  next_hooks:
    - 旧楼地下室出现新的电流声
""".format(participants="\n".join(f"  - {item}" for item in participants)),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
