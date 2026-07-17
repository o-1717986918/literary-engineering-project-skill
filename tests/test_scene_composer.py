import json
import unittest
from pathlib import Path

from literary_engineering_workbench.branch_lab import build_branch_simulation
from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.scene_composer import build_scene_composition

from helpers import TempProjectMixin, add_character


class SceneComposerTests(TempProjectMixin, unittest.TestCase):
    def test_build_scene_composition_uses_branch_manifest_and_character_background(self):
        project = self.make_project()
        add_character(project)
        _write_scene(project)
        branch = build_branch_simulation(
            project,
            scene=Path("scenes/scene_0001.yaml"),
            rebuild_context=True,
            branch_count=3,
        )

        result = build_scene_composition(
            project,
            scene=Path("scenes/scene_0001.yaml"),
            rebuild_context=True,
        )

        self.assertEqual(result.scene_id, "scene_0001")
        self.assertEqual(result.selected_branch, branch.recommended_branch)
        self.assertEqual(result.character_count, 1)
        self.assertEqual(result.beat_count, 5)
        self.assertTrue(result.output_path.exists())
        self.assertTrue(result.json_path.exists())

        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["selected_branch"], branch.recommended_branch)
        self.assertEqual(payload["characters"][0]["background_story"]["reveal_policy"], "implicit_only")
        self.assertIn("prose_seed", payload)
        self.assertEqual(len(payload["beats"]), 5)

        report = result.output_path.read_text(encoding="utf-8")
        self.assertIn("正文种子", report)
        self.assertIn("人物潜台词", report)
        self.assertIn("不得直白交代人物背景故事", report)
        self.assertIsNone(result.agent_tasks_path)

    def test_build_scene_composition_without_branch_manifest_uses_fallback(self):
        project = self.make_project()
        add_character(project)
        _write_scene(project)

        result = build_scene_composition(project, scene=Path("scenes/scene_0001.yaml"))
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertEqual(result.selected_branch, "none")
        self.assertEqual(payload["selection_source"], "fallback")
        self.assertEqual(payload["branch"]["status"], "no_manifest")
        self.assertIn("建议先运行 branch-simulate", "\n".join(payload["revision_targets"]))

    def test_agent_tasks_sidecar_keeps_composition_artifacts_clean(self):
        project = self.make_project()
        add_character(project)
        _write_scene(project)
        build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=3)

        result = build_scene_composition(project, scene=Path("scenes/scene_0001.yaml"), agent_tasks=True)

        self.assertIsNotNone(result.agent_tasks_path)
        assert result.agent_tasks_path is not None
        tasks = result.agent_tasks_path.read_text(encoding="utf-8")
        self.assertIn("[AGENT_TASK:", tasks)
        self.assertIn("composition.md 可能进入 generate-scene", tasks)
        self.assertNotIn("[AGENT_TASK:", result.output_path.read_text(encoding="utf-8"))
        self.assertNotIn("[AGENT_TASK:", result.json_path.read_text(encoding="utf-8"))

    def test_cli_exposes_and_runs_compose_scene(self):
        project = self.make_project()
        add_character(project)
        _write_scene(project)

        self.assertIn("compose-scene", build_parser().format_help())
        code = main(["compose-scene", str(project), "--scene", "scenes/scene_0001.yaml"])

        self.assertEqual(code, 0)
        self.assertTrue((project / "drafts" / "compositions" / "scene_0001_composition.md").exists())


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
  - 用动作承载心理
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
