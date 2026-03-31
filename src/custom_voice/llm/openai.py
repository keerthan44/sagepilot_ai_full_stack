"""OpenAI LLM implementation using LangChain."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterable
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI

from ..protocols import LLMMessage, LLMResponse
from .base import BaseLLM

logger = logging.getLogger("custom-agent")


class OpenAILLM(BaseLLM):
    """
    OpenAI Large Language Model implementation using LangChain.
    
    Supports streaming and function calling.
    """
    
    def __init__(
        self,
        *,
        model: str = "gpt-4.1-mini",
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ):
        """
        Initialize OpenAI LLM with LangChain.
        
        Args:
            model: OpenAI model name (e.g., "gpt-4", "gpt-4.1-mini")
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional LangChain ChatOpenAI parameters
        """
        super().__init__(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        # Get API key
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment "
                "variable or pass api_key parameter."
            )
        
        # Initialize LangChain ChatOpenAI
        self._llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
            **kwargs,
        )
    
    def _convert_messages(
        self,
        messages: list[LLMMessage],
    ) -> list[BaseMessage]:
        """Convert LLMMessage objects to LangChain format."""
        converted = []
        logger.debug("OpenAILLM: converting messages to LangChain format (messages=%d)", len(messages))
        
        for msg in messages:
            if msg.role == "system":
                converted.append(SystemMessage(content=msg.content))
            elif msg.role == "user":
                converted.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                # Handle tool calls if present
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
                # Tool response message
                converted.append(
                    ToolMessage(
                        content=msg.content,
                        tool_call_id=msg.tool_call_id or "",
                    )
                )
        
        return converted
    
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[str]:
        """
        Generate a streaming response from OpenAI via LangChain.
        
        Args:
            messages: Conversation history
            tools: Optional function tools
            **kwargs: Additional generation parameters
            
        Yields:
            Text chunks as they are generated
        """
        self._check_closed()
        self._reset_cancel()
        
        # Convert messages to LangChain format
        lc_messages = self._convert_messages(messages)
        logger.info(f"LangChain Messages: {[type(m).__name__ for m in lc_messages]}")
        
        # Update LLM parameters if provided
        llm = self._llm
        if kwargs.get("temperature") is not None:
            llm = llm.bind(temperature=kwargs["temperature"])
        
        logger.info(
            "OpenAILLM: starting generation (model=%s, messages=%d)",
            self._model,
            len(lc_messages),
        )
        
        token_count = 0
        try:
            # Stream tokens from LangChain
            async for chunk in llm.astream(lc_messages):
                if self._check_cancelled():
                    logger.info("OpenAILLM: generation cancelled after %d tokens", token_count)
                    break
                
                # Extract content from AIMessageChunk
                if hasattr(chunk, "content") and chunk.content:
                    token_count += 1
                    if token_count == 1:
                        logger.debug("OpenAILLM: first token received")
                    yield chunk.content
        except asyncio.CancelledError:
            logger.info("OpenAILLM: generation cancelled via CancelledError after %d tokens", token_count)
            raise
        finally:
            logger.info("OpenAILLM: generation complete (%d token chunks)", token_count)
    
    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a complete response from OpenAI via LangChain.
        
        Args:
            messages: Conversation history
            tools: Optional function tools
            **kwargs: Additional generation parameters
            
        Returns:
            Complete LLM response
        """
        self._check_closed()
        
        # Convert messages to LangChain format
        lc_messages = self._convert_messages(messages)
        
        # Update LLM parameters if provided
        llm = self._llm
        if kwargs.get("temperature") is not None:
            llm = llm.bind(temperature=kwargs["temperature"])
        
        # Get response from LangChain
        response = await llm.ainvoke(lc_messages)
        
        # Parse response
        content = response.content if isinstance(response.content, str) else ""
        
        # Extract tool calls if present
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
        
        # LangChain doesn't provide usage info in the response object by default
        # We'd need to use callbacks to capture it, so we'll leave it as None
        usage = None
        
        return LLMResponse(
            content=content,
            finish_reason="stop",  # LangChain doesn't expose finish_reason directly
            tool_calls=tool_calls,
            usage=usage,
        )
    
    async def close(self) -> None:
        """Close and cleanup."""
        await super().close()
        # LangChain ChatOpenAI doesn't require explicit cleanup
