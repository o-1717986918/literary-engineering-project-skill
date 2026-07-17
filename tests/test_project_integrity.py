import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProjectIntegrityTests(unittest.TestCase):
    def test_agentread_referenced_files_exist(self):
        agentread = (PROJECT_ROOT / "agentread.yaml").read_text(encoding="utf-8")
        refs = _extract_project_paths(agentread)
        missing = [ref for ref in refs if not (PROJECT_ROOT / ref).exists()]
        self.assertEqual(missing, [], f"missing agentread references: {missing}")

    def test_primary_docs_do_not_reference_missing_project_files(self):
        checked_files = [
            PROJECT_ROOT / "AGENTS.md",
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "docs" / "agentread" / "quickstart.md",
            PROJECT_ROOT / "docs" / "agentread" / "task-map.md",
            PROJECT_ROOT / "docs" / "maintenance" / "version-control.md",
            PROJECT_ROOT / "docs" / "maintenance" / "recovery-audit.md",
            PROJECT_ROOT / "docs" / "maintenance" / "precision-development-plan.md",
        ]
        missing = []
        for file in checked_files:
            text = file.read_text(encoding="utf-8")
            for ref in _extract_project_paths(text):
                if not (PROJECT_ROOT / ref).exists():
                    missing.append(f"{file.relative_to(PROJECT_ROOT).as_posix()} -> {ref}")
        self.assertEqual(missing, [], f"missing primary doc references: {missing}")

    def test_required_runtime_files_exist(self):
        required = [
            "pyproject.toml",
            "schemas/agent_outputs/generic_agent_output.v1.schema.json",
            "schemas/agent_outputs/scene_review.v1.schema.json",
            "schemas/agent_outputs/canon_review.v1.schema.json",
            "schemas/agent_outputs/style_prompt.v1.schema.json",
            "schemas/agent_outputs/json_patch_plan.v1.schema.json",
            "schemas/agent_outputs/reviewer_opinion.v1.schema.json",
            "schemas/agent_outputs/committee_review.v1.schema.json",
            "schemas/agent_outputs/character_profile.v1.schema.json",
            "schemas/agent_outputs/background_story.v1.schema.json",
            "schemas/agent_outputs/world_rules.v1.schema.json",
            "schemas/agent_outputs/location.v1.schema.json",
            "schemas/agent_outputs/organization.v1.schema.json",
            "schemas/agent_outputs/plot_outline.v1.schema.json",
            "schemas/agent_outputs/relationship_graph.v1.schema.json",
            "schemas/agent_outputs/director_decision.v1.schema.json",
            "src/literary_engineering_workbench/agent_canon_review.py",
            "src/literary_engineering_workbench/agent_committee.py",
            "src/literary_engineering_workbench/agent_json_builder.py",
            "src/literary_engineering_workbench/agent_provider.py",
            "src/literary_engineering_workbench/agent_schema.py",
            "src/literary_engineering_workbench/agent_scene_review.py",
            "src/literary_engineering_workbench/cli.py",
            "src/literary_engineering_workbench/api_server.py",
            "src/literary_engineering_workbench/asset_workshop.py",
            "src/literary_engineering_workbench/branch_lab.py",
            "src/literary_engineering_workbench/candidate_promotion.py",
            "src/literary_engineering_workbench/character_state_apply.py",
            "src/literary_engineering_workbench/character_state_evolver.py",
            "src/literary_engineering_workbench/dify_dsl.py",
            "src/literary_engineering_workbench/demo_project.py",
            "src/literary_engineering_workbench/director_agent.py",
            "src/literary_engineering_workbench/generation_provider.py",
            "src/literary_engineering_workbench/knowledge_store.py",
            "src/literary_engineering_workbench/langgraph_adapter.py",
            "src/literary_engineering_workbench/model_config.py",
            "src/literary_engineering_workbench/publish.py",
            "src/literary_engineering_workbench/prompt_pack.py",
            "src/literary_engineering_workbench/protocol.py",
            "src/literary_engineering_workbench/punctuation_standard.py",
            "src/literary_engineering_workbench/scene_composer.py",
            "src/literary_engineering_workbench/source_ingest.py",
            "src/literary_engineering_workbench/style_evaluator.py",
            "src/literary_engineering_workbench/style_lab.py",
            "src/literary_engineering_workbench/style_prompt.py",
            "src/literary_engineering_workbench/style_prompt_agent.py",
            "src/literary_engineering_workbench/style_prompt_eval.py",
            "src/literary_engineering_workbench/canon_lint.py",
            "templates/scene.yaml",
            "templates/character.yaml",
            "templates/prompts/scene_generation_system.md",
            "templates/prompts/scene_generation_user.md",
            "templates/prompts/character_creation_system.md",
            "templates/prompts/character_creation_user.md",
            "templates/prompts/worldbuilding_system.md",
            "templates/prompts/worldbuilding_user.md",
            "templates/prompts/outline_creation_system.md",
            "templates/prompts/outline_creation_user.md",
            "templates/prompts/director_system.md",
            "templates/prompts/director_user.md",
            "references/punctuation-standard.md",
            "references/agent-run-protocol.md",
            "references/cli-run-protocol.md",
            "frontend/index.html",
            "frontend/styles.css",
            "frontend/app.js",
            "docs/implementation/phase12-dify-dsl.md",
            "docs/implementation/phase13-api-auth.md",
            "docs/implementation/phase14-workflow-persistence.md",
            "docs/implementation/phase15-approval-loop.md",
            "docs/implementation/phase16-generation-provider.md",
            "docs/implementation/phase17-knowledge-store.md",
            "docs/implementation/phase18-style-eval.md",
            "docs/implementation/phase19-canon-lint.md",
            "docs/implementation/phase20-branch-simulation.md",
            "docs/implementation/phase20-character-background-story.md",
            "docs/implementation/phase21-publish-chain.md",
            "docs/implementation/phase22-scene-composer.md",
            "docs/implementation/phase23-model-provider-prompt-pack.md",
            "docs/implementation/phase24-character-state-evolution.md",
            "docs/implementation/phase25-candidate-promotion-state-apply.md",
            "docs/implementation/phase26-style-prompt-effectiveness.md",
            "docs/implementation/phase27-agent-provider.md",
            "docs/implementation/phase28-agent-schema-repair.md",
            "docs/implementation/phase29-agent-scene-review.md",
            "docs/implementation/phase30-agent-canon-review.md",
            "docs/implementation/phase31-agent-json-patch-plan.md",
            "docs/implementation/phase32-agent-style-prompt.md",
            "docs/implementation/phase33-agent-review-committee.md",
            "docs/implementation/phase34-agent-workflow-integration.md",
            "docs/implementation/phase35-demo-regression.md",
            "docs/implementation/phase36-global-config-frontend.md",
            "docs/implementation/phase37-asset-candidate-schemas.md",
            "docs/implementation/phase38-agent-character-creation.md",
            "docs/implementation/phase39-agent-worldbuilding.md",
            "docs/implementation/phase40-agent-outline-creation.md",
            "docs/implementation/phase41-candidate-review-promotion.md",
            "docs/implementation/phase42-asset-workflow-modes.md",
            "docs/implementation/phase43-asset-api-frontend.md",
            "docs/implementation/phase44-asset-prompt-templates.md",
            "docs/implementation/phase45-asset-demo-regression.md",
            "docs/implementation/phase46-creative-director-agent.md",
            "docs/implementation/phase47-frontend-api-key-config.md",
            "docs/implementation/phase48-agent-auto-llm-provider.md",
            "docs/implementation/phase57-frontend-surface-refactor.md",
            "docs/implementation/phase58-author-style-projects.md",
            "docs/implementation/phase59-style-skill-package.md",
            "docs/implementation/phase60-style-skill-mount.md",
            "docs/implementation/phase61-style-priority-enforcement.md",
            "docs/implementation/phase62-style-lab-frontend-loop.md",
            "docs/implementation/phase63-style-lab-regression-package.md",
            "docs/implementation/phase64-existing-work-ingest.md",
            "docs/modules/source-ingest-engine.md",
            "docs/maintenance/agentic-review-development-plan.md",
            "docs/maintenance/precision-development-plan.md",
            "docs/integrations/dify/README.md",
            "docs/integrations/dify/literary-workbench-reviewer.workflow.yml",
        ]
        missing = [ref for ref in required if not (PROJECT_ROOT / ref).exists()]
        self.assertEqual(missing, [])


def _extract_project_paths(text: str) -> list[str]:
    candidates = set()
    for match in re.findall(
        r"(?:docs|templates|src|tests)/[A-Za-z0-9_\-./]+(?:\.md|\.yaml|\.yml|\.py|\.toml|\.json|\.csv)?",
        text,
    ):
        candidates.add(match.rstrip("`.,)）:："))
    return sorted(candidates)


if __name__ == "__main__":
    unittest.main()
