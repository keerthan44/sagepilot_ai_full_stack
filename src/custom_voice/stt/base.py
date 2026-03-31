"""Base STT implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterable
from typing import Any

from livekit import rtc

from ..protocols import STTProtocol, TranscriptSegment


class BaseSTT(STTProtocol, ABC):
    """
    Base class for Speech-to-Text implementations.
    
    Provides common functionality for both WebSocket and HTTP transports.
    """
    
    def __init__(
        self,
        *,
        model: str,
        language: str | None = None,
        sample_rate: int = 16000,
        interim_results: bool = True,
    ):
        """
        Initialize base STT.
        
        Args:
            model: Model identifier
            language: Language code (None for auto-detect)
            sample_rate: Audio sample rate in Hz
            interim_results: Whether to return interim results
        """
        self._model = model
        self._language = language
        self._sample_rate = sample_rate
        self._interim_results = interim_results
        self._closed = False
    
    @property
    def model(self) -> str:
        """Get the model identifier."""
        return self._model
    
    @property
    def language(self) -> str | None:
        """Get the language code."""
        return self._language
    
    @property
    def sample_rate(self) -> int:
        """Get the sample rate."""
        return self._sample_rate
    
    @abstractmethod
    async def recognize_stream(
        self,
        audio_stream: AsyncIterable[rtc.AudioFrame],
    ) -> AsyncIterable[TranscriptSegment]:
        """Recognize speech from audio stream (must be implemented by subclass)."""
        ...
    
    async def configure(self, **kwargs: Any) -> None:
        """Configure the STT component."""
        if "model" in kwargs:
            self._model = kwargs["model"]
        if "language" in kwargs:
            self._language = kwargs["language"]
        if "sample_rate" in kwargs:
            self._sample_rate = kwargs["sample_rate"]
        if "interim_results" in kwargs:
            self._interim_results = kwargs["interim_results"]
    
    async def close(self) -> None:
        """Close and cleanup the STT component."""
        self._closed = True
    
    def _check_closed(self) -> None:
        """Check if STT is closed and raise error if so."""
        if self._closed:
            raise RuntimeError("STT is closed")
