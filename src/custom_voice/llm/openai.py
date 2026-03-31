"""OpenAI LLM implementation."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterable
from typing import Any

from openai import AsyncOpenAI

from ..protocols import LLMMessage, LLMResponse
from .base import BaseLLM

logger = logging.getLogger("custom-agent")


class OpenAILLM(BaseLLM):
    """
    OpenAI Large Language Model implementation.
    
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
        Initialize OpenAI LLM.
        
        Args:
            model: OpenAI model name (e.g., "gpt-4", "gpt-4.1-mini")
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenAI client parameters
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
        
        self._client = AsyncOpenAI(api_key=api_key, **kwargs)
    
    def _convert_messages(
        self,
        messages: list[LLMMessage],
    ) -> list[dict[str, Any]]:
        """Convert LLMMessage objects to OpenAI format."""
        converted = []
        logger.debug("OpenAILLM: converting messages to OpenAI format (messages=%d)", len(messages))
        
        for msg in messages:
            openai_msg: dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }
            
            if msg.name:
                openai_msg["name"] = msg.name
            
            if msg.tool_calls:
                openai_msg["tool_calls"] = msg.tool_calls
            
            if msg.tool_call_id:
                openai_msg["tool_call_id"] = msg.tool_call_id
            
            converted.append(openai_msg)
        
        return converted
    
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[str]:
        """
        Generate a streaming response from OpenAI.
        
        Args:
            messages: Conversation history
            tools: Optional function tools
            **kwargs: Additional generation parameters
            
        Yields:
            Text chunks as they are generated
        """
        self._check_closed()
        self._reset_cancel()
        
        # Convert messages
        openai_messages = self._convert_messages(messages)
        logger.info(f"Openai Messages: {openai_messages}")
        
        # Build request parameters
        params: dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self._temperature),
            "stream": True,
        }
        
        if self._max_tokens:
            params["max_tokens"] = self._max_tokens
        
        if tools:
            params["tools"] = tools
        
        logger.info(
            "OpenAILLM: starting generation (model=%s, messages=%d)",
            self._model,
            len(openai_messages),
        )
        stream = await self._client.chat.completions.create(**params)

        token_count = 0
        try:
            async for chunk in stream:
                if self._check_cancelled():
                    logger.info("OpenAILLM: generation cancelled after %d tokens", token_count)
                    break
                
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        token_count += 1
                        if token_count == 1:
                            logger.debug("OpenAILLM: first token received")
                        yield delta.content
        except asyncio.CancelledError:
            logger.info("OpenAILLM: generation cancelled via CancelledError after %d tokens", token_count)
            # Close the stream to abort the HTTP request
            await stream.close()
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
        Generate a complete response from OpenAI.
        
        Args:
            messages: Conversation history
            tools: Optional function tools
            **kwargs: Additional generation parameters
            
        Returns:
            Complete LLM response
        """
        self._check_closed()
        
        # Convert messages
        openai_messages = self._convert_messages(messages)
        
        # Build request parameters
        params: dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self._temperature),
        }
        
        if self._max_tokens:
            params["max_tokens"] = self._max_tokens
        
        if tools:
            params["tools"] = tools
        
        # Get response
        response = await self._client.chat.completions.create(**params)
        
        # Parse response
        choice = response.choices[0]
        message = choice.message
        
        # Extract tool calls if present
        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        
        # Extract usage
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        return LLMResponse(
            content=message.content or "",
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
            usage=usage,
        )
    
    async def close(self) -> None:
        """Close and cleanup."""
        await super().close()
        await self._client.close()
