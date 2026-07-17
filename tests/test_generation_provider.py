import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock
from pathlib import Path

from literary_engineering_workbench.cli import build_parser
from literary_engineering_workbench.generation_provider import generate_scene_candidate
from literary_engineering_workbench.scene_composer import build_scene_composition
from literary_engineering_workbench.style_compiler import StyleCompileOptions, compile_style_profile
from literary_engineering_workbench.style_prompt import build_style_prompt

from helpers import TempProjectMixin, make_reviewed_passing_scene


class GenerationProviderTests(TempProjectMixin, unittest.TestCase):
    def test_dry_run_generates_candidate_and_manifest(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        result = generate_scene_candidate(
            project,
            scene=Path("scenes/scene_0001.yaml"),
            rebuild_context=True,
            provider="dry-run",
        )
        self.assertTrue(result.candidate_path.exists())
        self.assertTrue(result.manifest_path.exists())
        self.assertTrue(result.prompt_manifest_path.exists())
        self.assertIn("dry-run provider", result.candidate_path.read_text(encoding="utf-8"))
        self.assertIn("background_story", result.candidate_path.read_text(encoding="utf-8"))
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["provider"], "dry-run")
        self.assertEqual(manifest["scene_id"], "scene_0001")
        self.assertTrue(manifest["candidate"].startswith("drafts/candidates/"))
        self.assertTrue(manifest["prompt_manifest"].startswith("drafts/candidates/"))
        prompt_manifest = json.loads(result.prompt_manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(prompt_manifest["messages"][0]["role"], "system")
        self.assertIn("输出契约", prompt_manifest["messages"][1]["content"])
        self.assertIn("标准中文标点约束", prompt_manifest["messages"][1]["content"])
        self.assertIsNone(result.agent_tasks_path)

    def test_agent_tasks_sidecar_reviews_prompt_manifest_without_pollution(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)

        result = generate_scene_candidate(
            project,
            scene=Path("scenes/scene_0001.yaml"),
            rebuild_context=True,
            provider="dry-run",
            agent_tasks=True,
        )

        self.assertIsNotNone(result.agent_tasks_path)
        assert result.agent_tasks_path is not None
        tasks = result.agent_tasks_path.read_text(encoding="utf-8")
        self.assertIn("[AGENT_TASK:", tasks)
        self.assertIn("审查 prompt manifest", tasks)
        self.assertIn("punctuation-standard.md", tasks)
        self.assertIn("标准中文标点", tasks)
        self.assertNotIn("[AGENT_TASK:", result.prompt_manifest_path.read_text(encoding="utf-8"))
        self.assertNotIn("[AGENT_TASK:", result.manifest_path.read_text(encoding="utf-8"))

    def test_prompt_pack_uses_scene_composition_when_available(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        build_scene_composition(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True)

        result = generate_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), provider="dry-run")
        prompt_manifest = json.loads(result.prompt_manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(prompt_manifest["composition"], "drafts/compositions/scene_0001_composition.md")
        self.assertIn("场景创作编排", prompt_manifest["messages"][1]["content"])

    def test_prompt_pack_prefers_style_prompt_over_profile_report(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        corpus = project / "corpus"
        corpus.mkdir()
        (corpus / "sample.txt").write_text("雨落旧城。灯影摇晃。人们沉默。", encoding="utf-8")
        compiled = compile_style_profile(
            StyleCompileOptions(
                corpus=corpus,
                output_dir=project / "style" / "demo-author",
                name="测试文风",
                author="公版示例",
                source_note="测试语料",
            )
        )
        build_style_prompt(compiled.output_dir, provider="dry-run")

        result = generate_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), provider="dry-run")
        prompt_manifest = json.loads(result.prompt_manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(prompt_manifest["style_profile"], "style/demo-author/style_prompt.md")
        self.assertIn("LLM 文风约束提示词", prompt_manifest["messages"][1]["content"])

    def test_http_chat_provider_posts_prompt_pack_to_endpoint(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
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
            result = generate_scene_candidate(
                project,
                scene=Path("scenes/scene_0001.yaml"),
                rebuild_context=True,
                provider="http-chat",
            )

        self.assertIn("本地假模型生成的正文。", result.candidate_path.read_text(encoding="utf-8"))
        self.assertEqual(server.last_auth, "Bearer test-key")
        self.assertEqual(server.last_payload["model"], "fake-model")
        self.assertEqual(server.last_payload["messages"][0]["role"], "system")
        self.assertIn("输出契约", server.last_payload["messages"][1]["content"])

    def test_http_chat_provider_requires_model_environment(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
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
                    generate_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), provider="http-chat")
        self.assertIn("LEW_MODEL_API_KEY", str(raised.exception))

    def test_unknown_provider_fails(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        with self.assertRaises(ValueError):
            generate_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), provider="unknown")

    def test_cli_exposes_generate_scene(self):
        self.assertIn("generate-scene", build_parser().format_help())


if __name__ == "__main__":
    unittest.main()


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
                                "content": "## 正文候选\n\n本地假模型生成的正文。\n\n## 状态变化候选\n\n### 新增事实候选\n\n- 无。\n\n### 人物状态变化\n\n- 无。\n\n### 关系变化\n\n- 无。\n\n### 伏笔变化\n\n- 无。\n\n### 需要人工确认\n\n- 无。"
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
