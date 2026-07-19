import json
import unittest
from pathlib import Path

from literary_engineering_workbench.agent_tasks import write_agent_completion_marker
from literary_engineering_workbench.agent_task_status import build_agent_task_status, build_route_audit
from literary_engineering_workbench.approval import record_workflow_approval
from literary_engineering_workbench.asset_workshop import create_asset_candidate, promote_candidate_asset
from literary_engineering_workbench.branch_lab import build_branch_simulation
from literary_engineering_workbench.candidate_promotion import promote_scene_candidate
from literary_engineering_workbench.canon_lint import build_canon_lint
from literary_engineering_workbench.character_state_evolver import build_character_state_patch
from literary_engineering_workbench.chapter_pipeline import build_chapter_workspace
from literary_engineering_workbench.cli import build_parser
from literary_engineering_workbench.context_packet import build_context_packet
from literary_engineering_workbench.export_package import build_export_package
from literary_engineering_workbench.longform_audit import build_longform_audit
from literary_engineering_workbench.platform_agent_tasks import (
    write_platform_asset_creation_task,
    write_platform_asset_review_task,
    write_platform_canon_review_task,
    write_platform_committee_task,
)
from literary_engineering_workbench.publish import publish_chapter
from literary_engineering_workbench.scene_composer import build_scene_composition

