import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literary_engineering_workbench.api_server import _director_conversation, _record_approval, create_app

from helpers import TempProjectMixin, make_reviewed_passing_scene


class ApiServerTests(TempProjectMixin, unittest.TestCase):
    def test_records_approval_without_fastapi_dependency(self):
        project = self.make_project()
        path = _record_approval(project, "run-demo", "approve", actor="tester", notes="ok")
        self.assertTrue(path.exists())
        record = json.loads(path.read_text(encoding="utf-8").strip())
        self.assertEqual(record["decision"], "approve")

    def test_fastapi_workflow_run_endpoint(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        project = self.make_project()
        make_reviewed_passing_scene(project)
        app = create_app(allowed_roots=[project.parent])
        client = TestClient(app)

        health = client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["ok"])
        self.assertFalse(health.json()["auth_required"])

        run = client.post(
            "/workflow/run",
            json={
                "project_root": str(project),
                "mode": "scene-loop",
                "scene": "scenes/scene_0001.yaml",
                "generate_candidate": True,
                "agent_tasks": True,
                "provider": "dry-run",
            },
        )
        self.assertEqual(run.status_code, 200)
        run_payload = run.json()
        self.assertIn("run_id", run_payload)

        state = client.get(f"/workflow/runs/{run_payload['run_id']}", params={"project_root": str(project)})
        self.assertEqual(state.status_code, 200)
        state_payload = state.json()
        self.assertEqual(state_payload["run_id"], run_payload["run_id"])
        self.assertEqual(state_payload["status"], "blocked")
        self.assertIn("simulation_agent_tasks", state_payload["artifacts"])
        self.assertIn("branch_agent_tasks", state_payload["artifacts"])
        self.assertNotIn("candidate_agent_tasks", state_payload["artifacts"])
        self.assertTrue((project / state_payload["artifacts"]["simulation_agent_tasks"]).exists())

        approval = client.post(
            "/workflow/approve",
            json={
                "project_root": str(project),
                "run_id": run_payload["run_id"],
                "decision": "revise",
                "actor": "tester",
                "notes": "继续修订。",
            },
        )
        self.assertEqual(approval.status_code, 200)
        self.assertTrue((project / approval.json()["approval_path"]).exists())
        self.assertTrue((project / approval.json()["task_path"]).exists())

    def test_fastapi_agent_run_endpoint(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        project = self.make_project()
        app = create_app(allowed_roots=[project.parent])
        client = TestClient(app)

        run = client.post(
            "/agent/run",
            json={
                "project_root": str(project),
                "agent_id": "api-reviewer",
                "task": "api-agent-test",
                "system_prompt": "system",
                "user_prompt": "user",
                "provider": "dry-run",
                "out_dir": "agents/runs/api-agent-test",
            },
        )
        self.assertEqual(run.status_code, 200)
        payload = run.json()
        self.assertEqual(payload["run_id"], "api-agent-test")

        state = client.get(f"/agent/runs/{payload['run_id']}", params={"project_root": str(project)})
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.json()["parsed_output"]["agent_id"], "api-reviewer")

    def test_fastapi_frontend_and_global_config_endpoints(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "lew-config.json"
            with patch.dict("os.environ", {"LEW_CONFIG_PATH": str(config)}, clear=False):
                project = self.make_project()
                app = create_app(allowed_roots=[project.parent])
                client = TestClient(app)

                ui = client.get("/")
                self.assertEqual(ui.status_code, 200)
                self.assertIn("文学工程控制台", ui.text)
                self.assertIn('value="auto"', ui.text)
                self.assertIn("创作总监", ui.text)
                self.assertIn("文风学习", ui.text)
                self.assertIn("全局配置", ui.text)
                self.assertIn("高级设置", ui.text)
                self.assertIn("留空可从一句话新建项目", ui.text)
                self.assertNotIn("设定工坊", ui.text)

                script = client.get("/ui/app.js")
                self.assertEqual(script.status_code, 200)
                self.assertIn("localStorage", script.text)
                self.assertIn("/director/chat", script.text)
                self.assertIn("/style-lab/compile", script.text)
                self.assertNotIn("/asset/create", script.text)
                self.assertIn("api_key", script.text)
                self.assertIn("addDirectorMessage", script.text)
                self.assertIn("conversation", script.text)

                cfg = client.get("/config")
                self.assertEqual(cfg.status_code, 200)
                self.assertEqual(cfg.json()["active_profile"], "deepseek")

                saved = client.post(
                    "/config",
                    json={
                        "active_profile": "deepseek",
                        "profiles": {
                            "deepseek": {
                                "provider": "http-chat",
                                "api_base": "https://api.deepseek.com",
                                "model": "deepseek-v4-flash",
                                "api_key_env": "DEEPSEEK_API_KEY",
                                "api_key": "front-end-secret",
                                "temperature": 0.2,
                                "max_tokens": 3000,
                                "timeout": 90,
                            }
                        },
                        "defaults": {"project_root": str(project), "style_library_root": str(Path(tmp) / "styles")},
                    },
                )
                self.assertEqual(saved.status_code, 200)
                self.assertEqual(saved.json()["effective"]["defaults"]["project_root"], str(project))
                self.assertEqual(saved.json()["effective"]["defaults"]["style_library_root"], str(Path(tmp) / "styles"))
                self.assertTrue(saved.json()["effective"]["api_key_available"])
                self.assertTrue(saved.json()["effective"]["profiles"]["deepseek"]["api_key_set"])
                self.assertNotIn("front-end-secret", json.dumps(saved.json(), ensure_ascii=False))
                stored = json.loads(config.read_text(encoding="utf-8"))
                self.assertEqual(stored["profiles"]["deepseek"]["api_key"], "front-end-secret")

                preserved = client.post(
                    "/config",
                    json={
                        "active_profile": "deepseek",
                        "profiles": {
                            "deepseek": {
                                "provider": "http-chat",
                                "api_base": "https://api.deepseek.com",
                                "model": "deepseek-v4-flash",
                                "api_key_env": "DEEPSEEK_API_KEY",
                                "api_key": "",
                                "temperature": 0.2,
                                "max_tokens": 3000,
                                "timeout": 90,
                            }
                        },
                        "defaults": {"project_root": str(project), "style_library_root": str(Path(tmp) / "styles")},
                    },
                )
                self.assertEqual(preserved.status_code, 200)
                stored_after_blank = json.loads(config.read_text(encoding="utf-8"))
                self.assertEqual(stored_after_blank["profiles"]["deepseek"]["api_key"], "front-end-secret")

                connection_without_root = client.post(
                    "/assistant/chat",
                    json={"message": "测试模型连接"},
                )
                self.assertEqual(connection_without_root.status_code, 400)

    def test_fastapi_style_lab_endpoints(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project()
            library = Path(tmp) / "style-library"
            app = create_app(allowed_roots=[project.parent])
            client = TestClient(app)

            author = client.post(
                "/style-lab/author",
                json={
                    "style_library_root": str(library),
                    "name": "测试作家",
                    "author_id": "demo-author",
                    "source_note": "测试语料",
                },
            )
            self.assertEqual(author.status_code, 200)
            self.assertEqual(author.json()["author_id"], "demo-author")

            work = client.post(
                "/style-lab/work",
                json={
                    "style_library_root": str(library),
                    "author_id": "demo-author",
                    "title": "测试作品",
                    "work_id": "demo-work",
                },
            )
            self.assertEqual(work.status_code, 200)

            imported = client.post(
                "/style-lab/import-source",
                json={
                    "style_library_root": str(library),
                    "author_id": "demo-author",
                    "work_id": "demo-work",
                    "text": "雨落旧城。灯影摇晃。人们沉默。门外传来细小的脚步声。",
                    "filename": "sample.txt",
                },
            )
            self.assertEqual(imported.status_code, 200)
            self.assertGreater(imported.json()["char_count"], 0)

            compiled = client.post(
                "/style-lab/compile",
                json={
                    "style_library_root": str(library),
                    "author_id": "demo-author",
                    "profile_id": "default",
                    "provider": "dry-run",
                },
            )
            self.assertEqual(compiled.status_code, 200)
            compiled_payload = compiled.json()
            self.assertEqual(compiled_payload["receiver"], "platform-agent")
            self.assertTrue((library / compiled_payload["style_prompt_task"]).exists())
            expected_prompt = library / compiled_payload["expected_style_prompt"]
            expected_json = library / compiled_payload["expected_json"]
            expected_prompt.write_text(_valid_style_prompt_text(), encoding="utf-8")
            expected_json.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/style-prompt-agent/v1",
                        "prompt_markdown": "style_prompt.md",
                        "constraints": ["测试约束"],
                        "avoid": [],
                        "source_paths": ["style-profile.md", "style_metrics.json"],
                        "evaluation_plan": ["back-translation"],
                        "risk_notes": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            evaluated = client.post(
                "/style-lab/evaluate",
                json={
                    "style_library_root": str(library),
                    "author_id": "demo-author",
                    "profile_id": "default",
                    "reference_text": "雨落旧城。灯影摇晃。人们沉默。",
                    "task_input_text": "Rain fell on the old city. The lights trembled.",
                    "mode": "back-translation",
                    "provider": "dry-run",
                },
            )
            self.assertEqual(evaluated.status_code, 200)
            evaluated_payload = evaluated.json()
            self.assertEqual(evaluated_payload["receiver"], "platform-agent")
            self.assertTrue((library / evaluated_payload["style_prompt_eval_task"]).exists())
            eval_dir = expected_prompt.parent / "evaluation_results" / "back-translation"
            eval_dir.mkdir(parents=True, exist_ok=True)
            (eval_dir / "style_eval_ready.json").write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/style-eval/v0.1",
                        "mode": "back-translation",
                        "overall_score": 72.0,
                        "risk_level": "normal",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            skill = client.post(
                "/style-lab/build-skill",
                json={
                    "style_library_root": str(library),
                    "author_id": "demo-author",
                    "profile_id": "default",
                },
            )
            self.assertEqual(skill.status_code, 200)

            mounted = client.post(
                "/style-lab/mount",
                json={
                    "project_root": str(project),
                    "style_library_root": str(library),
                    "style_id": skill.json()["style_id"],
                },
            )
            self.assertEqual(mounted.status_code, 200)
            self.assertEqual(mounted.json()["active_style_skill"]["priority"], "highest")
            self.assertTrue(mounted.json()["active_style_skill"]["readiness"]["ready"])

            status = client.get("/style-lab/mounts", params={"project_root": str(project)})
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["active_style_skill"]["style_id"], skill.json()["style_id"])

    def test_fastapi_director_chat_endpoint(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        project = self.make_project()
        app = create_app(allowed_roots=[project.parent])
        client = TestClient(app)

        planned = client.post(
            "/director/chat",
            json={
                "project_root": str(project),
                "message": "只规划角色关系和背景压力",
                "provider": "dry-run",
                "auto_execute": False,
            },
        )
        self.assertEqual(planned.status_code, 200)
        payload = planned.json()
        self.assertEqual(payload["action"], "director-chat")
        self.assertEqual(payload["data"]["status"], "planned")
        self.assertEqual(payload["data"]["decision_payload"]["chosen_workflow"], "character-lab")
        self.assertEqual(payload["data"]["decision_payload"]["tool_loop_status"], "planned")
        self.assertTrue((project / payload["data"]["tool_loop"]).exists())
        self.assertTrue((project / payload["data"]["decision"]).exists())
        self.assertIn("conversation", payload)
        self.assertEqual(payload["conversation"]["speaker"], "创作总监")
        self.assertIn("headline", payload["conversation"])
        self.assertNotIn("内部任务", payload["conversation"]["message"])
        self.assertNotIn("审计记录", payload["conversation"]["message"])
        self.assertIsInstance(payload["conversation"]["next_questions"], list)
        self.assertIsInstance(payload["conversation"]["will_handle"], list)
        self.assertEqual(payload["conversation"]["audit"]["run_id"], payload["data"]["run_id"])
        self.assertEqual(payload["conversation"]["audit"]["workflow"], "character-lab")
        self.assertEqual(payload["conversation"]["audit"]["tool_loop"], payload["data"]["tool_loop"])
        self.assertNotIn("project_yaml", json.dumps(payload["conversation"], ensure_ascii=False))

        status = client.get("/director/status", params={"project_root": str(project)})
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["counts"]["director_runs"], 1)
        self.assertEqual(len(status.json()["recent_conversation"]), 1)

    def test_fastapi_director_chat_can_bootstrap_project_from_one_sentence(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "lew-config.json"
            allowed = Path(tmp) / "allowed"
            allowed.mkdir()
            with patch.dict("os.environ", {"LEW_CONFIG_PATH": str(config)}, clear=False):
                app = create_app(allowed_roots=[allowed])
                client = TestClient(app)

                response = client.post(
                    "/director/chat",
                    json={
                        "project_root": "",
                        "message": "一句话生成一个完整文学项目：严肃悬疑伪纪录长篇，主角逐渐发现自己参与过核心罪案。",
                        "provider": "dry-run",
                        "auto_execute": False,
                    },
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                project = Path(payload["data"]["project_root"])
                self.assertTrue(payload["data"]["project_created"])
                self.assertTrue((project / "project.yaml").exists())
                self.assertTrue((project / payload["data"]["project_bootstrap"]).exists())
                self.assertEqual(payload["data"]["decision_payload"]["director_tools"][0]["tool"], "run_workflow")
                self.assertNotIn("project_yaml", json.dumps(payload["conversation"], ensure_ascii=False))

    def test_fastapi_director_chat_free_conversation_records_memory(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        project = self.make_project()
        app = create_app(allowed_roots=[project.parent])
        client = TestClient(app)

        response = client.post(
            "/director/chat",
            json={
                "project_root": str(project),
                "message": "记住：整体气质要冷硬克制，不要爽文感。",
                "provider": "dry-run",
                "auto_execute": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["decision_payload"]["intent"], "conversation")
        self.assertEqual(payload["conversation"]["headline"], "我已记住这个创作方向")
        self.assertIn("冷硬克制", payload["conversation"]["message"])
        self.assertIn("项目方向记忆", payload["conversation"]["message"])
        self.assertTrue((project / "director" / "memory" / "project_direction.jsonl").exists())
        self.assertNotIn("project_yaml", json.dumps(payload["conversation"], ensure_ascii=False))

    def test_director_conversation_hides_internal_decision_language(self):
        project = self.make_project()
        result = SimpleNamespace(
            decision={
                "chosen_workflow": "project-seeding",
                "auto_execute": False,
                "provider": "http-chat",
                "user_visible_decisions": [
                    "Approve or reject the world rules candidate.",
                    "Approve or reject the protagonist profile.",
                ],
                "secondary_decisions": ["run_project-seeding", "schema_gate_specialist_outputs"],
            },
            status="planned",
            run_id="run-demo",
            report_path=project / "director" / "runs" / "run-demo" / "director_report.md",
            validation_path=project / "director" / "runs" / "run-demo" / "agent_decision" / "schema_validation.json",
            workflow_state_path=None,
        )

        conversation = _director_conversation(result, project)
        visible = json.dumps(conversation, ensure_ascii=False)
        self.assertEqual(conversation["speaker"], "创作总监")
        self.assertNotIn("Approve", visible)
        self.assertNotIn("run_project", visible)
        self.assertNotIn("schema_gate", visible)
        self.assertIn("题材气质", " ".join(conversation["next_questions"]))

    def test_fastapi_director_chat_default_provider_requires_real_llm_config(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "lew-config.json"
            with patch.dict(
                "os.environ",
                {
                    "LEW_CONFIG_PATH": str(config),
                    "LEW_MODEL_API_BASE": "",
                    "LEW_MODEL_NAME": "",
                    "LEW_MODEL_API_KEY": "",
                    "DEEPSEEK_API_KEY": "",
                },
                clear=False,
            ):
                project = self.make_project()
                app = create_app(allowed_roots=[project.parent])
                client = TestClient(app)

                response = client.post(
                    "/director/chat",
                    json={
                        "project_root": str(project),
                        "message": "推进角色和世界观",
                        "auto_execute": False,
                    },
                )

        self.assertEqual(response.status_code, 400)
        self.assertIn("provider=auto", response.json()["detail"])

    def test_fastapi_asset_workshop_endpoints(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        project = self.make_project()
        app = create_app(allowed_roots=[project.parent])
        client = TestClient(app)

        created = client.post(
            "/asset/create",
            json={
                "project_root": str(project),
                "asset_type": "character",
                "brief": "谨慎的调查者",
                "target_id": "linzhou",
                "provider": "dry-run",
            },
        )
        self.assertEqual(created.status_code, 200)
        candidate = created.json()["candidate"]

        listed = client.get("/asset/candidates", params={"project_root": str(project), "asset_type": "character"})
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["count"], 1)

        reviewed = client.post(
            "/asset/review",
            json={"project_root": str(project), "candidate": candidate, "provider": "dry-run"},
        )
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.json()["status"], "pass")

        blocked = client.post(
            "/asset/promote",
            json={"project_root": str(project), "candidate": candidate, "group": "character"},
        )
        self.assertEqual(blocked.status_code, 400)

        promoted = client.post(
            "/asset/promote",
            json={"project_root": str(project), "candidate": candidate, "group": "character", "allow_unapproved": True},
        )
        self.assertEqual(promoted.status_code, 200)
        self.assertTrue((project / "characters" / "linzhou.yaml").exists())

    def test_fastapi_workflow_endpoints_require_token_when_configured(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        project = self.make_project()
        make_reviewed_passing_scene(project)
        app = create_app(allowed_roots=[project.parent], api_token="secret-token")
        client = TestClient(app)

        health = client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["auth_required"])

        unauthorized = client.post(
            "/workflow/run",
            json={
                "project_root": str(project),
                "mode": "scene-loop",
                "scene": "scenes/scene_0001.yaml",
            },
        )
        self.assertEqual(unauthorized.status_code, 401)

        authorized = client.post(
            "/workflow/run",
            headers={"Authorization": "Bearer secret-token"},
            json={
                "project_root": str(project),
                "mode": "scene-loop",
                "scene": "scenes/scene_0001.yaml",
            },
        )
        self.assertEqual(authorized.status_code, 200)
        run_payload = authorized.json()

        state = client.get(
            f"/workflow/runs/{run_payload['run_id']}",
            headers={"X-LEW-API-Token": "secret-token"},
            params={"project_root": str(project)},
        )
        self.assertEqual(state.status_code, 200)


def _valid_style_prompt_text() -> str:
    return """# LLM 文风约束提示词

## 使用身份

你是长篇虚构文本生成 LLM。写作时先执行本文风约束，再处理局部词汇和句子润色。本文件只约束表达层，不确认 canon，不新增人物事实，不替剧情解决因果问题。

## 核心风格机制

文风应从叙述距离、信息分配、句法重心、意象回环和心理呈现中形成。不要把风格理解成几个高频词，也不要复用原文连续片段。人物的隐藏背景只通过迟疑、回避、误判、沉默、动作折返和对白遮掩间接影响选择。

## 句法与节奏

句长和段长跟随人物注意力、场景压力和信息密度变化。紧张处可以短，但不能连续碎句；舒缓处可以长，但逗号必须承接未完成动作、感知、心理或因果关系。段落必须承担推进事件、暴露关系、改变注意力或加深主题中的一种功能。

## 意象、对白和动作

意象从场景物理空间和人物处境中生长，重复意象必须带来关系或认知变化。对白要带有信息差和关系压力，避免直接朗读设定。动作描写体现目标、恐惧、道德边界和背景故事造成的选择惯性。

## 标点边界

中文正文使用全角标点，省略号用“……”，破折号用“——”。句号用于真实语义、镜头或心理落点；逗号用于未完成关系；分号用于层级并列；破折号只用于打断、插入、骤变或强解释性补充。转折优先由动作、视线、意象、信息差和因果推进完成。

## 降低 AI 腔控制

不要高频使用“不是……而是……”“并非……而是……”等机械对照句式。不要用抽象总结、解释性心理标签、模板化转折、对称排比或结尾金句替代具体叙事。人物认知变化应通过动作、停顿、回避、误判、语气和对白潜台词呈现。

## 禁止倾向与自检

不得摘抄原文、堆叠高频词、把候选事实写成 canon、用密集句号或破折号伪装文学性。输出前检查叙述距离是否稳定，意象是否服务人物状态，标点是否服务节奏，文本是否仍服从项目事实。
"""


if __name__ == "__main__":
    unittest.main()
