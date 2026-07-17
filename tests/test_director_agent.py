import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.director_agent import build_director_status, run_director_turn

from helpers import TempProjectMixin, make_reviewed_passing_scene


class DirectorAgentTests(TempProjectMixin, unittest.TestCase):
    def test_director_routes_broad_direction_to_project_seeding(self):
        project = self.make_project()
        result = run_director_turn(project, "从零孵化一个带悬疑气质的双主角长篇", provider="dry-run")

        self.assertEqual(result.status, "executed")
        self.assertTrue(result.decision_path.exists())
        self.assertTrue(result.report_path.exists())
        self.assertTrue(result.workflow_state_path.exists())
        self.assertEqual(result.decision["chosen_workflow"], "project-seeding")
        self.assertGreaterEqual(len(list((project / "canon" / "candidates").rglob("*.json"))), 1)
        self.assertIn("创作总监", result.reply)

    def test_director_can_plan_without_execution(self):
        project = self.make_project()
        result = run_director_turn(project, "只补强角色背景故事和关系压力", provider="dry-run", auto_execute=False)

        self.assertEqual(result.status, "planned")
        self.assertIsNone(result.workflow_state_path)
        self.assertEqual(result.decision["chosen_workflow"], "character-lab")
        self.assertEqual(result.decision["director_tools"][0]["tool"], "run_workflow")
        self.assertEqual(result.decision["tool_loop_status"], "planned")
        self.assertEqual(list((project / "characters" / "candidates").rglob("*.json")), [])

    def test_director_tool_loop_executes_observes_and_reports(self):
        project = self.make_project()
        result = run_director_turn(project, "从零孵化一个带悬疑气质的双主角长篇", provider="dry-run")

        self.assertIn("tool_loop", result.artifacts)
        loop_path = project / result.artifacts["tool_loop"]
        self.assertTrue(loop_path.exists())
        loop = json.loads(loop_path.read_text(encoding="utf-8"))
        self.assertEqual(loop["schema"], "literary-engineering-workbench/director-tool-loop/v0.1")
        self.assertEqual(loop["status"], "completed")
        self.assertGreaterEqual(len(loop["steps"]), 2)
        self.assertEqual(loop["steps"][0]["tool"], "run_workflow")
        self.assertIn("observation_before", loop["steps"][0])
        self.assertIn("observation_after", loop["steps"][0])
        self.assertIn("observe_agent_run", loop["steps"][0])
        self.assertIn("workflow_state", loop["steps"][0]["artifacts"])
        self.assertEqual(loop["steps"][-1]["tool"], "write_director_report")
        self.assertEqual(result.decision["tool_loop_status"], "completed")
        self.assertGreaterEqual(result.decision["tool_loop_step_count"], 2)
        self.assertTrue(any("run_workflow" in item for item in result.decision["tool_loop_summary"]))

    def test_director_persists_and_reuses_conversation_context(self):
        project = self.make_project()
        first = run_director_turn(project, "主角要保持冷静克制，但关系压力要越来越强", provider="dry-run", auto_execute=False)
        second = run_director_turn(project, "继续按刚才的方向推进人物关系", provider="dry-run", auto_execute=False)

        conversation = project / "director" / "conversation" / "turns.jsonl"
        self.assertTrue(conversation.exists())
        records = [json.loads(line) for line in conversation.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["run_id"], first.run_id)
        self.assertEqual(records[1]["run_id"], second.run_id)
        self.assertIn("冷静克制", records[0]["user_direction"])
        status = build_director_status(project)
        self.assertEqual(len(status["recent_conversation"]), 2)
        prompt = json.loads((second.agent_run_dir / "input.prompt.json").read_text(encoding="utf-8"))
        user_prompt = prompt["messages"][1]["content"]
        self.assertIn("recent_conversation", user_prompt)
        self.assertIn("冷静克制", user_prompt)

    def test_director_free_conversation_records_project_direction_memory(self):
        project = self.make_project()
        first = run_director_turn(project, "记住：整体基调要冷硬克制，不要爽文感，人物选择要有代价。", provider="dry-run")

        self.assertEqual(first.status, "executed")
        self.assertEqual(first.decision["intent"], "conversation")
        self.assertEqual(first.decision["chosen_workflow"], "none")
        self.assertIn("record_project_direction", first.decision["tool_loop_summary"][0])
        memory = project / "director" / "memory" / "project_direction.jsonl"
        digest = project / "director" / "memory" / "project_direction.md"
        self.assertTrue(memory.exists())
        self.assertTrue(digest.exists())
        records = [json.loads(line) for line in memory.read_text(encoding="utf-8").splitlines()]
        self.assertIn("冷硬克制", records[-1]["summary"])

        second = run_director_turn(project, "继续按刚才的气质推进。", provider="dry-run", auto_execute=False)
        prompt = json.loads((second.agent_run_dir / "input.prompt.json").read_text(encoding="utf-8"))
        user_prompt = prompt["messages"][1]["content"]
        self.assertIn("recent_project_directions", user_prompt)
        self.assertIn("冷硬克制", user_prompt)

    def test_http_chat_director_normalizes_llm_route_aliases(self):
        project = self.make_project()
        server = _FakeDirectorChatServer(_director_payload_with_aliases())
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
            result = run_director_turn(project, "规划城市档案悬疑下一步方向", provider="http-chat", auto_execute=False)

        self.assertEqual(result.status, "planned")
        self.assertEqual(result.decision["intent"], "character-lab")
        self.assertEqual(result.decision["chosen_workflow"], "character-lab")
        self.assertEqual(result.decision["actions"][0], "run_character-lab")
        self.assertIn("character_repair_agent", result.decision["delegated_to"][0])
        self.assertIn("是否确认", result.decision["user_visible_decisions"][0])
        validation = json.loads(result.validation_path.read_text(encoding="utf-8"))
        self.assertEqual(validation["status"], "pass")
        self.assertEqual(validation["error_count"], 0)
        prompt = json.loads((result.agent_run_dir / "input.prompt.json").read_text(encoding="utf-8"))
        self.assertEqual(prompt["provider"], "http-chat")
        self.assertEqual(prompt["model"], "fake-model")

    def test_director_status_uses_same_project_view(self):
        project = self.make_project()
        status = build_director_status(project)

        self.assertTrue(status["has_project"])
        self.assertIn("counts", status)
        self.assertEqual(status["counts"]["candidate_assets"], 0)

    def test_director_cli_command(self):
        project = self.make_project()
        self.assertIn("director-chat", build_parser().format_help())
        code = main(["director-chat", str(project), "--message", "生成角色关系方向", "--provider", "dry-run", "--no-execute"])
        self.assertEqual(code, 0)
        index = project / "director" / "runs" / "index.jsonl"
        self.assertTrue(index.exists())
        latest = json.loads(index.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(latest["chosen_workflow"], "character-lab")

    def test_director_can_run_scene_loop(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        result = run_director_turn(project, "推进并审查当前场景", provider="dry-run")

        self.assertEqual(result.decision["chosen_workflow"], "scene-loop")
        self.assertTrue(result.workflow_state_path.exists())


def _director_payload_with_aliases():
    return {
        "route": "character-lab",
        "rationale": "当前项目需要先统一城市档案悬疑的人物动机与关系压力。",
        "secondary_decisions": {
            "scope": "修复角色候选并建立关系图",
            "priority": "先角色后场景",
        },
        "delegated_specialist_agents": [
            {"agent": "character_repair_agent", "task": "修复不合格角色候选"},
            {"agent": "relationship_graph_agent", "task": "生成关系压力图"},
        ],
        "constraints": ["新角色只能先作为候选资产。"],
        "risks": ["用户方向仍然较宽，需要后续收束城市和案件类型。"],
        "user_visible_choices": ["是否确认城市档案悬疑作为正式方向？"],
    }


class _FakeDirectorChatServer:
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
