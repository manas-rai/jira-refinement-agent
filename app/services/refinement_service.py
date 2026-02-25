"""
Refinement service — orchestrates ticket refinement via an LLM agent loop
that uses MCP tools to interact with Jira.

The LLM autonomously reads issues, searches for context, posts comments,
updates descriptions, and creates subtasks — all through MCP tool calls.
"""

import json

from structlog import get_logger

from app.core.config import load_domain_config, settings
from app.jira.mcp_client import mcp_jira_client
from app.llm.client import call_llm_with_tools
from app.llm.prompts import build_agent_prompt
from app.models.domain import DomainConfig
from app.models.jira_models import WebhookPayload

logger = get_logger()

# Maximum number of tool-call iterations to prevent runaway loops
MAX_AGENT_ITERATIONS = 15


async def handle_webhook(payload: WebhookPayload) -> None:
    """Main dispatcher — runs the agent loop for the given issue."""
    logger.info("webhook_received", issue=payload.issue_key, mode=payload.mode)

    await run_agent_loop(
        issue_key=payload.issue_key,
        mode=payload.mode,
        pm_comment=payload.pm_comment,
    )


async def run_agent_loop(
    issue_key: str,
    mode: str,
    pm_comment: str | None = None,
) -> str:
    """Run the LLM agent loop with MCP tools.

    The LLM decides which Jira tools to call. The loop continues until
    the LLM returns a final text response (no more tool calls) or
    the iteration limit is reached.

    Args:
        issue_key: Jira issue key (e.g., "PROJ-123").
        mode: "first_pass" or "pm_feedback".
        pm_comment: PM's comment text (only for pm_feedback mode).

    Returns:
        The LLM's final summary text.
    """
    domain_config = _get_domain_config()

    # Build initial messages with agent instructions
    messages = build_agent_prompt(issue_key, mode, pm_comment, domain_config)

    # Get available MCP tools as OpenAI function definitions
    tools = mcp_jira_client.get_tools_as_openai_functions()

    logger.info(
        "agent_loop_start",
        issue=issue_key,
        mode=mode,
        available_tools=len(tools),
    )

    for iteration in range(MAX_AGENT_ITERATIONS):
        logger.info("agent_iteration", iteration=iteration + 1)

        # Call the LLM
        response = await call_llm_with_tools(messages, tools)

        if not response.wants_tool_calls:
            # LLM is done — returned a final text response
            logger.info(
                "agent_loop_complete",
                issue=issue_key,
                iterations=iteration + 1,
                summary=response.final_text[:200] if response.final_text else "",
            )
            return response.final_text or ""

        # Add the assistant's message (with tool calls) to the conversation
        messages.append(_assistant_message_to_dict(response.assistant_message))

        # Execute each tool call via MCP and add results to messages
        for tool_call in response.tool_calls:
            logger.info(
                "agent_tool_call",
                tool=tool_call.name,
                arguments=tool_call.arguments,
            )

            try:
                result = await mcp_jira_client.call_tool(
                    tool_call.name, tool_call.arguments
                )
            except Exception as e:
                result = f"Error calling tool '{tool_call.name}': {e}"
                logger.exception(
                    "agent_tool_call_failed",
                    tool=tool_call.name,
                    error=str(e),
                )

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    # Safety: hit iteration limit
    logger.warning(
        "agent_loop_max_iterations",
        issue=issue_key,
        max_iterations=MAX_AGENT_ITERATIONS,
    )
    return f"Agent reached maximum iterations ({MAX_AGENT_ITERATIONS}) for {issue_key}."


def _assistant_message_to_dict(message) -> dict:
    """Convert an OpenAI assistant message object to a dict for the messages list."""
    msg = {"role": "assistant", "content": message.content or ""}

    if message.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ]

    return msg


def _get_domain_config() -> DomainConfig:
    """Load and validate domain config."""
    raw = load_domain_config()
    return DomainConfig.model_validate(raw)
