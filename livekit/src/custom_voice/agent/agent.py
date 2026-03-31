"""Agent configuration.

Define agents with their instructions and tools.  Tools are plain async Python
functions decorated with LangChain's @tool, so the schema is inferred from
type hints and docstrings — no manual JSON schema required.

Example
-------
    from langchain_core.tools import tool
    from custom_voice.agent import AgentConfig

    @tool
    async def get_weather(location: str) -> str:
        "Get the current weather for a location."
        return f"Sunny in {location}."

    agent = AgentConfig(
        name="assistant",
        instructions="You are a helpful assistant.",
        tools=[get_weather],
    )
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool

from ..config import LLMConfig, STTConfig, TTSConfig

logger = logging.getLogger("custom-agent")

# Dispatcher type used by OpenAILLM
ToolHandler = Callable[[str, dict[str, Any]], Awaitable[str]]


@dataclass
class AgentConfig:
    """
    Configuration for a single agent.

    Attributes:
        name:         Unique agent identifier used in the registry.
        instructions: System prompt the LLM receives at the start of each session.
        tools:        LangChain BaseTool instances (use the @tool decorator).
                      Schema, name, and description are inferred automatically.
        stt_config:   Optional STT override (defaults to the session-level config).
        tts_config:   Optional TTS override (defaults to the session-level config).
        llm_config:   Optional LLM override (defaults to the session-level config).
    """

    name: str
    instructions: str
    tools: list[BaseTool] = field(default_factory=list)
    stt_config: STTConfig | None = None
    tts_config: TTSConfig | None = None
    llm_config: LLMConfig | None = None

    def make_tool_handler(self) -> ToolHandler:
        """
        Return an async dispatcher ``(tool_name, args) -> str`` that routes
        calls to the matching LangChain tool via ``tool.ainvoke()``.

        Pass this to ``create_llm(tool_handler=agent.make_tool_handler())``.
        """
        tool_map: dict[str, BaseTool] = {t.name: t for t in self.tools}

        async def _dispatch(name: str, args: dict[str, Any]) -> str:
            tool = tool_map.get(name)
            if tool is None:
                logger.warning("AgentConfig: unknown tool %r requested", name)
                return f"Unknown tool: {name}"
            try:
                result = await tool.ainvoke(args)
                # ainvoke may return a ToolMessage or a plain string
                if isinstance(result, str):
                    return result
                # ToolMessage / AIMessage has a .content attribute
                if hasattr(result, "content"):
                    content = result.content
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        # content blocks — join text parts
                        return " ".join(
                            block.get("text", "") if isinstance(block, dict) else str(block)
                            for block in content
                        )
                return json.dumps(result) if not isinstance(result, str) else result
            except Exception:
                logger.exception("AgentConfig: tool %r raised an error", name)
                return f"Error executing tool {name}."

        return _dispatch
