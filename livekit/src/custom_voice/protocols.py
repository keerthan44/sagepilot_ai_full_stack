"""Protocol definitions for custom voice stack components.

This module defines abstract protocols (interfaces) for all swappable components
in the voice stack: STT, LLM, TTS, VAD, and turn detectors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from livekit import rtc

# ============================================================================
# Common Data Types
# ============================================================================


@dataclass
class TranscriptSegment:
    """A segment of transcribed text."""

    text: str
    is_final: bool
    confidence: float = 1.0
    start_time: float | None = None
    end_time: float | None = None
    language: str | None = None


@dataclass
class VADSignal:
    """Voice activity detection signal."""

    is_speech: bool
    probability: float
    timestamp: float


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    role: Literal["user", "assistant", "system", "tool_call", "tool_result"]
    content: str
    timestamp: float
    metadata: dict[str, Any] | None = None
    # Populated for role="tool_call": list of {"name": str, "args": dict, "id": str}
    tool_calls: list[dict[str, Any]] | None = None
    # Populated for role="tool_result": the tool call id this result belongs to
    tool_call_id: str | None = None


# ============================================================================
# STT Protocol
# ============================================================================


class STTProtocol(Protocol):
    """Protocol for Speech-to-Text implementations."""

    @abstractmethod
    async def recognize_stream(
        self,
        audio_stream: AsyncIterable[rtc.AudioFrame],
    ) -> AsyncIterable[TranscriptSegment]:
        """
        Recognize speech from an audio stream.

        Args:
            audio_stream: Async iterable of audio frames

        Yields:
            TranscriptSegment objects with interim and final results
        """
        ...

    @abstractmethod
    async def configure(self, **kwargs: Any) -> None:
        """Configure the STT component."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close and cleanup the STT component."""
        ...


# ============================================================================
# LLM Protocol
# ============================================================================


@dataclass
class LLMMessage:
    """A message in the LLM conversation."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


@dataclass
class LLMResponse:
    """Response from LLM generation."""

    content: str
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    usage: dict[str, int] | None = None


class LLMProtocol(Protocol):
    """Protocol for Large Language Model implementations."""

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[str]:
        """
        Generate a streaming response from the LLM.

        Args:
            messages: Conversation history
            tools: Optional function tools for the LLM to use
            **kwargs: Additional generation parameters

        Yields:
            Text chunks as they are generated
        """
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a complete response from the LLM.

        Args:
            messages: Conversation history
            tools: Optional function tools for the LLM to use
            **kwargs: Additional generation parameters

        Returns:
            Complete LLM response
        """
        ...

    @abstractmethod
    async def configure(self, **kwargs: Any) -> None:
        """Configure the LLM component."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close and cleanup the LLM component."""
        ...


# ============================================================================
# TTS Protocol
# ============================================================================


class TTSProtocol(Protocol):
    """Protocol for Text-to-Speech implementations."""

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str | AsyncIterable[str],
    ) -> AsyncIterable[rtc.AudioFrame]:
        """
        Synthesize speech from text with streaming output.

        Args:
            text: Text to synthesize (string or async iterable of chunks)

        Yields:
            Audio frames as they are synthesized
        """
        ...

    @abstractmethod
    async def synthesize_stream_from_iterator(
        self,
        text_iterator: AsyncIterable[str],
    ) -> AsyncIterable[rtc.AudioFrame]:
        """
        Synthesize audio from a streaming text source.

        The TTS implementation handles internal buffering and chunking
        based on its configured strategy (sentence, word, time-based).
        This enables clean LLM→TTS streaming pipelines.

        Args:
            text_iterator: Async iterator yielding text tokens/chunks

        Yields:
            Audio frames as they are synthesized
        """
        ...

    @abstractmethod
    async def synthesize(self, text: str) -> list[rtc.AudioFrame]:
        """
        Synthesize complete speech from text.

        Args:
            text: Text to synthesize

        Returns:
            List of audio frames
        """
        ...

    @abstractmethod
    async def configure(self, **kwargs: Any) -> None:
        """Configure the TTS component."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close and cleanup the TTS component."""
        ...

    @abstractmethod
    async def cancel(self) -> None:
        """Cancel ongoing synthesis (for interruption support)."""
        ...


# ============================================================================
# VAD Protocol
# ============================================================================


class VADProtocol(Protocol):
    """Protocol for Voice Activity Detection implementations."""

    @abstractmethod
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
        ...

    @abstractmethod
    async def configure(self, **kwargs: Any) -> None:
        """Configure the VAD component."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset VAD state."""
        ...


# ============================================================================
# Turn Detector Protocols
# ============================================================================


class TurnDetectorProtocol(ABC):
    """Base protocol for turn detection implementations."""

    @property
    @abstractmethod
    def input_modality(self) -> Literal["audio", "text", "hybrid"]:
        """The input modality this turn detector processes."""
        ...

    @abstractmethod
    async def configure(self, **kwargs: Any) -> None:
        """Configure the turn detector."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset turn detector state."""
        ...


class AudioTurnDetectorProtocol(TurnDetectorProtocol):
    """Protocol for audio-based turn detection."""

    @property
    def input_modality(self) -> Literal["audio"]:
        return "audio"

    @abstractmethod
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
        ...


class TextTurnDetectorProtocol(TurnDetectorProtocol):
    """Protocol for text-based turn detection."""

    @property
    def input_modality(self) -> Literal["text"]:
        return "text"

    @abstractmethod
    async def process_transcript(
        self,
        transcript: str,
        is_final: bool,
        conversation_context: list[ConversationTurn],
    ) -> float:
        """
        Process transcript and return turn completion probability.

        Args:
            transcript: Current transcript text
            is_final: Whether this is a final transcript
            conversation_context: Recent conversation turns for context

        Returns:
            Turn completion probability (0.0 to 1.0)
        """
        ...


class HybridTurnDetectorProtocol(TurnDetectorProtocol):
    """Protocol for hybrid audio+text turn detection."""

    @property
    def input_modality(self) -> Literal["hybrid"]:
        return "hybrid"

    @abstractmethod
    async def process_audio(
        self,
        audio_frame: rtc.AudioFrame,
        vad_probability: float,
    ) -> None:
        """
        Process audio features for turn detection.

        Args:
            audio_frame: Audio frame to process
            vad_probability: VAD probability for this frame
        """
        ...

    @abstractmethod
    async def process_transcript(
        self,
        transcript: str,
        is_final: bool,
        conversation_context: list[ConversationTurn],
    ) -> None:
        """
        Process transcript for turn detection.

        Args:
            transcript: Current transcript text
            is_final: Whether this is a final transcript
            conversation_context: Recent conversation turns for context
        """
        ...

    @abstractmethod
    async def get_turn_probability(self) -> float:
        """
        Get aggregated turn completion probability from both modalities.

        Returns:
            Turn completion probability (0.0 to 1.0)
        """
        ...
