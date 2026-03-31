"""VAD-based turn detection."""

from __future__ import annotations

import time

from livekit import rtc

from .base import AudioTurnDetector


class VADBasedTurnDetector(AudioTurnDetector):
    """
    Audio-based turn detector using VAD silence duration.
    
    Detects turn completion when silence duration exceeds threshold.
    """
    
    def __init__(
        self,
        *,
        threshold: float = 0.5,
        silence_duration: float = 0.8,
    ):
        """
        Initialize VAD-based turn detector.
        
        Args:
            threshold: Turn completion probability threshold
            silence_duration: Required silence duration in seconds to signal turn end
        """
        super().__init__(threshold=threshold)
        self._silence_duration = silence_duration
        self._last_speech_time: float | None = None
        self._silence_start_time: float | None = None
    
    async def process_audio(
        self,
        audio_frame: rtc.AudioFrame,
        vad_probability: float,
    ) -> float:
        """
        Process audio and return turn completion probability.
        
        Args:
            audio_frame: Audio frame to process
            vad_probability: VAD probability for this frame
            
        Returns:
            Turn completion probability (0.0 to 1.0)
        """
        current_time = time.time()
        
        # Check if speech is detected
        is_speech = vad_probability >= self._threshold
        
        if is_speech:
            # Speech detected, reset silence tracking
            self._last_speech_time = current_time
            self._silence_start_time = None
            return 0.0  # Not end of turn
        
        else:
            # Silence detected
            if self._last_speech_time is None:
                # No speech detected yet
                return 0.0
            
            # Start tracking silence if not already
            if self._silence_start_time is None:
                self._silence_start_time = current_time
            
            # Calculate silence duration
            silence_elapsed = current_time - self._silence_start_time
            
            # Calculate turn probability based on silence duration
            if silence_elapsed >= self._silence_duration:
                # Silence threshold exceeded, high probability of turn end
                return 1.0
            else:
                # Partial silence, return proportional probability
                return min(silence_elapsed / self._silence_duration, 0.99)
    
    def reset(self) -> None:
        """Reset turn detector state."""
        super().reset()
        self._last_speech_time = None
        self._silence_start_time = None
