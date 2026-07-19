import json
import unittest
from pathlib import Path

from literary_engineering_workbench.agent_tasks import write_agent_completion_marker
from literary_engineering_workbench.branch_lab import build_branch_simulation
from literary_engineering_workbench.candidate_promotion import promote_scene_candidate
from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.flow_gates import FlowGateError
from literary_engineering_workbench.generation_provider import generate_scene_candidate
from literary_engineering_workbench.scene_composer import build_scene_composition

from helpers import TempProjectMixin, write_formal_candidate_artifacts


class CandidatePromotionTests(TempProjectMixin, unittest.TestCase):
    def test_promotes_candidate_into_reviewable_draft(self):
        project = self.make_project()
        _prepare_generation_ready(project)
        candidate = generate_scene_candidate(
            project,
            scene=Path("scenes/scene_0001.yaml"),
            rebuild_context=True,
            provider="dry-run",
        )

        with self.assertRaises(FlowGateError):
            promote_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), candidate=candidate.candidate_path)
        write_formal_candidate_artifacts(project, candidate.candidate_path)
        _write_candidate_review(project, candidate.candidate_path)

        result = promote_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), candidate=candidate.candidate_path)

        self.assertTrue(result.draft_path.exists())
        self.assertTrue(result.manifest_path.exists())
        self.assertTrue(result.report_path.exists())
        draft = result.draft_path.read_text(encoding="utf-8")
        self.assertIn("## 正文草稿", draft)
        self.assertIn("来源候选", draft)
        self.assertIn("## 状态变化", draft)
        self.assertIn("dry-run provider", draft)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["candidate"], "drafts/candidates/" + candidate.candidate_path.name)
        self.assertEqual(manifest["draft"], "drafts/scenes/scene_0001.md")

        with self.assertRaises(FileExistsError):
            promote_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), candidate=candidate.candidate_path)

    def test_cli_exposes_and_runs_promote_candidate(self):
        project = self.make_project()
        _prepare_generation_ready(project)
        candidate = generate_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True, provider="dry-run")
        write_formal_candidate_artifacts(project, candidate.candidate_path)
        _write_candidate_review(project, candidate.candidate_path)

        self.assertIn("promote-candidate", build_parser().format_help())
        code = main(
            [
                "promote-candidate",
                str(project),
                "--scene",
                "scenes/scene_0001.yaml",
                "--candidate",
                str(candidate.candidate_path),
            ]
        )

        self.assertEqual(code, 0)
        self.assertTrue((project / "drafts" / "scenes" / "scene_0001.md").exists())

    def test_internal_experiment_can_promote_unreviewed_candidate(self):
        project = self.make_project()
        _prepare_generation_ready(project)
        candidate = generate_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True, provider="dry-run")

        result = promote_scene_candidate(
            project,
            scene=Path("scenes/scene_0001.yaml"),
            candidate=candidate.candidate_path,
            allow_unreviewed=True,
        )

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertTrue(manifest["allow_unreviewed"])
        self.assertEqual(manifest["candidate_review"]["status"], "missing")

    def test_promote_candidate_blocks_style_lint_gate_even_with_pass_review(self):
        project = self.make_project()
        _prepare_generation_ready(project)
        candidate = generate_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True, provider="dry-run")
        _replace_candidate_body(candidate.candidate_path, "不是C营的——是那个E营的年轻人，他把袖章藏在雨衣里面。")
        write_formal_candidate_artifacts(project, candidate.candidate_path)
        _write_candidate_review(project, candidate.candidate_path)

        with self.assertRaises(FlowGateError) as ctx:
            promote_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), candidate=candidate.candidate_path)

        self.assertIn("Style Lint Gate", str(ctx.exception))
        self.assertIn("mechanical-contrast-frame", str(ctx.exception))

    def test_promote_candidate_blocks_unresolved_new_character_register(self):
        project = self.make_project()
        _prepare_generation_ready(project)
        candidate = generate_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True, provider="dry-run")
        write_formal_candidate_artifacts(project, candidate.candidate_path)
        _write_candidate_review(
            project,
            candidate.candidate_path,
            new_character_register={
                "schema": "literary-engineering-workbench/new-character-register/v0.1",
                "status": "needs_candidate",
                "introduced": [
                    {
                        "name": "沈迟",
                        "character_id": "shenchi",
                        "scene_function": "掌握关键线索并将在后续复用",
                        "persistence": "recurring",
                    }
                ],
                "ephemeral_waivers": [],
                "blocking_issues": ["persistent character has no candidate asset"],
            },
        )

        with self.assertRaises(FlowGateError) as ctx:
            promote_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), candidate=candidate.candidate_path)

        self.assertIn("new_character_register", str(ctx.exception))

    def test_promotes_revision_candidate_body(self):
        project = self.make_project()
        _prepare_generation_ready(project)
        revision = project / "drafts" / "revisions" / "scene_0001_revision.md"
        revision.parent.mkdir(parents=True, exist_ok=True)
        revision.write_text(
            """# 修订候选：scene_0001

## 修订正文候选

他袖章上是E营。先前那件C营雨衣，是别人丢下的。

他把雨衣叠好，塞进柜门后面。楼下有人喊他的名字，他没有应声。

## 状态变化候选

### 新增事实候选

- 林舟确认雨衣来自另一名队员。

### 人物状态变化

- 林舟选择隐藏雨衣线索。

### 关系变化

- 林舟与E营线索建立隐性关联。

### 伏笔变化

- C营雨衣成为误导线索。

### 需要人工确认

- 是否确认E营身份线索。
""",
            encoding="utf-8",
        )
        write_formal_candidate_artifacts(project, revision, revision=True)
        _write_candidate_review(project, revision)

        result = promote_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), candidate=revision)

        draft = result.draft_path.read_text(encoding="utf-8")
        self.assertIn("他袖章上是E营", draft)
        self.assertIn("## 正文草稿", draft)


