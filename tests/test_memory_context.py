import json
import unittest
from pathlib import Path

from literary_engineering_workbench.context_packet import build_context_packet
from literary_engineering_workbench.memory_index import build_memory_index, search_memory

from helpers import TempProjectMixin, add_character


class MemoryContextTests(TempProjectMixin, unittest.TestCase):
    def test_index_search_and_context_packet(self):
        project = self.make_project()
        result = build_memory_index(project)
        self.assertTrue(result.index_path.exists())
        self.assertGreater(result.chunk_count, 0)

        hits = search_memory(project, "测试作品")
        self.assertGreaterEqual(len(hits), 1)

        packet = build_context_packet(project, scene=Path("scenes/scene_0001.yaml"), rebuild_index=True)
        self.assertTrue(packet.output_path.exists())
        self.assertTrue(packet.trace_path.exists())
        self.assertIn("场景上下文包", packet.output_path.read_text(encoding="utf-8"))
        trace = json.loads(packet.trace_path.read_text(encoding="utf-8"))
        self.assertEqual(trace["schema"], "literary-engineering-workbench/context-trace/v1")
        self.assertEqual(trace["context_packet"], "memory/context_packets/scene_0001.md")
        self.assertIn("project.yaml", trace["loaded_files"])
        self.assertIn("scenes/scene_0001.yaml", trace["loaded_files"])

    def test_context_packet_loads_major_and_scene_referenced_minor_characters(self):
        project = self.make_project()
        add_character(project)
        (project / "characters" / "guard.yaml").write_text(
            """character_id: guard
name: 守卫
role: 次要角色
importance: secondary
background_story:
  summary: 他只在旧楼门口短暂出现。
bdi:
  belief:
    - 今夜不会有人来。
  desire:
    - 尽快结束值守。
  intention:
    - 阻止陌生人靠近。
""",
            encoding="utf-8",
        )
        (project / "characters" / "bystander.yaml").write_text(
            """character_id: bystander
name: 路人
role: 次要角色
importance: secondary
background_story:
  summary: 无关次要角色绝密传闻不应进入本场上下文。
""",
            encoding="utf-8",
        )
        (project / "scenes" / "scene_0001.yaml").write_text(
            """scene_id: scene_0001
chapter_id: chapter_0001
location: 旧楼门口
participants:
  - guard
referenced_characters: []
scene_goal: 林舟绕开守卫进入旧楼。
conflict:
  external: 守卫正在门口巡查。
  internal: 林舟不想牵连同伴。
output_state:
  new_facts: []
  character_changes: []
  relationship_changes: []
  foreshadowing_changes: []
  next_hooks: []
""",
            encoding="utf-8",
        )

        packet = build_context_packet(project, scene=Path("scenes/scene_0001.yaml"), rebuild_index=True)
        text = packet.output_path.read_text(encoding="utf-8")
        trace = json.loads(packet.trace_path.read_text(encoding="utf-8"))

        self.assertIn("linzhou.yaml（主要角色常驻）", text)
        self.assertIn("guard.yaml（本场景参与/引用）", text)
        self.assertIn("本场景省略的次要角色", text)
        self.assertIn("bystander", text)
        self.assertNotIn("无关次要角色绝密传闻", text)
        self.assertIn("characters/linzhou.yaml", trace["character_files"])
        self.assertIn("characters/guard.yaml", trace["character_files"])
        self.assertIn("characters/bystander.yaml", trace["excluded_files"])


if __name__ == "__main__":
    unittest.main()
