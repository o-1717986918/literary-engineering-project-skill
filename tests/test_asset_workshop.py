import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from literary_engineering_workbench.asset_workshop import (
    create_asset_candidate,
    list_asset_candidates,
    promote_candidate_asset,
    review_candidate_asset,
)
from literary_engineering_workbench.approval import record_workflow_approval
from literary_engineering_workbench.workflow_runner import run_workflow

from helpers import TempProjectMixin


class AssetWorkshopTests(TempProjectMixin, unittest.TestCase):
    def test_creates_reviews_and_lists_character_candidate(self):
        project = self.make_project()
        result = create_asset_candidate(project, asset_type="character", brief="谨慎的调查者", target_id="linzhou", provider="dry-run")

        self.assertEqual(result.status, "pass")
        self.assertTrue(result.candidate_path.exists())
        payload = json.loads(result.candidate_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["asset_type"], "character")
        self.assertEqual(payload["character_id"], "linzhou")

        review = review_candidate_asset(project, result.candidate_path, provider="dry-run")
        self.assertEqual(review.status, "pass")
        self.assertTrue(review.report_path.exists())

        items = list_asset_candidates(project, asset_type="character")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["candidate_id"], result.candidate_id)

    def test_http_chat_asset_creation_normalizes_system_metadata(self):
        project = self.make_project()
        server = _FakeAssetChatServer(_character_payload_without_system_metadata())
        server.start()
        self.addCleanup(server.stop)

        with mock.patch.dict(
            "os.environ",
            {
                "LEW_MODEL_API_BASE": server.url,
                "LEW_MODEL_NAME": "fake-model",
                "LEW_MODEL_API_KEY": "test-key",
            },
            clear=False,
        ):
            result = create_asset_candidate(
                project,
                asset_type="character",
                brief="谨慎的调查者",
                target_id="linzhou",
                provider="http-chat",
            )

        self.assertEqual(result.status, "pass")
        self.assertEqual(server.last_auth, "Bearer test-key")
        self.assertEqual(server.last_payload["model"], "fake-model")

        payload = json.loads(result.candidate_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "literary-engineering-workbench/character-profile-candidate/v1")
        self.assertEqual(payload["candidate_id"], result.candidate_id)
        self.assertEqual(payload["character_id"], "linzhou")
        self.assertIn("project_brief", payload["source_paths"])
        self.assertIn("晋升后", payload["promotion_notes"])

        parsed = json.loads((result.run_dir / "parsed_output.json").read_text(encoding="utf-8"))
        self.assertEqual(parsed["schema"], "literary-engineering-workbench/character-profile-candidate/v1")
        self.assertEqual(parsed["candidate_id"], result.candidate_id)
        validation = json.loads(result.validation_path.read_text(encoding="utf-8"))
        self.assertEqual(validation["status"], "pass")
        self.assertEqual(validation["error_count"], 0)

    def test_promotion_requires_approval_by_default(self):
        project = self.make_project()
        result = create_asset_candidate(project, asset_type="character", brief="谨慎的调查者", target_id="linzhou", provider="dry-run")

        with self.assertRaises(RuntimeError):
            promote_candidate_asset(project, result.candidate_path, group="character")

        record_workflow_approval(project, result.candidate_id, "approve", actor="tester")
        promoted = promote_candidate_asset(project, result.candidate_id, group="character")
        self.assertEqual(promoted.status, "promoted")
        self.assertTrue((project / "characters" / "linzhou.yaml").exists())

    def test_promotes_world_and_outline_candidates_in_internal_mode(self):
        project = self.make_project()
        world = create_asset_candidate(project, asset_type="world", brief="档案被垄断的城市", provider="dry-run")
        outline = create_asset_candidate(project, asset_type="outline", brief="调查旧档案", provider="dry-run")

        world_promotion = promote_candidate_asset(project, world.candidate_path, group="world", allow_unapproved=True)
        outline_promotion = promote_candidate_asset(project, outline.candidate_path, group="outline", allow_unapproved=True)

        self.assertTrue((project / "canon" / "world_rules.yaml").exists())
        self.assertTrue((project / "plot" / "outline.md").exists())
        self.assertTrue(world_promotion.manifest_path.exists())
        self.assertTrue(outline_promotion.manifest_path.exists())

    def test_project_seeding_workflow_creates_reviewed_candidates(self):
        project = self.make_project()
        result = run_workflow(project, mode="project-seeding", run_id="seed-test", provider="dry-run")

        self.assertEqual(result.status, "completed")
        state = json.loads(result.state_path.read_text(encoding="utf-8"))
        self.assertTrue(state["human_approval_required"])
        self.assertIn("world_candidate", state["artifacts"])
        self.assertIn("character_candidate", state["artifacts"])
        self.assertIn("outline_candidate", state["artifacts"])

    def test_cli_exposes_asset_creation_and_promotion(self):
        help_text = subprocess.check_output(
            [sys.executable, "-m", "literary_engineering_workbench", "--help"],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTHONPATH": "src"},
            text=True,
        )
        self.assertIn("agent-create-character", help_text)
        self.assertIn("promote-candidate-asset", help_text)


def _character_payload_without_system_metadata():
    return {
        "asset_type": "character",
        "schema": "character_profile.v1",
        "target_id": "linzhou",
        "character": {
            "character_id": "linzhou",
            "name": "林舟",
            "role": "主角",
            "identity": {"age": 31, "gender": "男", "occupation": "档案调查员", "background": "曾因误判旧档案影响他人命运。"},
            "background_story": {
                "summary": "一次误判让林舟在关键选择前总会先确认代价。",
                "formative_events": ["误读旧档案，导致无辜者被牵连。"],
                "behavior_influences": ["重要判断前反复核对证据。"],
                "reveal_policy": "implicit_only",
            },
            "bdi": {"belief": ["证据必须被重新核对。"], "desire": ["找回被遮蔽的真相。"], "intention": ["先保护同伴，再推进调查。"]},
            "psychology": {"fear": ["再次误伤无辜者。"], "secret": "曾被上级催促草率结案。", "wound": "无法原谅自己的误判。", "mask": "冷静克制。", "moral_line": "不伪造证据。"},
            "relationships": [],
            "speech_style": {"vocabulary": "具体、审慎。", "rhythm": "短句，停顿多。", "taboo_words": ["大概"], "signature_patterns": ["我需要再查原件。"]},
            "arc": {"current_stage": "回避承担", "expected_change": "直面旧错", "required_trigger_events": ["遇到相似误判案件。"]},
            "state": {"location": "档案馆", "health": "正常", "resources": ["查档权限"], "known_facts": ["旧档案存在缺页。"], "unknown_facts": ["缺页由谁移走。"]},
            "memory_refs": ["旧档案编号。"],
        },
        "risks": ["需要避免把愧疚写成单一标签。"],
    }


class _FakeAssetChatServer:
    def __init__(self, content):
        self._content = content
        self._server = HTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self.last_payload = {}
        self.last_auth = ""
        self.url = f"http://127.0.0.1:{self._server.server_port}/v1/chat/completions"
        self._server.owner = self

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._thread.join(timeout=2)
        self._server.server_close()

    @staticmethod
    def _handler():
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                self.server.owner.last_payload = json.loads(body)
                self.server.owner.last_auth = self.headers.get("Authorization", "")
                response = {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(self.server.owner._content, ensure_ascii=False)
                            }
                        }
                    ]
                }
                data = json.dumps(response, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format, *args):
                return

        return Handler


if __name__ == "__main__":
    unittest.main()
