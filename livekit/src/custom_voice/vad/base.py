"""Base VAD implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from livekit import rtc

from ..protocols import VADProtocol, VADSignal


class BaseVAD(VADProtocol, ABC):
    """
    Base class for Voice Activity Detection implementations.
    
    Provides common functionality for VAD providers.
    """
    
    def __init__(
        self,
        *,
        threshold: float = 0.5,
        min_speech_duration: float = 0.1,
        min_silence_duration: float = 0.5,
    ):
        """
        Initialize base VAD.
        
        Args:
            threshold: Speech probability threshold (0.0 to 1.0)
            min_speech_duration: Minimum speech duration in seconds
            min_silence_duration: Minimum silence duration in seconds
        """
        self._threshold = threshold
        self._min_speech_duration = min_speech_duration
        self._min_silence_duration = min_silence_duration
        self._is_speaking = False
    
    @property
    def threshold(self) -> float:
        """Get the speech threshold."""
        return self._threshold
    
    @property
    def is_speaking(self) -> bool:
        """Check if currently detecting speech."""
        return self._is_speaking
    
    @abstractmethod
    async def process_audio(
        self,
        audio_frame: rtc.AudioFrame,
    ) -> VADSignal:
        """Process audio frame (must be implemented by subclass)."""
        ...
    
    async def configure(self, **kwargs: Any) -> None:
        """Configure the VAD component."""
        if "threshold" in kwargs:
            self._threshold = kwargs["threshold"]
        if "min_speech_duration" in kwargs:
            self._min_speech_duration = kwargs["min_speech_duration"]
        if "min_silence_duration" in kwargs:
            self._min_silence_duration = kwargs["min_silence_duration"]
    
    def reset(self) -> None:
        """Reset VAD state."""
        self._is_speaking = False