def _prepare_generation_ready(project: Path):
    branch = build_branch_simulation(project, scene=Path("scenes/scene_0001.yaml"), branch_count=3)
    _select_branch(branch.selection_path, branch.recommended_branch)
    build_scene_composition(project, scene=Path("scenes/scene_0001.yaml"), rebuild_context=True)


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


def _write_candidate_review(project: Path, candidate: Path, *, new_character_register: dict | None = None):
    review_dir = project / "reviews" / "agent"
    review_dir.mkdir(parents=True, exist_ok=True)
    rel_candidate = candidate.resolve().relative_to(project.resolve()).as_posix()
    payload = {
        "schema": "literary-engineering-workbench/scene-review-agent/v1",
        "scene_id": "scene_0001",
        "conclusion": "pass",
        "summary": "候选稿已通过 promotion 前正式审查。",
        "blocking_issues": [],
        "warnings": [],
        "revision_actions": [],
        "character_logic": [{"character": "all", "assessment": "人物行动符合当前约束。"}],
        "canon_risks": [],
        "style_notes": [],
        "style_adherence": {
            "status": "not_applicable",
            "style_profile": "n/a",
            "evidence": [],
            "deviations": [],
            "revision_actions": [],
        },
        "word_budget_adherence": {
            "status": "not_required",
            "target_words": 0,
            "min_words": 0,
            "max_words": 0,
            "clean_body_words": 120,
            "narrative_load_satisfied": True,
            "message": "test project does not require longform budget",
        },
        "new_character_register": new_character_register or {
            "schema": "literary-engineering-workbench/new-character-register/v0.1",
            "status": "none",
            "introduced": [],
            "ephemeral_waivers": [],
            "blocking_issues": [],
        },
        "source_paths": [
            "scenes/scene_0001.yaml",
            rel_candidate,
            "memory/context_packets/scene_0001.md",
            "memory/context_packets/scene_0001.trace.json",
        ],
        "agent_confidence": "platform-test",
        "next_gate": "promote_candidate",
    }
    (review_dir / "scene_0001_scene_review.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (review_dir / "scene_0001_scene_review.md").write_text("# 候选审查\n\n- 结论：`pass`\n", encoding="utf-8")
    task = review_dir / "scene_0001_scene_review.agent_tasks.md"
    task.write_text(
        "# 平台 Agent 任务说明：fixture candidate review\n\n创建或覆盖 `reviews/agent/scene_0001_scene_review.json`。\n",
        encoding="utf-8",
    )
    write_agent_completion_marker(task, root=project, handled_by="platform-agent-test")


def _replace_candidate_body(candidate: Path, body: str) -> None:
    text = candidate.read_text(encoding="utf-8")
    start = text.index("## 正文候选") + len("## 正文候选")
    end = text.index("## 状态变化候选")
    candidate.write_text(text[:start] + "\n\n" + body.strip() + "\n\n" + text[end:], encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
