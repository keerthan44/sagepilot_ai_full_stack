"""Base turn detector classes."""

from __future__ import annotations

import time
from abc import ABC
from typing import Any

from livekit import rtc

from ..protocols import (
    AudioTurnDetectorProtocol,
    ConversationTurn,
    TextTurnDetectorProtocol,
)


class BaseTurnDetector(ABC):
    """Base class for all turn detectors with common functionality."""
    
    def __init__(self, threshold: float = 0.5):
        """
        Initialize base turn detector.
        
        Args:
            threshold: Turn completion probability threshold
        """
        self._threshold = threshold
        self._last_reset_time = time.time()
    
    @property
    def threshold(self) -> float:
        """Get the turn completion threshold."""
        return self._threshold
    
    async def configure(self, **kwargs: Any) -> None:
        """Configure the turn detector."""
        if "threshold" in kwargs:
            self._threshold = kwargs["threshold"]
    
    def reset(self) -> None:
        """Reset turn detector state."""
        self._last_reset_time = time.time()


class AudioTurnDetector(BaseTurnDetector, AudioTurnDetectorProtocol):
    """Base class for audio-based turn detectors."""
    
    def __init__(self, threshold: float = 0.5):
        """
        Initialize audio turn detector.
        
        Args:
            threshold: Turn completion probability threshold
        """
        super().__init__(threshold=threshold)


class TextTurnDetector(BaseTurnDetector, TextTurnDetectorProtocol):
    """Base class for text-based turn detectors."""
    
    def __init__(
        self,
        threshold: float = 0.5,
        context_window_turns: int = 4,
    ):
        """
        Initialize text turn detector.
        
        Args:
            threshold: Turn completion probability threshold
            context_window_turns: Number of conversation turns to consider
        """
        super().__init__(threshold=threshold)
        self._context_window_turns = context_window_turns
    
    @property
    def context_window_turns(self) -> int:
        """Get the context window size."""
        return self._context_window_turns
    
    async def configure(self, **kwargs: Any) -> None:
        """Configure the turn detector."""
        await super().configure(**kwargs)
        if "context_window_turns" in kwargs:
            self._context_window_turns = kwargs["context_window_turns"]
