"""
LLM client — async wrapper around OpenAI-compatible chat completions API
with JSON mode and function-calling support for agent loops.
"""

import json

from openai import AsyncOpenAI
from pydantic import BaseModel
from structlog import get_logger

from app.core.config import settings

logger = get_logger()

_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL,
)


async def call_llm(
    messages: list[dict],
    response_model: type[BaseModel],
) -> BaseModel:
    """Call the LLM with JSON mode and parse into a Pydantic model.

    Args:
        messages: Chat-style messages list.
        response_model: Pydantic model to validate the JSON output.

    Returns:
        Parsed and validated Pydantic model instance.
    """
    logger.info(
        "llm_call_start",
        model=settings.LLM_MODEL,
        messages_count=len(messages),
    )

    response = await _client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw = response.choices[0].message.content
    logger.debug("llm_raw_response", raw=raw[:500])

    parsed = json.loads(raw)
    result = response_model.model_validate(parsed)

    logger.info(
        "llm_call_complete",
        model=settings.LLM_MODEL,
        tokens_prompt=response.usage.prompt_tokens if response.usage else None,
        tokens_completion=response.usage.completion_tokens if response.usage else None,
    )

    return result


async def call_llm_with_tools(
    messages: list[dict],
    tools: list[dict],
) -> "LLMToolResponse":
    """Call the LLM with function-calling tools.

    Returns either tool calls to execute or a final text response.
    Does NOT loop — the caller (agent loop) handles iteration.

    Args:
        messages: Chat-style messages list.
        tools: OpenAI-format tool definitions.

    Returns:
        LLMToolResponse with either tool_calls or final_text.
    """
    logger.info(
        "llm_tool_call_start",
        model=settings.LLM_MODEL,
        messages_count=len(messages),
        tools_count=len(tools),
    )

    response = await _client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        tools=tools if tools else None,
        temperature=0.3,
    )

    choice = response.choices[0]
    message = choice.message

    logger.info(
        "llm_tool_call_complete",
        model=settings.LLM_MODEL,
        finish_reason=choice.finish_reason,
        has_tool_calls=bool(message.tool_calls),
        tokens_prompt=response.usage.prompt_tokens if response.usage else None,
        tokens_completion=response.usage.completion_tokens if response.usage else None,
    )

    if message.tool_calls:
        calls = []
        for tc in message.tool_calls:
            calls.append(ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments),
            ))
        return LLMToolResponse(
            tool_calls=calls,
            assistant_message=message,
        )

    return LLMToolResponse(
        final_text=message.content or "",
        assistant_message=message,
    )


class ToolCall:
    """A single tool call requested by the LLM."""

    def __init__(self, id: str, name: str, arguments: dict):
        self.id = id
        self.name = name
        self.arguments = arguments

    def __repr__(self) -> str:
        return f"ToolCall(id={self.id!r}, name={self.name!r}, arguments={self.arguments!r})"


class LLMToolResponse:
    """Response from a tool-calling LLM invocation."""

    def __init__(
        self,
        tool_calls: list[ToolCall] | None = None,
        final_text: str | None = None,
        assistant_message=None,
    ):
        self.tool_calls = tool_calls
        self.final_text = final_text
        self.assistant_message = assistant_message

    @property
    def wants_tool_calls(self) -> bool:
        return bool(self.tool_calls)
