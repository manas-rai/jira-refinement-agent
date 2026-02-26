"""Tests for the MCP client wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jira.mcp_client import MCPJiraClient


class TestMCPJiraClient:
    """Tests for the MCPJiraClient class."""

    def test_initial_state(self):
        """Client should start disconnected with no tools."""
        client = MCPJiraClient()
        assert not client.is_connected
        assert client.get_tools() == []
        assert client.get_tools_as_openai_functions() == []

    @pytest.mark.asyncio
    async def test_call_tool_requires_connection(self):
        """call_tool should raise if client is not started."""
        client = MCPJiraClient()
        with pytest.raises(RuntimeError, match="not connected"):
            await client.call_tool("jira_get_issue", {"issue_key": "PROJ-1"})

    def test_get_tools_as_openai_functions(self):
        """Should convert MCP tool schemas to OpenAI function-calling format."""
        client = MCPJiraClient()

        # Create mock tools
        mock_tool = MagicMock()
        mock_tool.name = "jira_get_issue"
        mock_tool.description = "Get a Jira issue by key"
        mock_tool.inputSchema = {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "The issue key"}
            },
            "required": ["issue_key"],
        }

        client._tools = [mock_tool]

        result = client.get_tools_as_openai_functions()
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "jira_get_issue"
        assert result[0]["function"]["description"] == "Get a Jira issue by key"
        assert "properties" in result[0]["function"]["parameters"]

    def test_get_tools_as_openai_functions_no_schema(self):
        """Should handle tools with no input schema."""
        client = MCPJiraClient()

        mock_tool = MagicMock()
        mock_tool.name = "jira_get_issue"  # Must be in CORE_TOOLS
        mock_tool.description = "Get a Jira issue"
        mock_tool.inputSchema = None

        client._tools = [mock_tool]

        result = client.get_tools_as_openai_functions()
        assert result[0]["function"]["parameters"] == {
            "type": "object",
            "properties": {},
        }
