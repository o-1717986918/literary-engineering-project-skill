import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from literary_engineering_workbench.agent_provider import run_agent_task
from literary_engineering_workbench.cli import build_parser, main

from helpers import TempProjectMixin


class AgentProviderTests(TempProjectMixin, unittest.TestCase):
    def test_dry_run_writes_auditable_agent_artifacts(self):
        project = self.make_project()

        result = run_agent_task(
            project,
            agent_id="scene-reviewer",
            task="review-scene",
            system_prompt="你是文学工程审查 agent。",
            user_prompt="请审查 scene_0001。",
            provider="dry-run",
        )

        self.assertTrue(result.input_path.exists())
        self.assertTrue(result.raw_output_path.exists())
        self.assertTrue(result.parsed_output_path.exists())
        self.assertTrue(result.validation_path.exists())
        self.assertEqual(result.parse_status, "json_parsed")

        input_payload = json.loads(result.input_path.read_text(encoding="utf-8"))
        self.assertEqual(input_payload["schema"], "literary-engineering-workbench/agent-input/v0.1")
        self.assertEqual(input_payload["agent_id"], "scene-reviewer")
        self.assertEqual(input_payload["messages"][0]["role"], "system")

        parsed = json.loads(result.parsed_output_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed["agent_id"], "scene-reviewer")
        self.assertEqual(parsed["task"], "review-scene")
        self.assertEqual(parsed["status"], "dry_run")
        self.assertIn("json_parsed", result.validation_path.read_text(encoding="utf-8"))

    def test_cli_runs_agent_task_with_inline_prompts(self):
        project = self.make_project()
        out_dir = project / "agents" / "runs" / "cli-agent-test"

        code = main(
            [
                "agent-run",
                str(project),
                "--agent-id",
                "prompt-builder",
                "--task",
                "build-style-prompt",
                "--system-text",
                "你负责生成提示词。",
                "--user-text",
                "请根据 profile 生成约束。",
                "--provider",
                "dry-run",
                "--out-dir",
                str(out_dir),
            ]
        )

        self.assertEqual(code, 0)
        self.assertTrue((out_dir / "input.prompt.json").exists())
        parsed = json.loads((out_dir / "parsed_output.json").read_text(encoding="utf-8"))
        self.assertEqual(parsed["agent_id"], "prompt-builder")

    def test_http_chat_provider_requires_model_environment(self):
        project = self.make_project()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(
                "os.environ",
                {
                    "LEW_CONFIG_PATH": str(Path(tmp) / "config.json"),
                    "LEW_MODEL_API_BASE": "",
                    "LEW_MODEL_NAME": "",
                    "LEW_MODEL_API_KEY": "",
                    "DEEPSEEK_API_KEY": "",
                },
                clear=False,
            ):
                with self.assertRaises(RuntimeError) as raised:
                    run_agent_task(
                        project,
                        agent_id="scene-reviewer",
                        task="review-scene",
                        system_prompt="系统提示",
                        user_prompt="用户提示",
                        provider="http-chat",
                    )
        self.assertIn("LEW_MODEL_API_KEY", str(raised.exception))

    def test_auto_provider_uses_configured_http_chat(self):
        project = self.make_project()
        server = _FakeChatServer()
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
            result = run_agent_task(
                project,
                agent_id="scene-reviewer",
                task="review-scene",
                system_prompt="系统提示",
                user_prompt="用户提示",
            )

        self.assertEqual(result.provider, "http-chat")
        self.assertEqual(server.last_auth, "Bearer test-key")
        self.assertEqual(server.last_payload["model"], "fake-model")
        parsed = json.loads(result.parsed_output_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed["status"], "llm")

    def test_cli_exposes_agent_run(self):
        self.assertIn("agent-run", build_parser().format_help())


class _FakeChatServer:
    def __init__(self):
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
                                "content": json.dumps(
                                    {
                                        "schema": "literary-engineering-workbench/agent-output/v0.1",
                                        "agent_id": "scene-reviewer",
                                        "task": "review-scene",
                                        "status": "llm",
                                        "findings": [],
                                        "recommendations": [],
                                    },
                                    ensure_ascii=False,
                                )
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
