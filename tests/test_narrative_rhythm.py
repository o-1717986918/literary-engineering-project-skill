import json
import unittest
from pathlib import Path

from literary_engineering_workbench.context_packet import build_context_packet
from literary_engineering_workbench.narrative_rhythm import narrative_rhythm_contract, render_narrative_rhythm_contract
from literary_engineering_workbench.prompt_pack import build_scene_prompt_pack, write_prompt_manifest

from helpers import TempProjectMixin


class NarrativeRhythmTests(TempProjectMixin, unittest.TestCase):
    def test_empty_explicit_rhythm_block_is_incomplete_not_pass(self):
        project = self.make_project()
        scene = project / "scenes" / "scene_0001.yaml"
        scene.write_text(
            scene.read_text(encoding="utf-8")
            + """
narrative_rhythm:
  scene_function: []
  scene_turn: ""
  reader_effect: ""
scene_bridge:
  incoming_pressure: ""
  outgoing_hook: ""
""",
            encoding="utf-8",
        )

        contract = narrative_rhythm_contract(project, Path("scenes/scene_0001.yaml"))

        self.assertEqual(contract["status"], "incomplete")
        self.assertIn("narrative_rhythm.scene_turn", contract["missing_required"])

    def test_scene_yaml_rhythm_and_bridge_enter_generation_prompt(self):
        project = self.make_project()
        _write_rhythm_scene(project)
        context = build_context_packet(project, scene=Path("scenes/scene_0001.yaml"), rebuild_index=True)

        contract = narrative_rhythm_contract(project, Path("scenes/scene_0001.yaml"))
        rendered = render_narrative_rhythm_contract(project, Path("scenes/scene_0001.yaml"))

        self.assertEqual(contract["status"], "pass")
        self.assertEqual(contract["source"], "scene.yaml")
        self.assertEqual(contract["narrative_rhythm"]["density_mix"]["summary"], "low")
        self.assertEqual(contract["scene_bridge"]["outgoing_hooks"][0]["type"], "plot_pressure")
        self.assertIn("推进主线；改变关系", rendered)
        self.assertIn("plot_pressure: 敌方拿到错误线索", rendered)

        pack = build_scene_prompt_pack(
            project,
            Path("scenes/scene_0001.yaml"),
            context.output_path,
            allow_missing_composition=True,
        )
        self.assertIn("本场景叙事节奏与场景桥接硬属性", pack.user_prompt)
        self.assertIn("叙述距离：limited_close", pack.user_prompt)
        manifest_path = write_prompt_manifest(pack, project / "drafts" / "candidates" / "scene_0001.prompt.json", "platform-agent")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rhythm = manifest["generation_standards"]["narrative_rhythm_contract"]
        self.assertEqual(rhythm["status"], "pass")
        self.assertTrue(manifest["generation_standards"]["narrative_rhythm_loaded"])


def _write_rhythm_scene(project: Path) -> Path:
    path = project / "scenes" / "scene_0001.yaml"
    path.write_text(
        """scene_id: scene_0001
chapter_id: chapter_0001
status: planned
location: 旧楼档案室
participants: []
scene_goal: 找到停电与档案之间的关系
conflict:
  external: 看守即将回到旧楼
  internal: 主角担心牵连同伴
narrative_rhythm:
  rhythm_role: conflict
  pace: fast_to_slow
  density: high
  scene_function:
    - 推进主线
    - 改变关系
  scene_turn: 主角从试探转为明确承担代价
  reader_effect: 读者意识到表面胜利制造了更大风险
  density_mix:
    summary: low
    action: high
    dialogue: medium
    reflection: low
    description: low
  narrative_distance: limited_close
  slow_down_points:
    - 主角决定隐瞒事实
  speed_up_points:
    - 进入旧楼前的过场
scene_bridge:
  incoming_pressure: 接住上一场隐瞒事实的压力
  incoming_from_previous:
    - 上一场的错误线索
  reader_questions_carried:
    - 那封信是谁放进去的
  outgoing_hooks:
    - type: plot_pressure
      content: 敌方拿到错误线索
  outgoing_hook: 敌方即将按错误线索行动
  promise_payoff_items:
    - type: payoff_delay
      content: 兑现旧楼线索，延迟幕后组织真相
output_state:
  next_hooks: []
""",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
