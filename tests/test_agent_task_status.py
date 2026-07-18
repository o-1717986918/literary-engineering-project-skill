import json
import unittest
from pathlib import Path

from literary_engineering_workbench.agent_task_status import build_agent_task_status, build_route_audit
from literary_engineering_workbench.branch_lab import build_branch_simulation
from literary_engineering_workbench.cli import build_parser
from literary_engineering_workbench.scene_composer import build_scene_composition

from helpers import TempProjectMixin, add_character, make_reviewed_passing_scene, write_platform_scene_review


class AgentTaskStatusTests(TempProjectMixin, unittest.TestCase):
    def test_scans_pending_and_completed_sidecars(self):
        project = self.make_project()
        task = project / "drafts" / "candidates" / "scene_0001-platform-agent.agent_tasks.md"
        task.parent.mkdir(parents=True, exist_ok=True)
        task.write_text(
            """# 平台 Agent 任务说明：platform scene generation scene_0001

## Source Artifacts

- `scenes/scene_0001.yaml`

## Tasks

[AGENT_TASK: 创建或覆盖 `drafts/candidates/scene_0001-platform-agent.md`。
创建或覆盖 `drafts/candidates/scene_0001-platform-agent.json`。]
""",
            encoding="utf-8",
        )

        pending = build_agent_task_status(project)
        self.assertEqual(pending.task_count, 1)
        self.assertEqual(pending.pending_count, 1)
        payload = json.loads(pending.json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["tasks"][0]["route"], "scene-development")
        self.assertEqual(len(payload["tasks"][0]["missing_expected_paths"]), 2)

        (project / "drafts" / "candidates" / "scene_0001-platform-agent.md").write_text("done", encoding="utf-8")
        (project / "drafts" / "candidates" / "scene_0001-platform-agent.json").write_text("{}", encoding="utf-8")
        complete = build_agent_task_status(project)

        self.assertEqual(complete.complete_count, 1)
        self.assertEqual(complete.missing_expected_count, 0)

    def test_route_audit_reports_pending_sidecars(self):
        project = self.make_project()
        task = project / "branches" / "scene_0001" / "branch_manifest.agent_tasks.md"
        task.parent.mkdir(parents=True, exist_ok=True)
        task.write_text(
            """# 平台 Agent 任务说明：branch review

## Source Artifacts

- `scenes/scene_0001.yaml`

## Tasks

[AGENT_TASK: 创建或覆盖 `branches/scene_0001/branch_selection.md`。]
""",
            encoding="utf-8",
        )

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertGreater(result.blocking_count, 0)
        self.assertTrue(any(gate["key"] == "scene-sidecars-handled" and gate["status"] == "fail" for gate in payload["gates"]))

    def test_route_audit_reports_unresolved_review_notes(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        write_platform_scene_review(project, conclusion="pass_with_notes")

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertTrue(any(gate["key"] == "scene-review-notes-resolved" and gate["status"] == "fail" for gate in payload["gates"]))

        revision_dir = project / "drafts" / "revisions"
        revision_dir.mkdir(parents=True, exist_ok=True)
        (revision_dir / "scene_0001_revision_report.md").write_text("waiver recorded", encoding="utf-8")
        (revision_dir / "scene_0001_revision.json").write_text("{}", encoding="utf-8")
        resolved = build_route_audit(project, route="scene-development")
        resolved_payload = json.loads(resolved.json_path.read_text(encoding="utf-8"))

        self.assertTrue(any(gate["key"] == "scene-review-notes-resolved" and gate["status"] == "pass" for gate in resolved_payload["gates"]))

    def test_route_audit_reports_missing_scene_flow_artifacts(self):
        project = self.make_project()

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        failing_keys = {gate["key"] for gate in payload["gates"] if gate["status"] == "fail"}
        self.assertIn("scene_0001:roleplay-simulation", failing_keys)
        self.assertIn("scene_0001:branch-manifest", failing_keys)
        self.assertIn("scene_0001:branch-selection", failing_keys)
        self.assertIn("scene_0001:composition-ready", failing_keys)

    def test_route_audit_passes_scene_flow_after_rp_branch_and_composition(self):
        project = self.make_project()
        add_character(project)
        make_reviewed_passing_scene(project)
        roleplay = project / "branches" / "scene_0001" / "roleplay_simulation.md"
        roleplay.parent.mkdir(parents=True, exist_ok=True)
        roleplay.write_text(
            "# 角色推演实验室：scene_0001\n\n### 读取回执\n\n- 已读取：scenes/scene_0001.yaml\n- 写回边界：候选。\n",
            encoding="utf-8",
        )
        branch = build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=3)
        _select_branch(branch.selection_path, branch.recommended_branch)
        build_scene_composition(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True)

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        blocking_failures = [gate for gate in payload["gates"] if gate["severity"] == "blocking" and gate["status"] == "fail"]

        self.assertEqual(blocking_failures, [])

    def test_route_audit_blocks_mounted_style_without_style_adherence(self):
        project = self.make_project()
        add_character(project)
        make_reviewed_passing_scene(project)
        _mount_style(project)
        _write_roleplay_receipt(project)
        branch = build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=3)
        _select_branch(branch.selection_path, branch.recommended_branch)
        build_scene_composition(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True)

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertTrue(
            any(gate["key"] == "scene_0001:style-adherence-review" and gate["status"] == "fail" for gate in payload["gates"])
        )

    def test_route_audit_accepts_mounted_style_adherence_pass(self):
        project = self.make_project()
        add_character(project)
        _mount_style(project)
        make_reviewed_passing_scene(project)
        _write_roleplay_receipt(project)
        branch = build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=3)
        _select_branch(branch.selection_path, branch.recommended_branch)
        build_scene_composition(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True)

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertTrue(
            any(gate["key"] == "scene_0001:style-adherence-review" and gate["status"] == "pass" for gate in payload["gates"])
        )

    def test_route_audit_reports_promotion_without_candidate_review(self):
        project = self.make_project()
        promotion_dir = project / "drafts" / "promotions"
        candidate_dir = project / "drafts" / "candidates"
        promotion_dir.mkdir(parents=True, exist_ok=True)
        candidate_dir.mkdir(parents=True, exist_ok=True)
        (candidate_dir / "scene_0001-platform-agent.md").write_text("## 正文候选\n\n测试。\n", encoding="utf-8")
        (promotion_dir / "scene_0001_promotion.json").write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/candidate-promotion/v0.1",
                    "scene_id": "scene_0001",
                    "candidate": "drafts/candidates/scene_0001-platform-agent.md",
                    "draft": "drafts/scenes/scene_0001.md",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertTrue(
            any(gate["key"] == "scene_0001:promotion-candidate-review" and gate["status"] == "fail" for gate in payload["gates"])
        )

    def test_cli_exposes_task_status_commands(self):
        help_text = build_parser().format_help()
        self.assertIn("agent-task-status", help_text)
        self.assertIn("route-audit", help_text)


