"""Tests for Pydantic model validation."""

import pytest
from pydantic import ValidationError

from app.models.jira_models import (
    FeedbackOutput,
    FirstPassOutput,
    WebhookPayload,
)


class TestWebhookPayload:
    def test_valid_first_pass(self):
        p = WebhookPayload(issue_key="PROJ-1", mode="first_pass")
        assert p.issue_key == "PROJ-1"
        assert p.mode == "first_pass"
        assert p.pm_comment is None

    def test_valid_pm_feedback(self):
        p = WebhookPayload(
            issue_key="PROJ-2",
            mode="pm_feedback",
            pm_comment="1. Yes. 2. No.",
        )
        assert p.pm_comment == "1. Yes. 2. No."

    def test_missing_issue_key(self):
        with pytest.raises(ValidationError):
            WebhookPayload(mode="first_pass")

    def test_missing_mode(self):
        with pytest.raises(ValidationError):
            WebhookPayload(issue_key="PROJ-1")


class TestFirstPassOutput:
    def test_valid(self):
        data = {
            "questions": ["Q1", "Q2", "Q3"],
            "proposed_description": "# Background\nSome text",
            "proposed_acceptance_criteria": ["AC1", "AC2"],
            "proposed_subtasks": [],
        }
        result = FirstPassOutput.model_validate(data)
        assert len(result.questions) == 3
        assert result.proposed_subtasks == []

    def test_with_subtasks(self):
        data = {
            "questions": ["Q1"],
            "proposed_description": "desc",
            "proposed_acceptance_criteria": ["AC1"],
            "proposed_subtasks": [
                {"summary": "Setup DB", "description": "Create tables"}
            ],
        }
        result = FirstPassOutput.model_validate(data)
        assert result.proposed_subtasks[0].summary == "Setup DB"

    def test_empty_questions_rejected(self):
        data = {
            "questions": [],
            "proposed_description": "desc",
            "proposed_acceptance_criteria": ["AC1"],
        }
        with pytest.raises(ValidationError):
            FirstPassOutput.model_validate(data)


class TestFeedbackOutput:
    def test_valid_complete(self):
        data = {
            "final_description_markdown": "# Final spec",
            "final_acceptance_criteria": ["AC1"],
            "create_subtasks": False,
            "subtasks": [],
            "followup_questions": [],
        }
        result = FeedbackOutput.model_validate(data)
        assert result.followup_questions == []

    def test_with_followups(self):
        data = {
            "final_description_markdown": "spec",
            "final_acceptance_criteria": ["AC1"],
            "create_subtasks": True,
            "subtasks": [{"summary": "Sub1"}],
            "followup_questions": ["Still unclear about X"],
        }
        result = FeedbackOutput.model_validate(data)
        assert len(result.followup_questions) == 1
        assert result.create_subtasks is True
