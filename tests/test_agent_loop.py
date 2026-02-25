"""Tests for the agent loop in the refinement service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.refinement_service import run_agent_loop


class TestAgentLoop:
    """Tests for the agent loop orchestration."""

    @pytest.mark.asyncio
    @patch("app.services.refinement_service.call_llm_with_tools")
    @patch("app.services.refinement_service.mcp_jira_client")
    async def test_immediate_response_no_tool_calls(
        self, mock_mcp, mock_llm
    ):
        """If the LLM responds without tool calls, loop should exit immediately."""
        mock_mcp.get_tools_as_openai_functions.return_value = []

        # LLM returns a final text response (no tool calls)
        mock_response = MagicMock()
        mock_response.wants_tool_calls = False
        mock_response.final_text = "Done! I've refined the ticket."
        mock_llm.return_value = mock_response

        result = await run_agent_loop("PROJ-1", "first_pass")

        assert result == "Done! I've refined the ticket."
        mock_llm.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.refinement_service.call_llm_with_tools")
    @patch("app.services.refinement_service.mcp_jira_client")
    async def test_single_tool_call_then_response(
        self, mock_mcp, mock_llm
    ):
        """Agent should execute a tool call and then get the final response."""
        mock_mcp.get_tools_as_openai_functions.return_value = [
            {
                "type": "function",
                "function": {
                    "name": "jira_get_issue",
                    "description": "Get issue",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        mock_mcp.call_tool = AsyncMock(return_value='{"key": "PROJ-1", "summary": "Test"}')

        # First call: LLM wants to call a tool
        tool_call_mock = MagicMock()
        tool_call_mock.id = "call_123"
        tool_call_mock.name = "jira_get_issue"
        tool_call_mock.arguments = {"issue_key": "PROJ-1"}

        first_response = MagicMock()
        first_response.wants_tool_calls = True
        first_response.tool_calls = [tool_call_mock]
        first_response.assistant_message = MagicMock()
        first_response.assistant_message.content = ""
        first_response.assistant_message.tool_calls = [
            MagicMock(
                id="call_123",
                function=MagicMock(
                    name="jira_get_issue",
                    arguments='{"issue_key": "PROJ-1"}',
                ),
            )
        ]

        # Second call: LLM returns final response
        second_response = MagicMock()
        second_response.wants_tool_calls = False
        second_response.final_text = "Refinement complete."

        mock_llm.side_effect = [first_response, second_response]

        result = await run_agent_loop("PROJ-1", "first_pass")

        assert result == "Refinement complete."
        assert mock_llm.call_count == 2
        mock_mcp.call_tool.assert_called_once_with(
            "jira_get_issue", {"issue_key": "PROJ-1"}
        )

    @pytest.mark.asyncio
    @patch("app.services.refinement_service.call_llm_with_tools")
    @patch("app.services.refinement_service.mcp_jira_client")
    async def test_tool_call_error_is_fed_back(
        self, mock_mcp, mock_llm
    ):
        """If a tool call fails, the error should be fed back to the LLM."""
        mock_mcp.get_tools_as_openai_functions.return_value = []
        mock_mcp.call_tool = AsyncMock(
            side_effect=RuntimeError("Issue not found")
        )

        # First call: tool call
        tool_call_mock = MagicMock()
        tool_call_mock.id = "call_456"
        tool_call_mock.name = "jira_get_issue"
        tool_call_mock.arguments = {"issue_key": "MISSING-1"}

        first_response = MagicMock()
        first_response.wants_tool_calls = True
        first_response.tool_calls = [tool_call_mock]
        first_response.assistant_message = MagicMock()
        first_response.assistant_message.content = ""
        first_response.assistant_message.tool_calls = [
            MagicMock(
                id="call_456",
                function=MagicMock(
                    name="jira_get_issue",
                    arguments='{"issue_key": "MISSING-1"}',
                ),
            )
        ]

        # Second call: LLM recovers
        second_response = MagicMock()
        second_response.wants_tool_calls = False
        second_response.final_text = "Could not find the issue."

        mock_llm.side_effect = [first_response, second_response]

        result = await run_agent_loop("MISSING-1", "first_pass")

        assert "Could not find the issue" in result

    @pytest.mark.asyncio
    @patch("app.services.refinement_service.MAX_AGENT_ITERATIONS", 2)
    @patch("app.services.refinement_service.call_llm_with_tools")
    @patch("app.services.refinement_service.mcp_jira_client")
    async def test_max_iterations_safety(
        self, mock_mcp, mock_llm
    ):
        """Agent loop should stop after max iterations."""
        mock_mcp.get_tools_as_openai_functions.return_value = []
        mock_mcp.call_tool = AsyncMock(return_value="ok")

        # Every call returns a tool call (infinite loop scenario)
        tool_call_mock = MagicMock()
        tool_call_mock.id = "call_loop"
        tool_call_mock.name = "jira_search"
        tool_call_mock.arguments = {"jql": "project=PROJ"}

        response = MagicMock()
        response.wants_tool_calls = True
        response.tool_calls = [tool_call_mock]
        response.assistant_message = MagicMock()
        response.assistant_message.content = ""
        response.assistant_message.tool_calls = [
            MagicMock(
                id="call_loop",
                function=MagicMock(
                    name="jira_search",
                    arguments='{"jql": "project=PROJ"}',
                ),
            )
        ]

        mock_llm.return_value = response

        result = await run_agent_loop("PROJ-1", "first_pass")

        assert "maximum iterations" in result
        assert mock_llm.call_count == 2

    @pytest.mark.asyncio
    @patch("app.services.refinement_service.call_llm_with_tools")
    @patch("app.services.refinement_service.mcp_jira_client")
    async def test_pm_feedback_mode(
        self, mock_mcp, mock_llm
    ):
        """pm_feedback mode should pass pm_comment to the prompt."""
        mock_mcp.get_tools_as_openai_functions.return_value = []

        mock_response = MagicMock()
        mock_response.wants_tool_calls = False
        mock_response.final_text = "Feedback incorporated."
        mock_llm.return_value = mock_response

        result = await run_agent_loop(
            "PROJ-2", "pm_feedback", pm_comment="Yes to all"
        )

        assert result == "Feedback incorporated."
        # Verify the pm_comment was passed in the messages
        call_args = mock_llm.call_args
        messages = call_args[0][0]
        user_msg = messages[-1]["content"]
        assert "Yes to all" in user_msg
