import json
import unittest

from helpers import TempProjectMixin
from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.protocol import resolve_protocol_route
from literary_engineering_workbench.source_ingest import ingest_existing_work


class SourceIngestTests(TempProjectMixin, unittest.TestCase):
    def test_ingest_existing_work_writes_manifest_chunks_and_agent_task(self):
        root = self.make_project()
        source = root.parent / "existing-work.md"
        source.write_text(
            "林舟在停电后的旧楼里发现一页档案。"
            "档案没有写明名字，只留下一个被涂掉的机构编号。"
            "他不愿把同伴拖进危险，于是独自记下楼道里的脚步声。\n" * 8,
            encoding="utf-8",
        )

        result = ingest_existing_work(
            root,
            source=source,
            title="旧楼档案",
            work_id="old-archive",
            mode="continuation",
            chunk_size=220,
        )

        self.assertTrue(result.manifest_path.exists())
        self.assertTrue(result.report_path.exists())
        self.assertTrue(result.task_path.exists())
        self.assertGreaterEqual(result.chunk_count, 2)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], "literary-engineering-workbench/source-ingest/v1")
        self.assertEqual(manifest["work_id"], "old-archive")
        self.assertIn("characters", manifest["candidate_outputs"])
        task = result.task_path.read_text(encoding="utf-8")
        self.assertIn("[AGENT_TASK:", task)
        self.assertIn("evidence_refs", task)
        self.assertIn("characters/candidates/extracted/old-archive_characters.md", task)
        self.assertIn("reviews/source_ingest/old-archive_extraction_review.md", task)

    def test_cli_source_ingest_accepts_inline_text(self):
        root = self.make_project()
        code = main(
            [
                "source-ingest",
                str(root),
                "--text",
                "她把城门钥匙交给陌生人，又在黎明前改写了巡逻表。",
                "--title",
                "城门",
                "--work-id",
                "gate",
            ]
        )

        self.assertEqual(code, 0)
        self.assertTrue((root / "sources" / "imports" / "gate" / "source_manifest.json").exists())
        self.assertTrue((root / "sources" / "imports" / "gate" / "extract_project_files.agent_tasks.md").exists())

    def test_source_ingest_protocol_and_help_are_available(self):
        self.assertIn("source-ingest", build_parser().format_help())
        route = resolve_protocol_route("source_ingest")
        self.assertEqual(route.key, "source-ingest")
        self.assertIn("existing text", route.purpose)


if __name__ == "__main__":
    unittest.main()
