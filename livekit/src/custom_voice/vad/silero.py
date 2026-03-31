"""Silero VAD implementation."""

from __future__ import annotations

import asyncio
import logging
import time

from livekit import agents, rtc
from livekit.plugins import silero

from ..protocols import VADSignal
from .base import BaseVAD

logger = logging.getLogger("custom-agent")


class SileroVAD(BaseVAD):
    """
    Silero Voice Activity Detection implementation.
    
    Wraps the LiveKit Silero VAD plugin with our protocol interface.
    
    Note: This implementation uses a long-running background task to consume 
    VAD events from the Silero stream and maintains the latest probability state.
    The stream and task are created once during initialization and persist for
    the lifetime of the VAD instance.
    """
    
    def __init__(
        self,
        *,
        threshold: float = 0.5,
        min_speech_duration: float = 0.1,
        min_silence_duration: float = 0.5,
        vad_instance: silero.VAD | None = None,
    ):
        """
        Initialize Silero VAD.
        
        Args:
            threshold: Speech probability threshold (0.0 to 1.0)
            min_speech_duration: Minimum speech duration in seconds
            min_silence_duration: Minimum silence duration in seconds
            vad_instance: Pre-loaded Silero VAD instance (optional)
        """
        super().__init__(
            threshold=threshold,
            min_speech_duration=min_speech_duration,
            min_silence_duration=min_silence_duration,
        )
        
        # Use provided instance or load new one
        self._vad = vad_instance or silero.VAD.load(
            min_speech_duration=min_speech_duration,
            min_silence_duration=min_silence_duration,
            activation_threshold=threshold,
        )
        
        # Create stream and start event consumer task immediately
        self._stream: silero.VADStream = self._vad.stream()
        self._event_task: asyncio.Task = asyncio.create_task(self._consume_vad_events())
        
        # Track latest VAD state from events
        self._latest_probability: float = 0.0
        self._latest_is_speech: bool = False
        self._latest_timestamp: float = time.time()
    
    async def _consume_vad_events(self) -> None:
        """
        Long-running background task to consume VAD events from the stream.
        Updates the latest probability and speech state.
        This task runs for the lifetime of the VAD instance.
        """
        logger.debug("SileroVAD: event consumer started")
        try:
            async for event in self._stream:
                if event.type == agents.vad.VADEventType.START_OF_SPEECH:
                    self._latest_is_speech = True
                    self._latest_probability = event.probability
                    self._latest_timestamp = event.timestamp
                    logger.debug("SileroVAD: START_OF_SPEECH (prob=%.3f)", event.probability)
                elif event.type == agents.vad.VADEventType.END_OF_SPEECH:
                    self._latest_is_speech = False
                    self._latest_probability = event.probability
                    self._latest_timestamp = event.timestamp
                    logger.debug("SileroVAD: END_OF_SPEECH (prob=%.3f)", event.probability)
                elif event.type == agents.vad.VADEventType.INFERENCE_DONE:
                    self._latest_probability = event.probability
                    self._latest_is_speech = event.speaking
                    self._latest_timestamp = event.timestamp
        except asyncio.CancelledError:
            pass
        logger.debug("SileroVAD: event consumer stopped")
    
    async def process_audio(
        self,
        audio_frame: rtc.AudioFrame,
    ) -> VADSignal:
        """
        Process an audio frame and detect voice activity.
        
        Args:
            audio_frame: Audio frame to process
            
        Returns:
            VAD signal indicating speech presence and probability
        """
        # Push audio to VAD (returns None, events come asynchronously)
        self._stream.push_frame(audio_frame)
        
        # Return the latest VAD state
        return VADSignal(
            is_speech=self._latest_is_speech,
            probability=self._latest_probability,
            timestamp=self._latest_timestamp,
        )
    
    def reset(self) -> None:
        """
        Reset VAD state.
        
        Note: This only resets the internal state tracking variables.
        The stream and event consumer task continue running.
        """
        super().reset()
        self._latest_probability = 0.0
        self._latest_is_speech = False
        self._latest_timestamp = time.time()
    
    async def aclose(self) -> None:
        """Clean up resources."""
        self._event_task.cancel()
        try:
            await self._event_task
        except asyncio.CancelledError:
            pass
        await self._stream.aclose()
