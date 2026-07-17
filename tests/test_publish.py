import json
import unittest

from literary_engineering_workbench.approval import record_workflow_approval
from literary_engineering_workbench.cli import build_parser
from literary_engineering_workbench.publish import publish_chapter

from helpers import TempProjectMixin, make_reviewed_passing_scene


class PublishChapterTests(TempProjectMixin, unittest.TestCase):
    def test_publish_ready_approved_chapter(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        record_workflow_approval(project, "run-ok", "approve", actor="tester", notes="章节可发布。")

        result = publish_chapter(project, chapter_id="chapter_0001", release_id="release-test", approval_run_id="run-ok")

        self.assertEqual(result.status, "published")
        self.assertEqual(result.published_scene_count, 1)
        self.assertTrue(result.manifest_path.exists())
        self.assertTrue(result.notes_path.exists())
        self.assertTrue(result.rollback_path.exists())
        self.assertTrue(result.latest_path.exists())

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["approval"]["run_id"], "run-ok")
        self.assertEqual(manifest["gates"]["chapter_workspace"]["blocked_count"], 0)
        self.assertIn("novel", manifest["published_outputs"])

        latest = json.loads(result.latest_path.read_text(encoding="utf-8"))
        self.assertEqual(latest["release_id"], "release-test")

    def test_publish_requires_approval_by_default(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)

        with self.assertRaises(RuntimeError):
            publish_chapter(project, chapter_id="chapter_0001", release_id="release-test")

    def test_allow_unapproved_creates_internal_release(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)

        result = publish_chapter(
            project,
            chapter_id="chapter_0001",
            release_id="internal-test",
            allow_unapproved=True,
        )

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(result.status, "published_internal")
        self.assertEqual(manifest["approval"]["decision"], "allow_unapproved")

    def test_non_ready_chapter_is_blocked(self):
        project = self.make_project()
        record_workflow_approval(project, "run-ok", "approve", actor="tester")

        with self.assertRaises(RuntimeError):
            publish_chapter(project, chapter_id="chapter_0001", release_id="release-test", approval_run_id="run-ok")

    def test_cli_exposes_publish_chapter(self):
        self.assertIn("publish-chapter", build_parser().format_help())


if __name__ == "__main__":
    unittest.main()
