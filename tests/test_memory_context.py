import unittest
from pathlib import Path

from literary_engineering_workbench.context_packet import build_context_packet
from literary_engineering_workbench.memory_index import build_memory_index, search_memory

from helpers import TempProjectMixin


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
        self.assertIn("场景上下文包", packet.output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
