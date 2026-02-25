"""
Pydantic models for Jira webhook payloads and LLM response schemas.
"""

from pydantic import BaseModel, Field


# ── Incoming webhook payload ────────────────────────────


class WebhookPayload(BaseModel):
    """Payload sent by Jira Automation to /jira/refine."""

    issue_key: str = Field(..., description="Jira issue key, e.g. PROJ-123")
    mode: str = Field(
        ..., description="Either 'first_pass' or 'pm_feedback'"
    )
    pm_comment: str | None = Field(
        None,
        description="PM's latest comment text (only for pm_feedback mode)",
    )


# ── LLM output: first pass ─────────────────────────────


class ProposedSubtask(BaseModel):
    summary: str
    description: str = ""


class FirstPassOutput(BaseModel):
    """Structured output the LLM returns for a first-pass refinement."""

    questions: list[str] = Field(
        ...,
        description="3–7 clarifying questions for the PM",
        min_length=1,
        max_length=10,
    )
    proposed_description: str = Field(
        ..., description="Markdown description following the ticket template"
    )
    proposed_acceptance_criteria: list[str] = Field(
        ..., description="List of acceptance criteria"
    )
    proposed_subtasks: list[ProposedSubtask] = Field(
        default_factory=list,
        description="Optional list of suggested subtasks",
    )


# ── LLM output: PM feedback pass ───────────────────────


class Subtask(BaseModel):
    summary: str
    description: str = ""


class FeedbackOutput(BaseModel):
    """Structured output the LLM returns after PM answers questions."""

    final_description_markdown: str = Field(
        ..., description="Final description in markdown"
    )
    final_acceptance_criteria: list[str] = Field(
        ..., description="Final acceptance criteria list"
    )
    create_subtasks: bool = Field(
        default=False, description="Whether to create subtasks"
    )
    subtasks: list[Subtask] = Field(
        default_factory=list, description="Subtasks to create"
    )
    followup_questions: list[str] = Field(
        default_factory=list,
        description="Any remaining questions (empty = refinement complete)",
    )
