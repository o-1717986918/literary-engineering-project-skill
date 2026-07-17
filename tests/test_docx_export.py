import tempfile
import unittest
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
                    ]
                ),
                encoding="utf-8",
            )
            result = export_markdown_to_docx(source, kind="novel")
            self.assertTrue(result.docx_path.exists())
            self.assertGreaterEqual(result.paragraph_count, 5)
            info = inspect_docx(result.docx_path)
            self.assertGreaterEqual(info["paragraph_count"], 5)
            with zipfile.ZipFile(result.docx_path) as package:
                self.assertIn("word/document.xml", package.namelist())
                document_xml = package.read("word/document.xml").decode("utf-8")
                self.assertIn("第一章", document_xml)
                self.assertIn("旧档案", document_xml)


if __name__ == "__main__":
    unittest.main()
