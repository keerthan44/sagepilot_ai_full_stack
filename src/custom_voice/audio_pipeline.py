"""Audio pipeline for managing audio streaming and format conversions."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterable
from typing import Any

import numpy as np
from livekit import rtc

from .config import AudioPipelineConfig


class AudioPipeline:
    """
    Manages audio streaming and format conversions.
    
    Handles:
    - Audio input from LiveKit room
    - Resampling for different components (STT, VAD, TTS)
    - Audio output to LiveKit room
    - Buffer management
    """
    
    def __init__(self, config: AudioPipelineConfig | None = None):
        """
        Initialize audio pipeline.
        
        Args:
            config: Audio pipeline configuration
        """
        self._config = config or AudioPipelineConfig()
        
        # Input/output queues
        self._input_queue: asyncio.Queue[rtc.AudioFrame] = asyncio.Queue()
        self._output_queue: asyncio.Queue[rtc.AudioFrame] = asyncio.Queue()
        
        # Audio buffers
        self._input_buffer: deque[rtc.AudioFrame] = deque(maxlen=100)
        self._output_buffer: deque[rtc.AudioFrame] = deque(maxlen=100)
        
        # State
        self._started = False
        self._closed = False
    
    async def start(self) -> None:
        """Start the audio pipeline."""
        if self._started:
            return
        
        self._started = True
        self._closed = False
    
    async def push_input_audio(self, frame: rtc.AudioFrame) -> None:
        """
        Push audio frame to input pipeline.
        
        Args:
            frame: Audio frame from LiveKit room
        """
        if self._closed:
            return
        
        self._input_buffer.append(frame)
        await self._input_queue.put(frame)
    
    async def push_output_audio(self, frame: rtc.AudioFrame) -> None:
        """
        Push audio frame to output pipeline.
        
        Args:
            frame: Audio frame to send to LiveKit room
        """
        if self._closed:
            return
        
        self._output_buffer.append(frame)
        await self._output_queue.put(frame)
    
    async def get_input_audio(self) -> rtc.AudioFrame:
        """
        Get audio frame from input pipeline.
        
        Returns:
            Audio frame for processing
        """
        return await self._input_queue.get()
    
    async def get_output_audio(self) -> rtc.AudioFrame:
        """
        Get audio frame from output pipeline.
        
        Returns:
            Audio frame to send to room
        """
        return await self._output_queue.get()
    
    def input_stream(self) -> AsyncIterable[rtc.AudioFrame]:
        """
        Get async iterable of input audio frames.
        
        Yields:
            Audio frames from input pipeline
        """
        return self._audio_stream_generator(self._input_queue)
    
    def output_stream(self) -> AsyncIterable[rtc.AudioFrame]:
        """
        Get async iterable of output audio frames.
        
        Yields:
            Audio frames from output pipeline
        """
        return self._audio_stream_generator(self._output_queue)
    
    async def _audio_stream_generator(
        self,
        queue: asyncio.Queue[rtc.AudioFrame],
    ) -> AsyncIterable[rtc.AudioFrame]:
        """
        Generate audio stream from queue.
        
        Args:
            queue: Audio frame queue
            
        Yields:
            Audio frames
        """
        while not self._closed:
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield frame
            except asyncio.TimeoutError:
                continue
    
    def resample_frame(
        self,
        frame: rtc.AudioFrame,
        target_sample_rate: int,
    ) -> rtc.AudioFrame:
        """
        Resample audio frame to target sample rate.
        
        Args:
            frame: Input audio frame
            target_sample_rate: Target sample rate in Hz
            
        Returns:
            Resampled audio frame
        """
        if frame.sample_rate == target_sample_rate:
            return frame
        
        # Simple linear interpolation resampling
        # For production, use a proper resampling library like librosa or scipy
        ratio = target_sample_rate / frame.sample_rate
        
        # Get audio data as numpy array
        audio_data = np.frombuffer(frame.data.tobytes(), dtype=np.int16)
        
        # Calculate new length
        new_length = int(len(audio_data) * ratio)
        
        # Resample using linear interpolation
        indices = np.linspace(0, len(audio_data) - 1, new_length)
        resampled = np.interp(indices, np.arange(len(audio_data)), audio_data)
        resampled = resampled.astype(np.int16)
        
        # Create new frame
        return rtc.AudioFrame(
            data=resampled,
            sample_rate=target_sample_rate,
            num_channels=frame.num_channels,
            samples_per_channel=len(resampled),
        )
    
    def clear_buffers(self) -> None:
        """Clear all audio buffers."""
        self._input_buffer.clear()
        self._output_buffer.clear()
        
        # Clear queues
        while not self._input_queue.empty():
            try:
                self._input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        while not self._output_queue.empty():
            try:
                self._output_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
    
    async def aclose(self) -> None:
        """Close the audio pipeline."""
        self._closed = True
        self.clear_buffers()
