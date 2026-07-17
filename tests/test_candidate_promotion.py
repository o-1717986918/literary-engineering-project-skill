import json
import unittest
from pathlib import Path

from literary_engineering_workbench.candidate_promotion import promote_scene_candidate
from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.generation_provider import generate_scene_candidate

from helpers import TempProjectMixin


class CandidatePromotionTests(TempProjectMixin, unittest.TestCase):
    def test_promotes_candidate_into_reviewable_draft(self):
        project = self.make_project()
        candidate = generate_scene_candidate(
            project,
            scene=Path("scenes/scene_0001.yaml"),
            rebuild_context=True,
            provider="dry-run",
        )

        result = promote_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), candidate=candidate.candidate_path)

        self.assertTrue(result.draft_path.exists())
        self.assertTrue(result.manifest_path.exists())
        self.assertTrue(result.report_path.exists())
        draft = result.draft_path.read_text(encoding="utf-8")
        self.assertIn("## 正文草稿", draft)
        self.assertIn("来源候选", draft)
        self.assertIn("## 状态变化", draft)
        self.assertIn("dry-run provider", draft)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["candidate"], "drafts/candidates/" + candidate.candidate_path.name)
        self.assertEqual(manifest["draft"], "drafts/scenes/scene_0001.md")

        with self.assertRaises(FileExistsError):
            promote_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), candidate=candidate.candidate_path)

    def test_cli_exposes_and_runs_promote_candidate(self):
        project = self.make_project()
        candidate = generate_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True, provider="dry-run")

        self.assertIn("promote-candidate", build_parser().format_help())
        code = main(
            [
                "promote-candidate",
                str(project),
                "--scene",
                "scenes/scene_0001.yaml",
                "--candidate",
                str(candidate.candidate_path),
            ]
        )

        self.assertEqual(code, 0)
        self.assertTrue((project / "drafts" / "scenes" / "scene_0001.md").exists())


if __name__ == "__main__":
    unittest.main()
