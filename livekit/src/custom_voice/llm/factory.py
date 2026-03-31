"""Factory for creating LLM instances."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.tools import BaseTool

from ..config import LLMConfig
from ..protocols import LLMProtocol
from .openai import OnToolUse, OpenAILLM

ToolHandler = Callable[[str, dict[str, Any]], Awaitable[str]]


def create_llm(
    provider: str,
    *,
    model: str | None = None,
    temperature: float | None = None,
    config: LLMConfig | None = None,
    tools: list[BaseTool] | list[dict[str, Any]] | None = None,
    tool_handler: ToolHandler | None = None,
    on_tool_use: OnToolUse | None = None,
    **kwargs: Any,
) -> LLMProtocol:
    """
    Create an LLM instance.

    Args:
        provider:      LLM provider name ("openai").
        model:         Model identifier (overrides config).
        temperature:   Sampling temperature (overrides config).
        config:        LLMConfig object (alternative to individual params).
        tools:         LangChain BaseTool list or raw OpenAI schema dicts.
                       The LLM is bound to these so the model knows it can
                       call them.
        tool_handler:  Async callable ``(name, args) -> str`` that executes
                       tool calls.  Typically ``agent.make_tool_handler()``.
        on_tool_use:   Optional async callback fired after each tool round
                       with calls + results for transcript recording.
        **kwargs:      Extra provider-specific parameters.

    Returns:
        LLM instance implementing LLMProtocol.

    Raises:
        ValueError: If provider is not supported.
    """
    if config:
        provider = config.provider
        model = model or config.model
        temperature = temperature if temperature is not None else config.temperature
        kwargs.update(config.extra_params)

    if provider == "openai":
        return OpenAILLM(
            model=model or "gpt-4.1-mini",
            temperature=temperature or 0.7,
            tools=tools,
            tool_handler=tool_handler,
            on_tool_use=on_tool_use,
            **kwargs,
        )

    # Add more providers here:
    # elif provider == "anthropic":
    #     return AnthropicLLM(...)

    raise ValueError(f"Unsupported LLM provider: {provider!r}. Supported: openai")
