"""
MCP client — manages the mcp-atlassian subprocess and provides
async tool-calling interface for Jira operations.
"""

from __future__ import annotations

import json
import os
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from structlog import get_logger

from app.core.config import settings

logger = get_logger()


class MCPJiraClient:
    """Async MCP client that communicates with mcp-atlassian over stdio."""

    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._tools: list[types.Tool] = []

    async def start(self) -> None:
        """Start the mcp-atlassian subprocess and initialize the session."""
        # Build environment for the MCP server subprocess
        env = {
            **os.environ,
            "JIRA_URL": settings.JIRA_BASE_URL,
            "JIRA_USERNAME": settings.JIRA_USER_EMAIL,
            "JIRA_API_TOKEN": settings.JIRA_API_TOKEN,
        }

        server_params = StdioServerParameters(
            command="uvx",
            args=["mcp-atlassian"],
            env=env,
        )

        self._exit_stack = AsyncExitStack()
        read, write = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()

        # Cache available tools
        result = await self._session.list_tools()
        self._tools = result.tools
        tool_names = [t.name for t in self._tools]
        logger.info("mcp_client_started", tools=tool_names)

    async def stop(self) -> None:
        """Shut down the MCP session and subprocess."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._session = None
            self._exit_stack = None
            logger.info("mcp_client_stopped")

    @property
    def is_connected(self) -> bool:
        return self._session is not None

    def get_tools(self) -> list[types.Tool]:
        """Return the list of available MCP tools."""
        return self._tools

    def get_tools_as_openai_functions(self) -> list[dict]:
        """Convert MCP tool schemas to OpenAI function-calling format."""
        functions = []
        for tool in self._tools:
            func = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                },
            }
            if tool.inputSchema:
                func["function"]["parameters"] = tool.inputSchema
            else:
                func["function"]["parameters"] = {
                    "type": "object",
                    "properties": {},
                }
            functions.append(func)
        return functions

    async def call_tool(self, name: str, arguments: dict | None = None) -> str:
        """Call an MCP tool and return the text result.

        Args:
            name: Tool name (e.g., 'jira_get_issue').
            arguments: Tool arguments dict.

        Returns:
            Combined text content from the tool result.

        Raises:
            RuntimeError: If client is not connected.
            Exception: If the tool call fails.
        """
        if not self._session:
            raise RuntimeError("MCP client not connected. Call start() first.")

        logger.info("mcp_tool_call", tool=name, arguments=arguments)
        result = await self._session.call_tool(name, arguments=arguments or {})

        if result.isError:
            error_text = _extract_text(result)
            logger.error("mcp_tool_error", tool=name, error=error_text)
            raise RuntimeError(f"MCP tool '{name}' failed: {error_text}")

        text = _extract_text(result)
        logger.debug("mcp_tool_result", tool=name, result_len=len(text))
        return text


def _extract_text(result: types.CallToolResult) -> str:
    """Extract all text content from an MCP tool result."""
    parts = []
    for content in result.content:
        if isinstance(content, types.TextContent):
            parts.append(content.text)
    return "\n".join(parts)


# Singleton
mcp_jira_client = MCPJiraClient()