from helpers import TempProjectMixin, add_character, make_reviewed_passing_scene, write_formal_candidate_artifacts, write_platform_scene_review


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
        self.assertEqual(len(payload["tasks"][0]["missing_expected_paths"]), 3)

        (project / "drafts" / "candidates" / "scene_0001-platform-agent.md").write_text("done", encoding="utf-8")
        (project / "drafts" / "candidates" / "scene_0001-platform-agent.json").write_text("{}", encoding="utf-8")
        write_agent_completion_marker(task, root=project, handled_by="platform-agent-test")
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

    def test_route_audit_blocks_asset_without_review_approval_and_promotion(self):
        project = self.make_project()
        candidate = create_asset_candidate(project, asset_type="character", brief="谨慎调查者", target_id="linzhou", provider="dry-run")
        creation = write_platform_asset_creation_task(
            project,
            asset_type="character",
            brief="谨慎调查者",
            target_id="linzhou",
            candidate_path=candidate.candidate_path,
            report_path=candidate.report_path,
        )
        write_agent_completion_marker(creation.task_path, root=project, handled_by="platform-agent-test")

        result = build_route_audit(project, route="character-and-world-assets")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertGreater(result.blocking_count, 0)
        self.assertTrue(any(gate["key"].endswith(":asset-review-clean-pass") and gate["status"] == "fail" for gate in payload["gates"]))
        self.assertTrue(any(gate["key"].endswith(":asset-approval") and gate["status"] == "fail" for gate in payload["gates"]))

    def test_route_audit_passes_promoted_asset_route(self):
        project = self.make_project()
        candidate = create_asset_candidate(project, asset_type="character", brief="谨慎调查者", target_id="linzhou", provider="dry-run")
        creation = write_platform_asset_creation_task(
            project,
            asset_type="character",
            brief="谨慎调查者",
            target_id="linzhou",
            candidate_path=candidate.candidate_path,
            report_path=candidate.report_path,
        )
        write_agent_completion_marker(creation.task_path, root=project, handled_by="platform-agent-test")
        review = write_platform_asset_review_task(project, candidate_path=candidate.candidate_path)
        _write_clean_asset_review(project, candidate.candidate_id, candidate.candidate_path)
        write_agent_completion_marker(review.task_path, root=project, handled_by="platform-agent-test")
        record_workflow_approval(project, candidate.candidate_id, "approve", actor="tester")
        promote_candidate_asset(project, candidate.candidate_path, group="character", approval_run_id=candidate.candidate_id)

        result = build_route_audit(project, route="character-and-world-assets")

        self.assertEqual(result.blocking_count, 0)

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
        self.assertIn("scene_0001:prose-candidate", failing_keys)
        self.assertIn("scene_0001:agent-review-json", failing_keys)
        self.assertIn("scene_0001:promotion-manifest", failing_keys)
        self.assertIn("scene_0001:state-patch-json", failing_keys)

    def test_route_audit_blocks_context_packet_without_trace(self):
        project = self.make_project()
        context = build_context_packet(project, scene=Path("scenes/scene_0001.yaml"), rebuild_index=True)
        context.trace_path.unlink()

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertTrue(
            any(gate["key"] == "scene_0001:context-trace" and gate["status"] == "fail" for gate in payload["gates"])
        )

    def test_route_audit_passes_scene_flow_after_full_scene_loop(self):
        project = self.make_project()
        add_character(project)
        make_reviewed_passing_scene(project)
        roleplay = project / "branches" / "scene_0001" / "roleplay_simulation.md"
        roleplay.parent.mkdir(parents=True, exist_ok=True)
        roleplay.write_text(
            "# 角色推演实验室：scene_0001\n\n正式 CLI 来源：`simulate-scene`\n\n### 读取回执\n\n- 已读取：scenes/scene_0001.yaml\n- 写回边界：候选。\n",
            encoding="utf-8",
        )
        branch = build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=3)
        _select_branch(branch.selection_path, branch.recommended_branch)
        build_scene_composition(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True)
        _promote_candidate_and_patch_state(project)

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
        _promote_candidate_and_patch_state(project)

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
        write_formal_candidate_artifacts(project, candidate_dir / "scene_0001-platform-agent.md")
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

    def test_route_audit_blocks_style_lint_even_when_agent_review_passes(self):
        project = self.make_project()
        candidate = _write_candidate(project)
        text = candidate.read_text(encoding="utf-8")
        text = text.replace("林舟站在旧楼门口，先看了一眼街角的灯。", "不是C营的——是那个E营的年轻人，他把袖章藏在雨衣里面。")
        candidate.write_text(text, encoding="utf-8")
        review = write_platform_scene_review(project, scene_id="scene_0001")
        payload = json.loads(review.read_text(encoding="utf-8"))
        payload["candidate"] = "drafts/candidates/scene_0001-platform-agent.md"
        payload["source_paths"] = [
            "scenes/scene_0001.yaml",
            "drafts/candidates/scene_0001-platform-agent.md",
            "memory/context_packets/scene_0001.md",
        ]
        review.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertTrue(
            any(gate["key"] == "scene_0001:style-lint-clean" and gate["status"] == "fail" for gate in payload["gates"])
        )
        self.assertTrue(
            any(gate["key"] == "scene_0001:candidate-review-pass" and gate["status"] == "fail" for gate in payload["gates"])
        )

    def test_route_audit_requires_static_review_after_promotion(self):
        project = self.make_project()
        add_character(project)
        _write_roleplay_receipt(project)
        branch = build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=3)
        _select_branch(branch.selection_path, branch.recommended_branch)
        build_scene_composition(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True)
        _promote_candidate_and_patch_state(project)

        static_review = project / "reviews" / "scene_0001-review.md"
        if static_review.exists():
            static_review.unlink()

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertTrue(
            any(gate["key"] == "scene_0001:static-review-pass" and gate["status"] == "fail" for gate in payload["gates"])
        )

    def test_route_audit_requires_revision_anti_evasion_manifest(self):
        project = self.make_project()
        revision = project / "drafts" / "revisions" / "scene_0001_revision.md"
        revision.parent.mkdir(parents=True, exist_ok=True)
        revision.write_text("## 修订正文候选\n\n他袖章上是E营。先前那件C营雨衣，是别人丢下的。\n", encoding="utf-8")
        review = write_platform_scene_review(project, scene_id="scene_0001")
        payload = json.loads(review.read_text(encoding="utf-8"))
        payload["candidate"] = "drafts/revisions/scene_0001_revision.md"
        payload["source_paths"] = [
            "scenes/scene_0001.yaml",
            "drafts/revisions/scene_0001_revision.md",
            "memory/context_packets/scene_0001.md",
        ]
        review.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = build_route_audit(project, route="scene-development")
        audit = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertTrue(
            any(gate["key"] == "scene_0001:revision-evasion-clean" and gate["status"] == "fail" for gate in audit["gates"])
        )

        write_formal_candidate_artifacts(project, revision, revision=True)
        (project / "drafts" / "revisions" / "scene_0001_revision.json").write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/scene-revision/v0.1",
                    "scene_id": "scene_0001",
                    "candidate": "drafts/revisions/scene_0001_revision.md",
                    "anti_evasion_protocol_applied": True,
                    "evasion_risks_unresolved": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        resolved = build_route_audit(project, route="scene-development")
        resolved_payload = json.loads(resolved.json_path.read_text(encoding="utf-8"))

        self.assertTrue(
            any(gate["key"] == "scene_0001:revision-evasion-clean" and gate["status"] == "pass" for gate in resolved_payload["gates"])
        )

    def test_route_audit_requires_word_budget_before_bulk_longform_scene_work(self):
        project = self.make_project()
        project_yaml = project / "project.yaml"
        project_yaml.write_text(
            project_yaml.read_text(encoding="utf-8").replace("target_length: 30000", "target_length: 130000"),
            encoding="utf-8",
        )

        result = build_route_audit(project, route="scene-development")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertTrue(
            any(gate["key"] == "longform-required:word-budget-json" and gate["status"] == "fail" for gate in payload["gates"])
        )

    def test_route_audit_blocks_debug_review_bypass_flags(self):
        project = self.make_project()
        add_character(project)
        make_reviewed_passing_scene(project)
        _write_roleplay_receipt(project)
        branch = build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=3)
        _select_branch(branch.selection_path, branch.recommended_branch)
        build_scene_composition(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True)
        _promote_candidate_and_patch_state(project)
        promotion = project / "drafts" / "promotions" / "scene_0001_promotion.json"
        payload = json.loads(promotion.read_text(encoding="utf-8"))
        payload["allow_unreviewed"] = True
        promotion.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = build_route_audit(project, route="scene-development")
        audit = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertTrue(
            any(gate["key"] == "debug-waiver-flags" and gate["status"] == "fail" for gate in audit["gates"])
        )

    def test_route_audit_blocks_incomplete_review_and_audit_route(self):
        project = self.make_project()
        build_canon_lint(project)
        task = write_platform_canon_review_task(project)
        _write_canon_review(project, conclusion="pass_with_notes", warnings=["仍需修复。"])
        write_agent_completion_marker(task.task_path, root=project, handled_by="platform-agent-test")

        result = build_route_audit(project, route="review-and-audit")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertGreater(result.blocking_count, 0)
        self.assertTrue(any(gate["key"] == "review:canon-review-clean-pass" and gate["status"] == "fail" for gate in payload["gates"]))
        self.assertTrue(any(gate["key"] == "review:committee-approve" and gate["status"] == "fail" for gate in payload["gates"]))

    def test_route_audit_passes_review_and_audit_route(self):
        project = self.make_project()
        build_canon_lint(project)
        canon_task = write_platform_canon_review_task(project)
        _write_canon_review(project, conclusion="pass")
        write_agent_completion_marker(canon_task.task_path, root=project, handled_by="platform-agent-test")
        build_longform_audit(project)
        committee_task = write_platform_committee_task(project, subject="project-final-audit", source=project / "reviews" / "agent" / "canon_review.md")
        _write_committee_review(project, final_recommendation="approve")
        write_agent_completion_marker(committee_task.task_path, root=project, handled_by="platform-agent-test")

        result = build_route_audit(project, route="review-and-audit")

        self.assertEqual(result.blocking_count, 0)

    def test_route_audit_blocks_dirty_export_release_route(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        build_chapter_workspace(project, chapter_id="chapter_0001")
        build_export_package(project, chapter_id="chapter_0001", include_blocked=True)

        result = build_route_audit(project, route="export-and-release")
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        self.assertGreater(result.blocking_count, 0)
        self.assertTrue(any(gate["key"] == "chapter_0001:export-package-clean" and gate["status"] == "fail" for gate in payload["gates"]))
        self.assertTrue(any(gate["key"] == "chapter_0001:release-approval" and gate["status"] == "fail" for gate in payload["gates"]))

    def test_route_audit_passes_export_release_route(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        build_chapter_workspace(project, chapter_id="chapter_0001")
        build_export_package(project, chapter_id="chapter_0001", formats="md,docx")
        record_workflow_approval(project, "release-chapter_0001", "approve", actor="tester")
        publish_chapter(
            project,
            chapter_id="chapter_0001",
            release_id="formal-release",
            approval_run_id="release-chapter_0001",
            export_formats="md,docx",
        )

        result = build_route_audit(project, route="export-and-release")

        self.assertEqual(result.blocking_count, 0)

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
    project = path.parent.parent.parent
    task = path.with_name("branch_manifest.agent_tasks.md")
    task.write_text(
        "# 平台 Agent 任务说明：fixture branch\n\n创建或覆盖 `branches/scene_0001/branch_selection.md`。\n",
        encoding="utf-8",
    )
    write_agent_completion_marker(task, root=project, handled_by="platform-agent-test")


def _write_roleplay_receipt(project: Path):
    roleplay = project / "branches" / "scene_0001" / "roleplay_simulation.md"
    roleplay.parent.mkdir(parents=True, exist_ok=True)
    roleplay.write_text(
        "# 角色推演实验室：scene_0001\n\n正式 CLI 来源：`simulate-scene`\n\n### 读取回执\n\n- 已读取：scenes/scene_0001.yaml\n- 写回边界：候选。\n",
        encoding="utf-8",
    )
    task = roleplay.with_suffix(".agent_tasks.md")
    task.write_text(
        "# 平台 Agent 任务说明：fixture roleplay\n\n创建或覆盖 `branches/scene_0001/roleplay_simulation.md`。\n",
        encoding="utf-8",
    )
    write_agent_completion_marker(task, root=project, handled_by="platform-agent-test")


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


def _write_canon_review(project: Path, *, conclusion: str, warnings: list[str] | None = None) -> None:
    review_dir = project / "reviews" / "agent"
    review_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/canon-review-agent/v1",
        "conclusion": conclusion,
        "summary": "平台 Agent canon review fixture。",
        "blocking_issues": [],
        "warnings": warnings or [],
        "unresolved_facts": [],
        "timeline_risks": [],
        "source_paths": ["reviews/canon_lint.md", "reviews/canon_lint.json", "canon/", "characters/", "scenes/", "plot/"],
        "recommendations": [] if conclusion == "pass" and not warnings else ["先解决 notes 后再进入导出。"],
        "next_gate": "committee_review",
    }
    (review_dir / "canon_review.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (review_dir / "canon_review.md").write_text(f"# Canon Review\n\n- 结论：`{conclusion}`\n", encoding="utf-8")


def _write_committee_review(project: Path, *, final_recommendation: str, action_items: list[str] | None = None) -> None:
    review_dir = project / "reviews" / "agent"
    review_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/committee-review-agent/v1",
        "subject": "project-final-audit",
        "final_recommendation": final_recommendation,
        "reviewers": [
            {"reviewer_id": "chief-editor", "stance": "approve", "findings": [], "recommendations": [], "source_paths": []},
            {"reviewer_id": "canon-auditor", "stance": "approve", "findings": [], "recommendations": [], "source_paths": []},
        ],
        "disagreements": [],
        "action_items": action_items or [],
        "source_paths": ["reviews/agent/canon_review.json", "reviews/longform/longform_audit.json"],
        "minority_opinions": [],
    }
    (review_dir / "committee_project-final-audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (review_dir / "committee_project-final-audit.md").write_text(
        f"# Committee Review\n\n- Final Recommendation：`{final_recommendation}`\n",
        encoding="utf-8",
    )


def _write_clean_asset_review(project: Path, candidate_id: str, candidate_path: Path) -> None:
    review_dir = project / "reviews" / "assets"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_json = review_dir / f"{candidate_id}_review.json"
    review_md = review_dir / f"{candidate_id}_review.md"
    review_json.write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/candidate-asset-review/v0.1",
                "candidate": candidate_path.relative_to(project).as_posix(),
                "candidate_id": candidate_id,
                "asset_type": "character",
                "status": "pass",
                "blocking_issues": [],
                "warnings": [],
                "revision_actions": [],
                "promotion_risks": [],
                "reviewed_at": "2026-07-18T00:00:00+00:00",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    review_md.write_text("# Candidate Asset Review\n\n- Status：`pass`\n", encoding="utf-8")


def _write_candidate(project: Path, scene_id: str = "scene_0001") -> Path:
    candidate = project / "drafts" / "candidates" / f"{scene_id}-platform-agent.md"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text(
        f"""# 场景候选：{scene_id}

## 正文候选

林舟站在旧楼门口，先看了一眼街角的灯。灯还没转过来。

他推门进去。门轴响了一声。他停住，等楼里重新安静下来，才沿着墙边往里走。

## 状态变化候选

### 新增事实候选

- 林舟发现旧楼停电与残缺档案有关。

### 人物状态变化

- 林舟从旁观转为主动调查。

### 关系变化

- 林舟开始隐瞒自己的行动计划。

### 伏笔变化

- 残缺档案成为后续追查线索。

### 需要人工确认

- 是否确认旧楼停电为主线事件。
""",
        encoding="utf-8",
    )
    write_formal_candidate_artifacts(project, candidate, scene_id=scene_id)
    return candidate


def _promote_candidate_and_patch_state(project: Path, scene_id: str = "scene_0001") -> None:
    candidate = _write_candidate(project, scene_id=scene_id)
    review = write_platform_scene_review(project, scene_id=scene_id)
    payload = json.loads(review.read_text(encoding="utf-8"))
    payload["candidate"] = f"drafts/candidates/{scene_id}-platform-agent.md"
    payload["source_paths"] = [
        f"scenes/{scene_id}.yaml",
        f"drafts/candidates/{scene_id}-platform-agent.md",
        f"memory/context_packets/{scene_id}.md",
    ]
    review.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    promote_scene_candidate(project, scene=Path(f"scenes/{scene_id}.yaml"), candidate=candidate, overwrite=True)
    state = build_character_state_patch(project, scene=Path(f"scenes/{scene_id}.yaml"), source=Path(f"drafts/scenes/{scene_id}.md"), agent_tasks=True)
    assert state.agent_tasks_path is not None
    write_agent_completion_marker(state.agent_tasks_path, root=project, handled_by="platform-agent-test")


if __name__ == "__main__":
    unittest.main()
