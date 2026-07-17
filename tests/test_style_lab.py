import json
import tempfile
import unittest
from pathlib import Path

from literary_engineering_workbench.cli import build_parser, main
from literary_engineering_workbench.generation_provider import generate_scene_candidate
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

from helpers import TempProjectMixin, make_reviewed_passing_scene


class StyleLabTests(TempProjectMixin, unittest.TestCase):
    def test_author_project_builds_mountable_style_skill(self):
        project = self.make_project()
        make_reviewed_passing_scene(project)
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
            self.assertIn("已挂载文风 Style Skill", prompt_manifest["messages"][1]["content"])
            self.assertIn("最高优先级", prompt_manifest["messages"][1]["content"])
            self.assertEqual(list_author_projects(library)["count"], 1)
            self.assertEqual(list_style_skills(library)["count"], 1)

    def test_cli_exposes_style_lab_commands(self):
        help_text = build_parser().format_help()
        self.assertIn("style-lab-author", help_text)
        self.assertIn("style-lab-mount", help_text)
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "style-library"
            code = main(["style-lab-author", "--library", str(library), "--name", "测试作家", "--author-id", "demo-author"])
            self.assertEqual(code, 0)
            self.assertTrue((library / "authors" / "demo-author" / "author.json").exists())


if __name__ == "__main__":
    unittest.main()
