import unittest
import json
from pathlib import Path

from literary_engineering_workbench.workflow_runner import load_workflow_state, run_workflow

from helpers import TempProjectMixin, make_reviewed_passing_scene


class WorkflowRunnerTests(TempProjectMixin, unittest.TestCase):
    def test_full_cycle_preserves_existing_draft_and_exports(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        result = run_workflow(project, mode="full-cycle", scene=Path("scenes/scene_0001.yaml"))
        self.assertIn(result.status, {"completed", "completed_with_skips"})
        self.assertTrue(result.state_path.exists())
        self.assertTrue(result.log_path.exists())
        self.assertFalse(result.blocked)

    def test_unknown_mode_fails(self):
        project = self.make_project()
        with self.assertRaises(ValueError):
            run_workflow(project, mode="unknown")

    def test_run_index_and_stable_run_id_are_written(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        result = run_workflow(project, mode="scene-loop", scene=Path("scenes/scene_0001.yaml"), run_id="demo-run")
        self.assertEqual(result.run_id, "demo-run")

        index_path = project / "workflow" / "runs" / "index.jsonl"
        self.assertTrue(index_path.exists())
        record = json.loads(index_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        self.assertEqual(record["run_id"], "demo-run")
        self.assertEqual(record["state_path"], "workflow/runs/demo-run/workflow_state.json")

        state = load_workflow_state(project, "demo-run")
        self.assertEqual(state["run_id"], "demo-run")
        self.assertIn("branch_manifest", state["artifacts"])
        self.assertIn("scene_composition", state["artifacts"])
        self.assertIn("state_patch", state["artifacts"])

        with self.assertRaises(FileExistsError):
            run_workflow(project, mode="scene-loop", scene=Path("scenes/scene_0001.yaml"), run_id="demo-run")

    def test_resume_run_links_to_previous_run(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        first = run_workflow(project, mode="scene-loop", scene=Path("scenes/scene_0001.yaml"), run_id="first-run")
        second = run_workflow(
            project,
            mode="scene-loop",
            scene=Path("scenes/scene_0001.yaml"),
            run_id="retry-run",
            resumed_from=first.run_id,
        )
        self.assertEqual(second.resumed_from, "first-run")
        state = load_workflow_state(project, "retry-run")
        self.assertEqual(state["resumed_from"], "first-run")

    def test_scene_loop_can_generate_candidate_after_composition(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        result = run_workflow(
            project,
            mode="scene-loop",
            scene=Path("scenes/scene_0001.yaml"),
            run_id="generate-run",
            generate_candidate=True,
            provider="dry-run",
        )
        self.assertIn(result.status, {"completed", "completed_with_skips"})
        state = load_workflow_state(project, "generate-run")
        self.assertIn("candidate", state["artifacts"])
        self.assertIn("candidate_manifest", state["artifacts"])
        self.assertIn("prompt_manifest", state["artifacts"])

    def test_scene_loop_can_promote_generated_candidate(self):
        project = self.make_project()
        result = run_workflow(
            project,
            mode="scene-loop",
            scene=Path("scenes/scene_0001.yaml"),
            run_id="promote-run",
            generate_candidate=True,
            promote_candidate=True,
            provider="dry-run",
        )
        self.assertIn(result.status, {"completed", "completed_with_skips"})
        state = load_workflow_state(project, "promote-run")
        self.assertIn("candidate", state["artifacts"])
        self.assertIn("promoted_draft", state["artifacts"])
        self.assertIn("promotion_manifest", state["artifacts"])
        self.assertIn("review", state["artifacts"])
        self.assertIn("state_patch", state["artifacts"])
        draft = project / state["artifacts"]["promoted_draft"]
        self.assertIn("来源候选", draft.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
