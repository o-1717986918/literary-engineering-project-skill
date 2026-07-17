import unittest
from pathlib import Path

from literary_engineering_workbench.langgraph_adapter import (
    _combine_status,
    is_langgraph_available,
    run_literary_graph,
)

from helpers import TempProjectMixin, make_reviewed_passing_scene


class LangGraphAdapterTests(TempProjectMixin, unittest.TestCase):
    def test_availability_probe_returns_bool(self):
        self.assertIsInstance(is_langgraph_available(), bool)

    def test_status_combination_keeps_more_severe_state(self):
        self.assertEqual(_combine_status("blocked", "completed"), "blocked")
        self.assertEqual(_combine_status("completed_with_skips", "blocked"), "blocked")
        self.assertEqual(_combine_status("failed", "blocked"), "failed")

    def test_langgraph_adapter_runs_graph(self):
        if not is_langgraph_available():
            self.skipTest("langgraph is not installed")
        project = self.make_project()
        make_reviewed_passing_scene(project)
        result = run_literary_graph(project, scene=Path("scenes/scene_0001.yaml"), thread_id="thread-demo")
        self.assertIn(result["status"], {"completed", "completed_with_skips"})
        self.assertEqual(result["thread_id"], "thread-demo")
        self.assertIn("scene_loop_run_id", result)
        self.assertIn("chapter_publish_run_id", result)


if __name__ == "__main__":
    unittest.main()
