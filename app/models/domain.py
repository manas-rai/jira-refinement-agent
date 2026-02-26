"""
Domain configuration model — loaded from YAML, provides project-specific rules
that shape how the LLM refines tickets.
"""

from pydantic import BaseModel, Field


class Persona(BaseModel):
    name: str
    description: str = ""


class RepoModule(BaseModel):
    """A key module/directory in the repository."""
    name: str
    path: str = ""
    description: str = ""


class DomainConfig(BaseModel):
    """Project-specific configuration that the LLM uses as context."""

    project_name: str = "My Product"

    # ── Repository context ─────────────────────────────
    repo_url: str = Field(default="", description="GitHub/GitLab repo URL")
    tech_stack: list[str] = Field(default_factory=list)
    architecture_notes: str = Field(
        default="", description="Free-text architecture overview"
    )
    key_modules: list[RepoModule] = Field(default_factory=list)

    # ── Ticket structure ───────────────────────────────
    ticket_structure: list[str] = Field(
        default_factory=lambda: [
            "Background",
            "Problem / Current behavior",
            "Desired behavior",
            "Scope",
            "Out of scope",
            "Technical notes (high level)",
            "Risks & impact",
            "Test plan / QA hints",
            "Acceptance criteria",
        ]
    )

    user_personas: list[Persona] = Field(default_factory=list)

    platforms: list[str] = Field(default_factory=list)

    standards: dict[str, str] = Field(
        default_factory=dict,
        description="Key-value pairs like 'performance': 'p95 < 500ms'",
    )

    acceptance_criteria_style: str = Field(
        default="bullet",
        description="'bullet' or 'gherkin'",
    )
