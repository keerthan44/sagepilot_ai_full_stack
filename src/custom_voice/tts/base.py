"""Base TTS implementation."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterable
from typing import Any

from livekit import rtc

from ..protocols import TTSProtocol


class BaseTTS(TTSProtocol, ABC):
    """
    Base class for Text-to-Speech implementations.
    
    Provides common functionality for both WebSocket and HTTP transports.
    """
    
    def __init__(
        self,
        *,
        model: str,
        voice: str,
        sample_rate: int = 24000,
    ):
        """
        Initialize base TTS.
        
        Args:
            model: Model identifier
            voice: Voice identifier
            sample_rate: Audio sample rate in Hz
        """
        self._model = model
        self._voice = voice
        self._sample_rate = sample_rate
        self._closed = False
        self._cancelled = False
        self._cancel_event = asyncio.Event()
    
    @property
    def model(self) -> str:
        """Get the model identifier."""
        return self._model
    
    @property
    def voice(self) -> str:
        """Get the voice identifier."""
        return self._voice
    
    @property
    def sample_rate(self) -> int:
        """Get the sample rate."""
        return self._sample_rate
    
    @abstractmethod
    async def synthesize_stream(
        self,
        text: str | AsyncIterable[str],
    ) -> AsyncIterable[rtc.AudioFrame]:
        """Synthesize speech with streaming (must be implemented by subclass)."""
        ...
    
    @abstractmethod
    async def synthesize(self, text: str) -> list[rtc.AudioFrame]:
        """Synthesize complete speech (must be implemented by subclass)."""
        ...
    
    async def configure(self, **kwargs: Any) -> None:
        """Configure the TTS component."""
        if "model" in kwargs:
            self._model = kwargs["model"]
        if "voice" in kwargs:
            self._voice = kwargs["voice"]
        if "sample_rate" in kwargs:
            self._sample_rate = kwargs["sample_rate"]
    
    async def close(self) -> None:
        """Close and cleanup the TTS component."""
        self._closed = True
        await self.cancel()
    
    async def cancel(self) -> None:
        """Cancel ongoing synthesis."""
        self._cancelled = True
        self._cancel_event.set()
    
    def _reset_cancel(self) -> None:
        """Reset cancellation state."""
        self._cancelled = False
        self._cancel_event.clear()
    
    def _check_closed(self) -> None:
        """Check if TTS is closed and raise error if so."""
        if self._closed:
            raise RuntimeError("TTS is closed")
    
    def _check_cancelled(self) -> bool:
        """Check if synthesis is cancelled."""
        return self._cancelled
