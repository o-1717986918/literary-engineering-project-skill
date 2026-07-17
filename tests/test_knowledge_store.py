import json
import unittest

from literary_engineering_workbench.cli import build_parser
from literary_engineering_workbench.knowledge_store import build_knowledge_store, search_knowledge_store

from helpers import TempProjectMixin, add_character


class KnowledgeStoreTests(TempProjectMixin, unittest.TestCase):
    def test_build_json_knowledge_store_with_metadata(self):
        project = self.make_project()
        add_character(project)

        result = build_knowledge_store(project)
        self.assertTrue(result.store_path.exists())
        payload = json.loads(result.store_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["backend"], "json")
        self.assertGreater(payload["item_count"], 0)

        character_items = [
            item for item in payload["items"]
            if item["source"] == "characters/linzhou.yaml"
        ]
        self.assertTrue(character_items)
        metadata = character_items[0]["metadata"]
        self.assertEqual(metadata["canon_status"], "confirmed")
        self.assertEqual(metadata["character_id"], "linzhou")
        self.assertEqual(metadata["authority"], "structured")

    def test_search_knowledge_store_with_filters(self):
        project = self.make_project()
        add_character(project)
        build_knowledge_store(project)

        hits = search_knowledge_store(project, "林舟 档案", kind="characters", canon_status="confirmed")
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0].kind, "characters")
        self.assertEqual(hits[0].canon_status, "confirmed")
        self.assertEqual(hits[0].metadata["character_id"], "linzhou")

        no_hits = search_knowledge_store(project, "林舟", kind="drafts", canon_status="confirmed")
        self.assertEqual(no_hits, [])

    def test_cli_exposes_knowledge_commands(self):
        help_text = build_parser().format_help()
        self.assertIn("knowledge-build", help_text)
        self.assertIn("knowledge-search", help_text)


if __name__ == "__main__":
    unittest.main()
