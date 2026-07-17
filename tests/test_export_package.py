import json
import unittest

from literary_engineering_workbench.chapter_pipeline import build_chapter_workspace
from literary_engineering_workbench.cli import build_parser
from literary_engineering_workbench.export_package import build_export_package

from helpers import TempProjectMixin, make_reviewed_passing_scene


class ExportPackageTests(TempProjectMixin, unittest.TestCase):
    def test_exports_ready_scenes_to_multiple_formats(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        build_chapter_workspace(project, chapter_id="chapter_0001")
        result = build_export_package(project, chapter_id="chapter_0001")
        self.assertEqual(result.exported_scene_count, 1)
        self.assertEqual(result.skipped_scene_count, 0)
        self.assertTrue(result.novel_path.exists())
        self.assertTrue(result.screenplay_path.exists())
        self.assertTrue(result.video_prompt_path.exists())
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["exported_scenes"]), 1)
        self.assertEqual(result.docx_outputs, {})

    def test_exports_ready_scenes_to_docx_when_requested(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        build_chapter_workspace(project, chapter_id="chapter_0001")
        result = build_export_package(project, chapter_id="chapter_0001", formats="md,docx")
        self.assertEqual(set(result.docx_outputs), {"novel", "screenplay", "video_prompt_pack"})
        for path in result.docx_outputs.values():
            self.assertTrue(path.exists())
            self.assertEqual(path.suffix, ".docx")
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertIn("docx", manifest["requested_formats"])
        self.assertEqual(set(manifest["outputs"]["docx"]), {"novel", "screenplay", "video_prompt_pack"})

    def test_missing_project_fails(self):
        project = self.make_project()
        with self.assertRaises(FileNotFoundError):
            build_export_package(project / "missing")

    def test_cli_exposes_docx_export_commands(self):
        help_text = build_parser().format_help()
        self.assertIn("export-package", help_text)
        self.assertIn("export-docx", help_text)


if __name__ == "__main__":
    unittest.main()
