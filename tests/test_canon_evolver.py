import json
import unittest
from pathlib import Path

from literary_engineering_workbench.agent_tasks import write_agent_completion_marker
from literary_engineering_workbench.approval import record_workflow_approval
from literary_engineering_workbench.canon_evolver import (
    apply_canon_patch,
    build_canon_patch_backlog,
    build_canon_patch_task,
    canon_writeback_status,
)
from literary_engineering_workbench.cli import build_parser, main

from helpers import TempProjectMixin


class CanonEvolverTests(TempProjectMixin, unittest.TestCase):
    def test_canon_writeback_status_enforces_declarations_and_patch_completion(self):
        project = self.make_project()
        source = _write_candidate(project)

        self.assertEqual(canon_writeback_status(project, "scene_0001")["status"], "not_required")

        _write_manifest(source, {"canon_change": False})
        self.assertEqual(canon_writeback_status(project, "scene_0001")["status"], "missing_reason")

        _write_manifest(source, {"canon_change": False, "no_canon_change_reason": "本场只改变人物临时状态，没有新增持续世界事实。"})
        status = canon_writeback_status(project, "scene_0001")
        self.assertEqual(status["status"], "pass")

        _write_manifest(source, {"canon_change": "unknown"})
        self.assertEqual(canon_writeback_status(project, "scene_0001")["status"], "unknown")

        _write_manifest(source, {"canon_change": True})
        self.assertEqual(canon_writeback_status(project, "scene_0001")["status"], "missing_patch")

        result = build_canon_patch_task(project, scene=Path("scenes/scene_0001.yaml"), source=source)
        self.assertTrue(result.task_path.exists())
        self.assertEqual(canon_writeback_status(project, "scene_0001")["status"], "invalid_patch")

        result.json_path.write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/canon-patch-candidate/v0.1",
                    "scene_id": "scene_0001",
                    "canon_change": True,
                    "items": [{}],
                    "status": "candidate",
                    "applied": False,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        invalid_item_status = canon_writeback_status(project, "scene_0001")
        self.assertEqual(invalid_item_status["status"], "invalid_patch")
        self.assertIn("items[1].type", invalid_item_status["message"])

        result.json_path.write_text(
            json.dumps(
                {
                    "schema": "literary-engineering-workbench/canon-patch-candidate/v0.1",
                    "scene_id": "scene_0001",
                    "canon_change": True,
                    "no_canon_change_reason": "",
                    "items": [
                        {
                            "type": "world_fact",
                            "summary": "旧楼停电与档案系统存在持续关联。",
                            "source_evidence": "正文中确认旧楼停电触发档案线索。",
                            "target_files": ["canon/facts.json"],
                            "risk_level": "medium",
                            "requires_user_approval": True,
                        }
                    ],
                    "status": "candidate",
                    "applied": False,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        write_agent_completion_marker(result.task_path, root=project, handled_by="platform-agent-test")
        self.assertEqual(canon_writeback_status(project, "scene_0001")["status"], "pass")

    def test_cli_exposes_and_runs_canon_evolve(self):
        project = self.make_project()
        source = _write_candidate(project)
        _write_manifest(source, {"canon_change": True})

        self.assertIn("canon-evolve", build_parser().format_help())
        code = main(["canon-evolve", str(project), "--scene", "scenes/scene_0001.yaml", "--source", str(source)])

        self.assertEqual(code, 0)
        self.assertTrue((project / "canon" / "patches" / "scene_0001_canon_patch.agent_tasks.md").exists())

    def test_canon_backlog_and_apply_require_approval(self):
        project = self.make_project()
        source = _write_candidate(project)
        _write_manifest(source, {"canon_change": True})
        result = build_canon_patch_task(project, scene=Path("scenes/scene_0001.yaml"), source=source)
        _write_ready_patch(result.json_path)
        write_agent_completion_marker(result.task_path, root=project, handled_by="platform-agent-test")

        backlog = build_canon_patch_backlog(project)
        self.assertEqual(backlog.pending_count, 1)
        self.assertIn("needs_approval", backlog.output_path.read_text(encoding="utf-8"))

        with self.assertRaises(RuntimeError):
            apply_canon_patch(project, patch=result.json_path)

        record_workflow_approval(project, "scene_0001_canon_patch", "approve", actor="tester", notes="canon 变化可写入账本。")
        applied = apply_canon_patch(project, patch=result.json_path)

        self.assertEqual(applied.status, "applied")
        self.assertTrue(applied.json_path.exists())
        self.assertTrue((project / "canon" / "canon_change_log.md").exists())
        status = canon_writeback_status(project, "scene_0001")
        self.assertEqual(status["status"], "pass")
        self.assertTrue(status["applied"])

    def test_cli_blocks_canon_apply_bypass_without_maintainer_mode(self):
        project = self.make_project()
        source = _write_candidate(project)
        _write_manifest(source, {"canon_change": True})
        result = build_canon_patch_task(project, scene=Path("scenes/scene_0001.yaml"), source=source)
        _write_ready_patch(result.json_path)
        write_agent_completion_marker(result.task_path, root=project, handled_by="platform-agent-test")

        code = main(["canon-apply", str(project), "--patch", str(result.json_path), "--allow-unapproved"])

        self.assertEqual(code, 2)


def _write_candidate(project: Path) -> Path:
    path = project / "drafts" / "candidates" / "scene_0001-platform-agent.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("## 正文候选\n\n林舟在旧楼里发现停电和档案系统有关。\n", encoding="utf-8")
    return path


def _write_manifest(candidate: Path, declaration: dict[str, object]) -> Path:
    manifest = candidate.with_suffix(".json")
    payload = {
        "schema": "literary-engineering-workbench/scene-generation-candidate/v0.1",
        "scene_id": "scene_0001",
        "candidate": candidate.name,
        "generated_by": "platform-agent",
    }
    payload.update(declaration)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _write_ready_patch(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/canon-patch-candidate/v0.1",
                "scene_id": "scene_0001",
                "canon_change": True,
                "items": [
                    {
                        "type": "world_fact",
                        "summary": "旧楼停电与档案系统存在持续关联。",
                        "source_evidence": "正文中确认旧楼停电触发档案线索。",
                        "target_files": ["canon/canon_change_log.md"],
                        "risk_level": "medium",
                        "requires_user_approval": True,
                    }
                ],
                "status": "candidate",
                "applied": False,
                "requires_user_approval": True,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
