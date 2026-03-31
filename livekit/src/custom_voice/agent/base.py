"""Base agent class.

An agent owns its system prompt and its tools. Everything else (STT, TTS,
VAD, turn detection) is managed at the session level.

Usage
-----
    class MyAgent(BaseAgent):
        name = "my_agent"
        instructions = "You are..."

        @tool
        async def do_something(self, x: str) -> str:
            "Do something useful."
            return f"done: {x}"

        @property
        def tools(self):
            return [self.do_something]
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.tools import BaseTool

logger = logging.getLogger("custom-agent")

# Dispatcher type: (tool_name, args_dict) -> result string
ToolHandler = Callable[[str, dict[str, Any]], Awaitable[str]]


class BaseAgent(ABC):
    """
    Abstract base class for voice agents.

    Subclasses must define:
    - ``name``         — unique registry key (class attribute)
    - ``instructions`` — system prompt (class attribute)
    - ``tools``        — list of LangChain BaseTool instances (property)
    """

    #: Unique name used by the factory to look up this agent.
    name: str

    #: System prompt injected at the start of every session.
    instructions: str

    @property
    @abstractmethod
    def tools(self) -> list[BaseTool]:
        """Return all tools available to this agent."""
        ...

    # ------------------------------------------------------------------
    # Helpers consumed by the session / LLM
    # ------------------------------------------------------------------

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        Return tool schemas in OpenAI function-calling format.
        LangChain's BaseTool.args_schema is used automatically.
        """
        definitions = []
        for t in self.tools:
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.args_schema.model_json_schema()
                        if t.args_schema
                        else {"type": "object", "properties": {}},
                    },
                }
            )
        return definitions

    def make_tool_handler(self) -> ToolHandler:
        """
        Return an async dispatcher ``(name, args) -> str`` that routes
        calls to the correct LangChain tool via ``ainvoke``.

        Pass this to ``OpenAILLM`` so it can execute tools during the
        streaming agentic loop.
        """
        tool_map: dict[str, BaseTool] = {t.name: t for t in self.tools}

        async def _dispatch(name: str, args: dict[str, Any]) -> str:
            tool = tool_map.get(name)
            if tool is None:
                logger.warning("BaseAgent: unknown tool %r requested", name)
                return f"Unknown tool: {name}"
            try:
                result = await tool.ainvoke(args)
                if isinstance(result, str):
                    return result
                if hasattr(result, "content"):
                    content = result.content
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        return " ".join(
                            b.get("text", "") if isinstance(b, dict) else str(b)
                            for b in content
                        )
                return json.dumps(result)
            except Exception:
                logger.exception("BaseAgent: tool %r raised an error", name)
                return f"Error executing tool {name}."

        return _dispatch
