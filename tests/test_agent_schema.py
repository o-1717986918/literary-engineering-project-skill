import json
import unittest

from literary_engineering_workbench.agent_provider import run_agent_task
from literary_engineering_workbench.agent_schema import repair_agent_run, validate_agent_run

from helpers import TempProjectMixin


class AgentSchemaTests(TempProjectMixin, unittest.TestCase):
    def test_validates_generic_agent_output(self):
        project = self.make_project()
        run = run_agent_task(
            project,
            agent_id="generic-reviewer",
            task="generic",
            system_prompt="system",
            user_prompt="user",
            provider="dry-run",
        )

        validation = validate_agent_run(project, run_dir=run.run_dir, schema_name="generic_agent_output.v1")

        self.assertEqual(validation.status, "pass")
        payload = json.loads(validation.validation_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["error_count"], 0)

    def test_repairs_invalid_schema_output_with_dry_run_payload(self):
        project = self.make_project()
        run = run_agent_task(
            project,
            agent_id="generic-reviewer",
            task="generic",
            system_prompt="system",
            user_prompt="user",
            provider="dry-run",
        )

        failed = validate_agent_run(project, run_dir=run.run_dir, schema_name="scene_review.v1")
        self.assertEqual(failed.status, "failed")

        repaired = repair_agent_run(project, run_dir=run.run_dir, schema_name="scene_review.v1", provider="dry-run")

        self.assertEqual(repaired.status, "pass")
        repaired_payload = json.loads((repaired.repair_run_dir / "parsed_output.json").read_text(encoding="utf-8"))
        self.assertEqual(repaired_payload["schema"], "literary-engineering-workbench/scene-review-agent/v1")


if __name__ == "__main__":
    unittest.main()
