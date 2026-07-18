import tempfile
import unittest
import json
import zipfile
from pathlib import Path

from literary_engineering_workbench.docx_export import export_markdown_to_docx, inspect_docx


class DocxExportTests(unittest.TestCase):
    def test_exports_markdown_to_docx_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "chapter.md"
            source.write_text(
                "\n".join(
                    [
                        "# 第一章",
                        "",
                        "## 场景一",
                        "",
                        "她把旧档案放回桌面，听见楼下的钟声。",
                        "",
                        "- 保留人物动作",
                        "- 保留场景线索",
                        "",
                        "| 项目 | 状态 |",
                        "| --- | --- |",
                        "| 引号统一 | 已检查 |",
                    ]
                ),
                encoding="utf-8",
            )
            result = export_markdown_to_docx(source, kind="novel")
            self.assertTrue(result.docx_path.exists())
            self.assertTrue(result.layout_plan_path.exists())
            self.assertTrue(result.inspection_path.exists())
            self.assertGreaterEqual(result.paragraph_count, 5)
            info = inspect_docx(result.docx_path)
            self.assertGreaterEqual(info["paragraph_count"], 5)
            self.assertGreaterEqual(info["table_count"], 1)
            self.assertTrue(info["has_east_asia_fonts"])
            layout = json.loads(result.layout_plan_path.read_text(encoding="utf-8"))
            inspection = json.loads(result.inspection_path.read_text(encoding="utf-8"))
            self.assertEqual(layout["schema"], "literary-engineering-workbench/docx-layout-plan/v0.2")
            self.assertEqual(layout["source_structure"]["table_count"], 1)
            self.assertEqual(inspection["table_count"], 1)
            with zipfile.ZipFile(result.docx_path) as package:
                self.assertIn("word/document.xml", package.namelist())
                document_xml = package.read("word/document.xml").decode("utf-8")
                self.assertIn("第一章", document_xml)
                self.assertIn("旧档案", document_xml)
                self.assertIn("<w:tbl>", document_xml)


if __name__ == "__main__":
    unittest.main()
