import json
import unittest
import zipfile

from literary_engineering_workbench.chapter_pipeline import build_chapter_workspace
from literary_engineering_workbench.cli import build_parser
from literary_engineering_workbench.export_package import build_export_package
from literary_engineering_workbench.flow_gates import FlowGateError

from helpers import TempProjectMixin, make_reviewed_passing_scene, make_static_reviewed_passing_scene


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
        novel_text = result.novel_path.read_text(encoding="utf-8")
        screenplay_text = result.screenplay_path.read_text(encoding="utf-8")
        video_prompt_text = result.video_prompt_path.read_text(encoding="utf-8")
        self.assertNotIn("导出规则", novel_text)
        self.assertNotIn("新 canon 写回", novel_text)
        self.assertNotIn("scene_0001", novel_text)
        self.assertNotIn("scene_0001", screenplay_text)
        self.assertNotIn("scene_0001", video_prompt_text)
        self.assertNotIn("## 状态变化", novel_text)
        self.assertNotIn("### 新增事实候选", novel_text)
        self.assertNotIn("审查状态", screenplay_text)
        self.assertNotIn("场景目标", screenplay_text)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["exported_scenes"]), 1)
        self.assertEqual(result.docx_outputs, {})

    def test_final_export_filters_accidental_workbench_traces_from_body(self):
        project = self.make_project()
        draft = make_reviewed_passing_scene(project)
        text = draft.read_text(encoding="utf-8")
        text = text.replace(
            "他把手电压低，沿着墙边移动，心里清楚每一步都会改变同伴明天能否继续调查。",
            "他把手电压低，沿着墙边移动。\n\nscene_id: scene_0001\n\n## 状态变化候选\n\n### 新增事实候选\n\n- canon 信息不应进入最终作品。",
        )
        draft.write_text(text, encoding="utf-8")
        build_chapter_workspace(project, chapter_id="chapter_0001")

        result = build_export_package(project, chapter_id="chapter_0001")
        novel_text = result.novel_path.read_text(encoding="utf-8")

        self.assertIn("他把手电压低", novel_text)
        self.assertNotIn("scene_0001", novel_text)
        self.assertNotIn("状态变化候选", novel_text)
        self.assertNotIn("canon 信息", novel_text)

    def test_final_docx_filters_world_state_change_markers(self):
        project = self.make_project()
        draft = make_reviewed_passing_scene(project)
        text = draft.read_text(encoding="utf-8")
        text = text.replace(
            "他把手电压低，沿着墙边移动，心里清楚每一步都会改变同伴明天能否继续调查。",
            "他把手电压低，沿着墙边移动。\n\n## 世界状态变化\n\n- 旧楼停电扩大为城市级异常。",
        )
        draft.write_text(text, encoding="utf-8")

        result = build_export_package(project, chapter_id="chapter_0001", formats="md,docx")
        novel_text = result.novel_path.read_text(encoding="utf-8")
        with zipfile.ZipFile(result.docx_outputs["novel"]) as package:
            document_xml = package.read("word/document.xml").decode("utf-8")

        self.assertIn("他把手电压低", novel_text)
        self.assertNotIn("世界状态变化", novel_text)
        self.assertNotIn("城市级异常", novel_text)
        self.assertNotIn("世界状态变化", document_xml)
        self.assertNotIn("城市级异常", document_xml)

    def test_final_export_normalizes_corner_quotes(self):
        project = self.make_project()
        draft = make_reviewed_passing_scene(project)
        text = draft.read_text(encoding="utf-8")
        text = text.replace(
            "林舟站在旧楼门口，听见楼道深处的电流声断断续续。",
            "林舟站在旧楼门口，听见楼道深处有人说：「别再往前走。」",
        )
        draft.write_text(text, encoding="utf-8")
        build_chapter_workspace(project, chapter_id="chapter_0001")

        result = build_export_package(project, chapter_id="chapter_0001")
        novel_text = result.novel_path.read_text(encoding="utf-8")

        self.assertIn("“别再往前走。”", novel_text)
        self.assertNotIn("「", novel_text)
        self.assertNotIn("」", novel_text)

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
        self.assertEqual(set(manifest["outputs"]["docx_layout_plans"]), {"novel", "screenplay", "video_prompt_pack"})
        self.assertEqual(set(manifest["outputs"]["docx_inspections"]), {"novel", "screenplay", "video_prompt_pack"})
        for path in result.docx_layout_plans.values():
            self.assertTrue(path.exists())
        for path in result.docx_inspections.values():
            self.assertTrue(path.exists())

    def test_export_blocks_non_ready_scenes_by_default(self):
        project = self.make_project()
        make_static_reviewed_passing_scene(project)

        with self.assertRaises(FlowGateError):
            build_export_package(project, chapter_id="chapter_0001")

    def test_export_include_blocked_is_internal_preview_only(self):
        project = self.make_project()
        make_static_reviewed_passing_scene(project)

        result = build_export_package(project, chapter_id="chapter_0001", include_blocked=True)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(result.exported_scene_count, 1)
        self.assertTrue(manifest["include_blocked"])
        self.assertIn("内部预览", result.novel_path.read_text(encoding="utf-8"))

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
