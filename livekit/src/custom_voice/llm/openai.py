"""OpenAI LLM implementation using LangChain with streaming tool-call support."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterable, Awaitable, Callable
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from ..protocols import LLMMessage, LLMResponse
from .base import BaseLLM

logger = logging.getLogger("custom-agent")

# (tool_name, args_dict) -> result string
ToolHandler = Callable[[str, dict[str, Any]], Awaitable[str]]

# Called after each tool round: (tool_calls, results)
# tool_calls: list of {"name": str, "args": dict, "id": str}
# results:    list of {"tool_call_id": str, "content": str}
OnToolUse = Callable[
    [list[dict[str, Any]], list[dict[str, Any]]],
    Awaitable[None],
]

# Maximum agentic rounds to prevent infinite loops
_MAX_TOOL_ROUNDS = 5


class OpenAILLM(BaseLLM):
    """
    OpenAI LLM via LangChain with streaming + agentic tool-call loop.

    When the model requests one or more tool calls during streaming the LLM:
      1. Accumulates all tool-call chunks to reconstruct the full call.
      2. Executes each tool concurrently via ``tool_handler``.
      3. Appends the assistant + tool-result messages to the context.
      4. Streams the next model response.
    Steps 1-4 repeat until the model produces a final text response
    (finish_reason == "stop") or ``_MAX_TOOL_ROUNDS`` is reached.
    """

    def __init__(
        self,
        *,
        model: str = "gpt-4.1-mini",
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[BaseTool] | list[dict[str, Any]] | None = None,
        tool_handler: ToolHandler | None = None,
        on_tool_use: OnToolUse | None = None,
        **kwargs: Any,
    ):
        """
        Args:
            model:        OpenAI model name.
            api_key:      API key (falls back to OPENAI_API_KEY env var).
            temperature:  Sampling temperature.
            max_tokens:   Max tokens to generate.
            tools:        LangChain BaseTool instances *or* raw OpenAI
                          function-schema dicts.  The LLM is bound to these
                          tools so the model knows it can call them.
            tool_handler: Async callable ``(name, args) -> str`` executed
                          when the model requests a tool call.  Required if
                          ``tools`` is non-empty; raises at call time if
                          a tool is called without a handler.
            on_tool_use:  Optional async callback fired after each tool round
                          with the calls and their results so callers can
                          record them in the conversation transcript.
            **kwargs:     Extra ChatOpenAI parameters.
        """
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)

        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment "
                "variable or pass api_key parameter."
            )

        self._tool_handler = tool_handler
        self._on_tool_use = on_tool_use

        base_llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
            **kwargs,
        )

        # Bind tools so the model knows it can call them
        if tools:
            self._llm = base_llm.bind_tools(tools)
            logger.info(
                "OpenAILLM: bound %d tool(s) — %s",
                len(tools),
                [
                    t.name
                    if isinstance(t, BaseTool)
                    else t.get("function", {}).get("name", "?")
                    for t in tools
                ],
            )
        else:
            self._llm = base_llm

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _convert_messages(self, messages: list[LLMMessage]) -> list[BaseMessage]:
        """Convert LLMMessage list to LangChain BaseMessage list."""
        converted: list[BaseMessage] = []
        for msg in messages:
            if msg.role == "system":
                converted.append(SystemMessage(content=msg.content))
            elif msg.role == "user":
                converted.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                if msg.tool_calls:
                    converted.append(
                        AIMessage(
                            content=msg.content or "",
                            additional_kwargs={"tool_calls": msg.tool_calls},
                        )
                    )
                else:
                    converted.append(AIMessage(content=msg.content))
            elif msg.role == "tool":
                converted.append(
                    ToolMessage(
                        content=msg.content,
                        tool_call_id=msg.tool_call_id or "",
                    )
                )
        return converted

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> tuple[list[ToolMessage], list[dict[str, Any]]]:
        """
        Execute all tool calls concurrently.

        Returns:
            (lc_tool_messages, result_records)
            result_records: list of {"tool_call_id": str, "name": str, "content": str}
            for recording in the conversation transcript.
        """
        if not self._tool_handler:
            logger.warning("OpenAILLM: tool calls requested but no tool_handler set")
            msgs = [
                ToolMessage(
                    content="Tool execution is not configured.",
                    tool_call_id=tc.get("id", ""),
                )
                for tc in tool_calls
            ]
            records = [
                {
                    "tool_call_id": tc.get("id", ""),
                    "name": tc.get("name", ""),
                    "content": "Tool execution is not configured.",
                }
                for tc in tool_calls
            ]
            return msgs, records

        async def _call_one(tc: dict[str, Any]) -> tuple[ToolMessage, dict[str, Any]]:
            name = tc.get("name") or tc.get("function", {}).get("name", "")
            raw_args = tc.get("args") or tc.get("function", {}).get("arguments", {})
            args: dict[str, Any] = (
                json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            )
            tool_call_id = tc.get("id", "")
            logger.info("OpenAILLM: executing tool %r args=%r", name, args)
            result = await self._tool_handler(name, args)
            logger.info(
                "OpenAILLM: tool %r result=%r", name, result[:100] if result else ""
            )
            msg = ToolMessage(content=result, tool_call_id=tool_call_id)
            record = {"tool_call_id": tool_call_id, "name": name, "content": result}
            return msg, record

        pairs = list(await asyncio.gather(*[_call_one(tc) for tc in tool_calls]))
        lc_msgs = [p[0] for p in pairs]
        records = [p[1] for p in pairs]
        return lc_msgs, records

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[str]:
        """
        Stream text tokens, transparently handling tool-call rounds.

        The caller receives only the final user-facing text.  All tool
        execution is handled internally and invisibly.
        """
        self._check_closed()
        self._reset_cancel()

        lc_messages: list[BaseMessage] = self._convert_messages(messages)

        logger.info(
            "OpenAILLM: starting generation (model=%s, messages=%d)",
            self._model,
            len(lc_messages),
        )

        for round_idx in range(_MAX_TOOL_ROUNDS):
            if self._check_cancelled():
                return

            accumulated = None
            token_count = 0

            try:
                async for chunk in self._llm.astream(lc_messages):
                    if self._check_cancelled():
                        logger.info("OpenAILLM: cancelled after %d tokens", token_count)
                        return

                    # Accumulate for tool-call reconstruction
                    accumulated = chunk if accumulated is None else accumulated + chunk

                    # Yield text content to caller immediately
                    if chunk.content:
                        token_count += 1
                        if token_count == 1:
                            logger.debug(
                                "OpenAILLM: first token received (round=%d)", round_idx
                            )
                        yield chunk.content

            except asyncio.CancelledError:
                logger.info("OpenAILLM: CancelledError after %d tokens", token_count)
                raise

            logger.info(
                "OpenAILLM: generation complete (%d token chunks, round=%d)",
                token_count,
                round_idx,
            )

            # No tool calls → we're done
            if accumulated is None or not getattr(accumulated, "tool_calls", None):
                return

            # ----------------------------------------------------------------
            # Tool-call round
            # ----------------------------------------------------------------
            tool_calls = accumulated.tool_calls  # list of dicts from LangChain
            logger.info(
                "OpenAILLM: %d tool call(s) requested: %s",
                len(tool_calls),
                [tc.get("name") for tc in tool_calls],
            )

            # Add assistant message (with tool_calls) to context
            lc_messages.append(accumulated)

            # Execute all tools concurrently
            tool_messages, result_records = await self._execute_tool_calls(tool_calls)

            # Add tool results to context
            lc_messages.extend(tool_messages)

            # Notify caller so it can record in transcript
            if self._on_tool_use:
                call_records = [
                    {
                        "name": tc.get("name", ""),
                        "args": tc.get("args", {}),
                        "id": tc.get("id", ""),
                    }
                    for tc in tool_calls
                ]
                await self._on_tool_use(call_records, result_records)

            # Loop: stream the next response with tool results in context
            logger.info(
                "OpenAILLM: resuming stream after tool execution (round=%d)",
                round_idx + 1,
            )

        logger.warning(
            "OpenAILLM: reached max tool rounds (%d), stopping", _MAX_TOOL_ROUNDS
        )

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a complete (non-streaming) response."""
        self._check_closed()

        lc_messages = self._convert_messages(messages)
        response = await self._llm.ainvoke(lc_messages)

        content = response.content if isinstance(response.content, str) else ""

        tool_calls = None
        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_calls = [
                {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("name", ""),
                        "arguments": tc.get("args", {}),
                    },
                }
                for tc in response.tool_calls
            ]

        return LLMResponse(
            content=content,
            finish_reason="stop",
            tool_calls=tool_calls,
            usage=None,
        )

    async def close(self) -> None:
        """Close and cleanup."""
        await super().close()
