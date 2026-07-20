import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literary_engineering_workbench.api_server import _director_conversation, _record_approval, create_app
from literary_engineering_workbench.task_registry import issue_next_task

from helpers import TempProjectMixin, add_character, make_passing_scene, make_reviewed_passing_scene, prepare_formal_scene_flow


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
        make_reviewed_passing_scene(project, prepare_flow=False)
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
        self.assertNotIn("branch_agent_tasks", state_payload["artifacts"])
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

    def test_fastapi_workflow_dashboard_endpoint(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        project = self.make_project()
        make_reviewed_passing_scene(project, prepare_flow=False)
        app = create_app(allowed_roots=[project.parent])
        client = TestClient(app)

        response = client.get("/workflow/dashboard", params={"project_root": str(project)})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["dashboard"]["schema"], "literary-engineering-workbench/workflow-dashboard/v0.1")
        self.assertIn("summary", payload)
        self.assertIn("route_audits", payload)
        self.assertIn("next_actions", payload)
        self.assertEqual(payload["paths"]["json"], "workflow/dashboard/workflow_dashboard.json")
        self.assertTrue((project / payload["paths"]["json"]).exists())
        self.assertTrue((project / payload["paths"]["markdown"]).exists())
        self.assertTrue((project / payload["paths"]["html"]).exists())

    def test_fastapi_workflow_activity_endpoints(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        project = self.make_project()
        issued = issue_next_task(project, route="scene-development")
        app = create_app(allowed_roots=[project.parent])
        client = TestClient(app)

        activity = client.get("/workflow/activity", params={"project_root": str(project)})
        self.assertEqual(activity.status_code, 200)
        payload = activity.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema"], "literary-engineering-workbench/workflow-activity/v0.1")
        self.assertEqual(payload["active_task"]["task_id"], issued.task_id)
        self.assertIn("route_lanes", payload)
        self.assertIn("timeline", payload)

        package = client.get("/workflow/task-package", params={"project_root": str(project), "task_id": issued.task_id})
        self.assertEqual(package.status_code, 200)
        self.assertEqual(package.json()["schema"], "literary-engineering-workbench/task-package-summary/v0.1")
        self.assertEqual(package.json()["task"]["task_id"], issued.task_id)

        stream = client.get("/workflow/activity/stream", params={"project_root": str(project), "max_events": 1})
        self.assertEqual(stream.status_code, 200)
        self.assertIn("event: activity", stream.text)

        dashboard_stream = client.get("/workflow/dashboard/stream", params={"project_root": str(project), "max_events": 1})
        self.assertEqual(dashboard_stream.status_code, 200)
        self.assertIn("event: dashboard", dashboard_stream.text)

    def test_fastapi_project_library_and_human_choice_endpoints(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test client is not installed")

        project = self.make_project()
        add_character(project)
        make_passing_scene(project)
        prepare_formal_scene_flow(project)
        selection = project / "branches" / "scene_0001" / "branch_selection.md"
        selection.unlink()
        export_dir = project / "exports" / "chapter_0001"
        export_dir.mkdir(parents=True, exist_ok=True)
        chapter_readme = project / "drafts" / "chapters" / "README.md"
        chapter_readme.parent.mkdir(parents=True, exist_ok=True)
        chapter_readme.write_text("chapters\n\n章节级工作台和章节草稿放在这里。", encoding="utf-8")
        (export_dir / "chapter_0001_novel.md").write_text(
            "# 第一章\n\n林舟把已经完成的章节正文放在桌上。\n\n## 工作流程\n\n- scene_0001 已处理。",
            encoding="utf-8",
        )
        canon_dir = project / "canon" / "patches"
        canon_dir.mkdir(parents=True, exist_ok=True)
        (canon_dir / "scene_0001_canon_patch.json").write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/canon-patch/v0.1",
                    "scene_id": "scene_0001",
                    "canon_change": True,
                    "items": [{"type": "world_rule", "content": "林舟所在城市禁止公开讨论旧案。"}],
                    "source": "drafts/scenes/scene_0001.md",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        app = create_app(allowed_roots=[project.parent])
        client = TestClient(app)

        library = client.get("/project/library", params={"project_root": str(project)})
        self.assertEqual(library.status_code, 200)
        payload = library.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema"], "literary-engineering-workbench/project-library/v0.1")
        self.assertGreaterEqual(payload["counts"]["drafts"], 1)
        self.assertGreaterEqual(payload["counts"]["characters"], 1)
        draft_body = payload["sections"]["drafts"][0]["body"]
        self.assertNotIn("scene_id", draft_body)
        self.assertNotIn("状态变化候选", draft_body)
        self.assertIn("林舟", draft_body)
        completed = payload["completed_prose"]
        self.assertEqual(completed["status"], "available")
        self.assertGreaterEqual(completed["count"], 1)
        self.assertGreater(completed["total_chinese_content_chars"], 0)
        completed_paths = [item["path"] for item in completed["items"]]
        self.assertNotIn("drafts/chapters/README.md", completed_paths)
        self.assertEqual(completed["items"][0]["status"], "exported")
        self.assertIn("林舟", completed["items"][0]["body"])
        self.assertNotIn("#", completed["items"][0]["body"])
        self.assertNotIn("scene_0001", completed["items"][0]["body"])
        self.assertTrue(payload["sections"]["characters"][0]["key_points"])
        self.assertTrue(payload["sections"]["canon_patches"][0]["key_points"])

        stream = client.get("/project/library/stream", params={"project_root": str(project), "max_events": 1})
        self.assertEqual(stream.status_code, 200)
        self.assertIn("event: library", stream.text)

        item = client.get(
            "/project/library/item",
            params={"project_root": str(project), "kind": "characters", "item_id": "linzhou"},
        )
        self.assertEqual(item.status_code, 200)
        self.assertEqual(item.json()["item"]["title"], "林舟")

        schema = client.get("/project/editable-schema", params={"project_root": str(project)})
        self.assertEqual(schema.status_code, 200)
        self.assertIn("workflow/ui_overrides.json", json.dumps(schema.json(), ensure_ascii=False))

        edited = client.patch(
            "/project/display-field",
            json={
                "project_root": str(project),
                "target_type": "characters",
                "target_id": "linzhou",
                "field": "display_summary",
                "value": "前端包装后的角色摘要。",
            },
        )
        self.assertEqual(edited.status_code, 200)
        self.assertTrue((project / edited.json()["path"]).exists())

        noted = client.post(
            "/project/ui-note",
            json={
                "project_root": str(project),
                "target_type": "characters",
                "target_id": "linzhou",
                "note": "后续让他的选择更谨慎。",
            },
        )
        self.assertEqual(noted.status_code, 200)
        self.assertTrue((project / noted.json()["note_path"]).exists())

        choices = client.get("/workflow/current-choice", params={"project_root": str(project)})
        self.assertEqual(choices.status_code, 200)
        choice_payload = choices.json()
        self.assertTrue(any(item["decision_type"] == "branch_selection" for item in choice_payload["choices"]))
        self.assertTrue(any(item["decision_type"] == "canon_patch_approval" for item in choice_payload["choices"]))
        branch_choice = next(item for item in choice_payload["choices"] if item["decision_type"] == "branch_selection")

        recorded = client.post(
            "/workflow/human-choice",
            json={
                "project_root": str(project),
                "choice_id": branch_choice["choice_id"],
                "route": branch_choice["route"],
                "decision_type": "branch_selection",
                "target": branch_choice["target"],
                "options": branch_choice["options"],
                "selected": branch_choice["options"][0]["id"],
                "rationale": "测试中选择角色行为更稳的分支。",
            },
        )
        self.assertEqual(recorded.status_code, 200)
        self.assertEqual(recorded.json()["choice"]["decision_type"], "branch_selection")
        self.assertEqual(recorded.json()["materialized"], "branches/scene_0001/branch_selection.md")
        self.assertTrue(selection.exists())
        selection_text = selection.read_text(encoding="utf-8")
        self.assertIn("decision: selected", selection_text)
        self.assertIn("selected_branch:", selection_text)

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
                self.assertIn("项目总控", ui.text)
                self.assertIn("任务推进", ui.text)
                self.assertIn("作品档案", ui.text)
                self.assertIn("文风挂载", ui.text)
                self.assertIn("连接设置", ui.text)
                self.assertIn("已完成正文", ui.text)
                self.assertIn("滑动阅览框", ui.text)
                self.assertIn("这里不会把机器记录原样摊开", ui.text)
                self.assertIn("流程证据柜", ui.text)
                self.assertIn("当前任务灯塔", ui.text)
                self.assertIn("assets/editorial-icons/dashboard-board.png", ui.text)
                self.assertIn("需要你决定的节点", ui.text)
                self.assertIn("搜索人物、场景、关键词", ui.text)
                self.assertIn("状态筛选", ui.text)
                self.assertIn("合并相似条目", ui.text)
                self.assertIn("我的备注", ui.text)
                self.assertIn("可挂载文风", ui.text)
                self.assertNotIn('data-view="config"', ui.text)
                self.assertNotIn("模型配置", ui.text)
                self.assertIn("机器记录已包装成证据卡", ui.text)
                self.assertNotIn("创作总监", ui.text)
                self.assertNotIn("Dashboard JSON", ui.text)
                icon = client.get("/ui/assets/editorial-icons/dashboard-board.png")
                self.assertEqual(icon.status_code, 200)
                self.assertEqual(icon.headers["content-type"], "image/png")
                self.assertTrue(icon.content.startswith(b"\x89PNG"))
                self.assertNotIn("设定工坊", ui.text)

                script = client.get("/ui/app.js")
                self.assertEqual(script.status_code, 200)
                self.assertIn("localStorage", script.text)
                self.assertIn("/workflow/dashboard", script.text)
                self.assertIn("/workflow/dashboard/stream", script.text)
                self.assertIn("/workflow/activity", script.text)
                self.assertIn("/workflow/task-package", script.text)
                self.assertIn("/project/library", script.text)
                self.assertIn("/workflow/current-choice", script.text)
                self.assertIn("/workflow/human-choice", script.text)
                self.assertIn("/project/display-field", script.text)
                self.assertIn("/project/ui-note", script.text)
                self.assertIn("renderDashboardProse", script.text)
                self.assertIn("openLibraryDrafts", script.text)
                self.assertIn("/style-lab/mounts", script.text)
                self.assertIn("/style-lab/library", script.text)
                self.assertIn("/style-lab/mount", script.text)
                self.assertIn("friendlyMessage", script.text)
                self.assertNotIn("/director/chat", script.text)
                self.assertNotIn("/style-lab/compile", script.text)
                self.assertNotIn("/asset/create", script.text)
                self.assertIn("api_key", script.text)
                self.assertNotIn("addDirectorMessage", script.text)
                self.assertNotIn("JSON.stringify(value, null, 2)", script.text)

                style = client.get("/ui/styles.css")
                self.assertEqual(style.status_code, 200)
                self.assertIn(".completed-preview", style.text)
                self.assertIn(".reader-body", style.text)
                self.assertIn(".task-beacon", style.text)
                self.assertIn(".route-lane", style.text)
                self.assertIn(".key-points", style.text)
                self.assertIn("overflow-y: auto", style.text)

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
                                "api_key": "dummy-front-end-key",
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
                self.assertNotIn("dummy-front-end-key", json.dumps(saved.json(), ensure_ascii=False))
                stored = json.loads(config.read_text(encoding="utf-8"))
                self.assertEqual(stored["profiles"]["deepseek"]["api_key"], "dummy-front-end-key")

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
                self.assertEqual(stored_after_blank["profiles"]["deepseek"]["api_key"], "dummy-front-end-key")

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
        self.assertEqual(promoted.status_code, 400)

        with patch.dict("os.environ", {"LEW_MAINTAINER_MODE": "1"}):
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

        unauthorized_dashboard = client.get("/workflow/dashboard", params={"project_root": str(project)})
        self.assertEqual(unauthorized_dashboard.status_code, 401)

        authorized_dashboard = client.get(
            "/workflow/dashboard",
            headers={"X-LEW-API-Token": "secret-token"},
            params={"project_root": str(project)},
        )
        self.assertEqual(authorized_dashboard.status_code, 200)


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

中文正文使用全角标点，省略号用“……”。句号用于真实语义、镜头或心理落点；逗号用于未完成关系；分号用于层级并列。正式正文原则上不用破折号，孤立破折号需逐句复核，超过约 2% 叙事单元密度或替代“而是/但是/于是”时必须修订。转折优先由动作、视线、意象、信息差和因果推进完成。

## 降低 AI 腔控制

机械“不是……而是……”“并非……而是……”以及“不是……——是……”等变体是核心禁区，不判断为合理修辞；若语料里有否定纠偏，只提取其认知二分、信息反转、讽刺顿挫或叙述者纠偏功能，改写为动作、事实顺序、信息差或直接陈述。抽象总结、解释性心理标签、模板化转折、器官轮岗、万能占位、比喻依赖、对称排比和结尾金句按约 2% 叙事单元密度门禁控制。人物认知变化应通过动作、停顿、回避、误判、语气和对白潜台词呈现。

## 禁止倾向与自检

不得摘抄原文、堆叠高频词、把候选事实写成 canon、用密集句号或破折号伪装文学性。输出前检查叙述距离是否稳定，意象是否服务人物状态，标点是否服务节奏，AI 腔风险是否低于 2% 密度门禁，文本是否仍服从项目事实。
"""


if __name__ == "__main__":
    unittest.main()