def _select_branch(path: Path, branch_id: str):
    path.write_text(
        f"""# Branch Selection：scene_0001

## 人工决定

- decision: selected
- selected_branch: {branch_id}
- reviewer: platform-agent-test
- selected_at: 2026-01-01T00:00:00Z
""",
        encoding="utf-8",
    )


def _write_roleplay_receipt(project: Path):
    roleplay = project / "branches" / "scene_0001" / "roleplay_simulation.md"
    roleplay.parent.mkdir(parents=True, exist_ok=True)
    roleplay.write_text(
        "# 角色推演实验室：scene_0001\n\n### 读取回执\n\n- 已读取：scenes/scene_0001.yaml\n- 写回边界：候选。\n",
        encoding="utf-8",
    )


def _mount_style(project: Path):
    mounted = project / "style" / "mounted" / "test-style"
    mounted.mkdir(parents=True, exist_ok=True)
    (mounted / "prompt.md").write_text(
        "保持低位叙述距离、动作先于解释、标点停顿克制，避免模板化转折和空泛主题总结。",
        encoding="utf-8",
    )
    active = project / "style" / "active_style_skill.json"
    active.write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/active-style-skill/v0.1",
                "style_id": "test-style",
                "prompt": "style/mounted/test-style/prompt.md",
                "mount_path": "style/mounted/test-style",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
