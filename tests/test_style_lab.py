import json
import tempfile
import unittest
from pathlib import Path

from literary_engineering_workbench.branch_lab import build_branch_simulation
from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.generation_provider import generate_scene_candidate
from literary_engineering_workbench.platform_agent_tasks import write_platform_scene_review_task
from literary_engineering_workbench.scene_composer import build_scene_composition
from literary_engineering_workbench.style_lab import (
    active_project_style,
    build_style_skill,
    create_author_project,
    create_author_work,
    import_work_source,
    list_author_projects,
    list_style_skills,
    mount_style_skill,
    run_author_style_learning,
)
from literary_engineering_workbench.style_prompt import (
    STYLE_PROMPT_MAX_DETAIL_CHARS,
    STYLE_PROMPT_MIN_DETAIL_CHARS,
    count_style_prompt_detail_chars,
)

from helpers import TempProjectMixin, make_reviewed_passing_scene


class StyleLabTests(TempProjectMixin, unittest.TestCase):
    def test_author_project_builds_mountable_style_skill(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
        _prepare_generation_ready(project)
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "style-library"
            author = create_author_project(library, name="测试作家", author_id="demo-author", source_note="测试语料")
            work = create_author_work(library, author_id=author.author_id, title="测试作品", work_id="demo-work")
            imported = import_work_source(
                library,
                author_id=author.author_id,
                work_id=work.work_id,
                text="雨落在旧城。灯影摇晃。人们沉默。门外传来细小的脚步声。\n\n他没有解释，只把信折好。",
                filename="sample.txt",
            )
            learned = run_author_style_learning(library, author_id=author.author_id, provider="dry-run")
            self._write_style_readiness(learned.profile_dir)
            skill = build_style_skill(library, author_id=author.author_id)
            mounted = mount_style_skill(project, library_root=library, style_id=skill.style_id)

            self.assertTrue(imported.normalized_path.exists())
            self.assertTrue(learned.style_prompt_path.exists())
            self.assertTrue(skill.manifest_path.exists())
            self.assertTrue((mounted.mount_dir / "prompt.md").exists())
            active = active_project_style(project)
            self.assertEqual(active["style_id"], skill.style_id)
            self.assertEqual(active["priority"], "highest")

            generated = generate_scene_candidate(project, scene=Path("scenes/scene_0001.yaml"), provider="dry-run")
            prompt_manifest = json.loads(generated.prompt_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(prompt_manifest["style_profile"], f"style/mounted/{skill.style_id}/prompt.md")
            self.assertEqual(prompt_manifest["generation_standards"]["style_profile"], f"style/mounted/{skill.style_id}/prompt.md")
            self.assertIn("已挂载文风 Style Skill", prompt_manifest["messages"][1]["content"])
            self.assertIn("文风生成标准", prompt_manifest["messages"][1]["content"])
            self.assertIn("最高优先级", prompt_manifest["messages"][1]["content"])
            review_task = write_platform_scene_review_task(
                project,
                scene_path=project / "scenes" / "scene_0001.yaml",
                draft_path=project / "drafts" / "scenes" / "scene_0001.md",
            )
            task_text = review_task.task_path.read_text(encoding="utf-8")
            self.assertIn("style/active_style_skill.json", task_text)
            self.assertIn(f"style/mounted/{skill.style_id}/prompt.md", task_text)
            self.assertEqual(list_author_projects(library)["count"], 1)
            self.assertEqual(list_style_skills(library)["count"], 1)

    def test_mount_blocks_unreviewed_style_skill_by_default(self):
        project = self.make_project()
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "style-library"
            author = create_author_project(library, name="测试作家", author_id="demo-author", source_note="测试语料")
            work = create_author_work(library, author_id=author.author_id, title="测试作品", work_id="demo-work")
            import_work_source(
                library,
                author_id=author.author_id,
                work_id=work.work_id,
                text="雨落在旧城。灯影摇晃。人们沉默。",
                filename="sample.txt",
            )
            run_author_style_learning(library, author_id=author.author_id, provider="dry-run")
            skill = build_style_skill(library, author_id=author.author_id)

            with self.assertRaises(ValueError):
                mount_style_skill(project, library_root=library, style_id=skill.style_id)

            experimental = mount_style_skill(project, library_root=library, style_id=skill.style_id, allow_unreviewed=True)
            active = active_project_style(project)
            self.assertEqual(experimental.style_id, skill.style_id)
            self.assertFalse(active["readiness"]["ready"])
            self.assertTrue(active["allow_unreviewed"])

    def test_mount_blocks_style_prompt_outside_detail_range(self):
        project = self.make_project()
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "style-library"
            author = create_author_project(library, name="测试作家", author_id="demo-author", source_note="测试语料")
            work = create_author_work(library, author_id=author.author_id, title="测试作品", work_id="demo-work")
            import_work_source(
                library,
                author_id=author.author_id,
                work_id=work.work_id,
                text="雨落在旧城。灯影摇晃。人们沉默。门外传来细小的脚步声。",
                filename="sample.txt",
            )
            learned = run_author_style_learning(library, author_id=author.author_id, provider="dry-run")
            self._write_style_readiness(learned.profile_dir)
            skill = build_style_skill(library, author_id=author.author_id)

            (skill.skill_dir / "prompt.md").write_text("文风约束太短。\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, f"detail_chars_below_{STYLE_PROMPT_MIN_DETAIL_CHARS}"):
                mount_style_skill(project, library_root=library, style_id=skill.style_id)

            long_prompt = "# LLM 文风约束提示词\n\n" + ("文风约束必须具体说明叙述距离句法节奏意象调度心理呈现对白动作标点边界。" * 80)
            self.assertGreater(count_style_prompt_detail_chars(long_prompt), STYLE_PROMPT_MAX_DETAIL_CHARS)
            (skill.skill_dir / "prompt.md").write_text(long_prompt, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, f"detail_chars_above_{STYLE_PROMPT_MAX_DETAIL_CHARS}"):
                mount_style_skill(project, library_root=library, style_id=skill.style_id)

            vague_prompt = "# LLM 文风约束提示词\n\n" + ("这份提示词要求文风优美克制，文学性强，整体高级，气质稳定，表达自然。" * 35)
            self.assertGreaterEqual(count_style_prompt_detail_chars(vague_prompt), STYLE_PROMPT_MIN_DETAIL_CHARS)
            self.assertLessEqual(count_style_prompt_detail_chars(vague_prompt), STYLE_PROMPT_MAX_DETAIL_CHARS)
            (skill.skill_dir / "prompt.md").write_text(vague_prompt, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing_required_block"):
                mount_style_skill(project, library_root=library, style_id=skill.style_id)

    def test_cli_exposes_style_lab_commands(self):
        help_text = build_parser().format_help()
        self.assertIn("style-lab-author", help_text)
        self.assertIn("style-lab-mount", help_text)
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "style-library"
            code = main(["style-lab-author", "--library", str(library), "--name", "测试作家", "--author-id", "demo-author"])
            self.assertEqual(code, 0)
            self.assertTrue((library / "authors" / "demo-author" / "author.json").exists())

    def _write_style_readiness(self, profile_dir: Path) -> None:
        prompt_text = _valid_style_prompt_text()
        detail_chars = count_style_prompt_detail_chars(prompt_text)
        self.assertGreaterEqual(detail_chars, STYLE_PROMPT_MIN_DETAIL_CHARS)
        self.assertLessEqual(detail_chars, STYLE_PROMPT_MAX_DETAIL_CHARS)
        (profile_dir / "style_prompt.md").write_text(prompt_text, encoding="utf-8")
        (profile_dir / "style_prompt.agent.json").write_text(
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
        eval_dir = profile_dir / "evaluation_results" / "back-translation"
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


if __name__ == "__main__":
    unittest.main()
