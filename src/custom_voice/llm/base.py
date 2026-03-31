"""Base LLM implementation."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterable
from typing import Any

from ..protocols import LLMMessage, LLMProtocol, LLMResponse


class BaseLLM(LLMProtocol, ABC):
    """
    Base class for Large Language Model implementations.
    
    Provides common functionality for LLM providers.
    """
    
    def __init__(
        self,
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ):
        """
        Initialize base LLM.
        
        Args:
            model: Model identifier
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
        """
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._closed = False
        self._cancelled = False
        self._cancel_event = asyncio.Event()
    
    @property
    def model(self) -> str:
        """Get the model identifier."""
        return self._model
    
    @property
    def temperature(self) -> float:
        """Get the temperature."""
        return self._temperature
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[str]:
        """Generate streaming response (must be implemented by subclass)."""
        ...
    
    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate complete response (must be implemented by subclass)."""
        ...
    
    async def configure(self, **kwargs: Any) -> None:
        """Configure the LLM component."""
        if "model" in kwargs:
            self._model = kwargs["model"]
        if "temperature" in kwargs:
            self._temperature = kwargs["temperature"]
        if "max_tokens" in kwargs:
            self._max_tokens = kwargs["max_tokens"]
    
    async def close(self) -> None:
        """Close and cleanup the LLM component."""
        self._closed = True
        await self.cancel()
    
    async def cancel(self) -> None:
        """Cancel ongoing generation."""
        self._cancelled = True
        self._cancel_event.set()
    
    def _reset_cancel(self) -> None:
        """Reset cancellation state."""
        self._cancelled = False
        self._cancel_event.clear()
    
    def _check_closed(self) -> None:
        """Check if LLM is closed and raise error if so."""
        if self._closed:
            raise RuntimeError("LLM is closed")
    
    def _check_cancelled(self) -> bool:
        """Check if generation is cancelled."""
        return self._cancelled
