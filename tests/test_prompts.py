"""Tests for prompt builders."""

from app.llm.prompts import build_feedback_prompt, build_first_pass_prompt
from app.models.domain import DomainConfig, Persona


def _sample_config() -> DomainConfig:
    return DomainConfig(
        project_name="TestProject",
        ticket_structure=["Background", "Desired behavior", "Acceptance criteria"],
        user_personas=[Persona(name="Admin", description="Full access user")],
        platforms=["Web"],
        standards={"performance": "p95 < 500ms"},
        acceptance_criteria_style="bullet",
    )


class TestFirstPassPrompt:
    def test_contains_ticket_summary(self):
        fields = {
            "summary": "Add dark mode toggle",
            "description": "Users want dark mode",
            "issuetype": {"name": "Story"},
            "priority": {"name": "High"},
            "labels": ["ui"],
        }
        messages = build_first_pass_prompt(fields, [], _sample_config())

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Add dark mode toggle" in messages[1]["content"]
        assert "dark mode" in messages[1]["content"]

    def test_includes_domain_config(self):
        fields = {"summary": "Test", "description": "desc"}
        messages = build_first_pass_prompt(fields, [], _sample_config())
        system = messages[0]["content"]

        assert "TestProject" in system
        assert "Background" in system
        assert "Admin" in system
        assert "p95 < 500ms" in system

    def test_includes_similar_tickets(self):
        fields = {"summary": "Test", "description": "desc"}
        similar = [{"summary": "Past ticket", "description": "Old spec"}]
        messages = build_first_pass_prompt(fields, similar, _sample_config())

        assert "Past ticket" in messages[1]["content"]

    def test_json_schema_hint(self):
        fields = {"summary": "Test"}
        messages = build_first_pass_prompt(fields, [], _sample_config())
        system = messages[0]["content"]

        assert "questions" in system
        assert "proposed_description" in system
        assert "proposed_acceptance_criteria" in system


class TestFeedbackPrompt:
    def test_basic_structure(self):
        messages = build_feedback_prompt(
            original_description="Rough desc",
            previous_spec="Draft spec here",
            pm_comment="1. Yes. 2. Web only.",
            similar_tickets=[],
            domain_config=_sample_config(),
        )

        assert len(messages) == 2
        assert "Rough desc" in messages[1]["content"]
        assert "Draft spec here" in messages[1]["content"]
        assert "1. Yes. 2. Web only." in messages[1]["content"]

    def test_json_schema_hint(self):
        messages = build_feedback_prompt(
            original_description="desc",
            previous_spec="spec",
            pm_comment="answers",
            similar_tickets=[],
            domain_config=_sample_config(),
        )
        system = messages[0]["content"]

        assert "final_description_markdown" in system
        assert "final_acceptance_criteria" in system
        assert "followup_questions" in system
