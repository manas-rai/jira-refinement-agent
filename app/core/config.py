"""
Application configuration — all settings loaded from environment variables.
"""

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env / environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_parse_none_str="",
    )

    # ── Jira ────────────────────────────────────────────
    JIRA_BASE_URL: str = "https://your-org.atlassian.net"
    JIRA_USER_EMAIL: str = ""
    JIRA_API_TOKEN: str = ""
    JIRA_REFINEMENT_STATE_FIELD: str = "customfield_10050"

    # ── MCP ─────────────────────────────────────────────
    MCP_ATLASSIAN_COMMAND: str = "uvx"
    MCP_ATLASSIAN_ARGS: str = "mcp-atlassian"

    # ── Webhook ─────────────────────────────────────────
    WEBHOOK_SECRET: str = "change-me"

    # ── LLM ─────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o"

    # ── App ─────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    DOMAIN_CONFIG_PATH: str = "domain_config.yaml"
    CORS_ORIGINS: str = "http://localhost:3000"

    # ── Derived helpers ─────────────────────────────────
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # ── Bot display name used in Jira comments ──────────
    BOT_DISPLAY_NAME: str = Field(
        default="🤖 Refinement Agent",
        description="Name shown at the top of bot comments",
    )


settings = Settings()


def load_domain_config() -> dict:
    """Load the YAML domain config file."""
    path = Path(settings.DOMAIN_CONFIG_PATH)
    if not path.exists():
        return {}
    with path.open() as f:
        return yaml.safe_load(f) or {}
