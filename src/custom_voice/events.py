"""Event system for event-driven agent session architecture."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from livekit import rtc

from .protocols import TranscriptSegment, VADSignal


class EventType(Enum):
    """Event types for the event-driven system."""
    
    AUDIO_FRAME = auto()
    
    VAD_START_OF_SPEECH = auto()
    VAD_END_OF_SPEECH = auto()
    VAD_INFERENCE_DONE = auto()
    
    STT_INTERIM_TRANSCRIPT = auto()
    STT_FINAL_TRANSCRIPT = auto()
    
    AUDIO_TURN_PROBABILITY = auto()
    TEXT_TURN_PROBABILITY = auto()
    TURN_COMPLETE = auto()
    
    AGENT_START_SPEAKING = auto()
    AGENT_STOP_SPEAKING = auto()
    INTERRUPTION_DETECTED = auto()
    
    SHUTDOWN = auto()


@dataclass
class Event:
    """Base event container."""
    type: EventType
    data: Any
    timestamp: float = field(default_factory=time.time)


@dataclass
class AudioFrameData:
    """Data for AUDIO_FRAME events."""
    frame: rtc.AudioFrame


@dataclass
class VADSignalData:
    """Data for VAD-related events."""
    signal: VADSignal


@dataclass
class TranscriptData:
    """Data for STT transcript events."""
    segment: TranscriptSegment


@dataclass
class TurnProbabilityData:
    """Data for turn probability events."""
    probability: float
    source: str


@dataclass
class TurnCompleteData:
    """Data for TURN_COMPLETE events."""
    transcript: str
    audio_prob: float
    text_prob: float
