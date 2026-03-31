"""Custom voice stack implementation.

A modular voice agent system with swappable components for STT, LLM, TTS, VAD,
and turn detection. Uses LiveKit only for room management and worker spawning.
"""

from .config import (
    AudioPipelineConfig,
    AudioTurnDetectorConfig,
    InterruptionConfig,
    LLMConfig,
    STTConfig,
    TextTurnDetectorConfig,
    TTSConfig,
    TurnDetectionConfig,
    VADConfig,
    VoiceStackConfig,
    create_default_config,
)
from .context import ConversationContext
from .llm import create_llm
from .protocols import (
    AudioTurnDetectorProtocol,
    ConversationTurn,
    HybridTurnDetectorProtocol,
    LLMMessage,
    LLMProtocol,
    LLMResponse,
    STTProtocol,
    TextTurnDetectorProtocol,
    TranscriptSegment,
    TTSProtocol,
    TurnDetectorProtocol,
    VADProtocol,
    VADSignal,
)
from .session import CustomAgentSession
from .stt import create_stt
from .tts import create_tts
from .turn_detection import create_turn_detector
from .vad import create_vad

__all__ = [
    # Protocols
    "AudioTurnDetectorProtocol",
    "ConversationTurn",
    "HybridTurnDetectorProtocol",
    "LLMMessage",
    "LLMProtocol",
    "LLMResponse",
    "STTProtocol",
    "TextTurnDetectorProtocol",
    "TranscriptSegment",
    "TTSProtocol",
    "TurnDetectorProtocol",
    "VADProtocol",
    "VADSignal",
    # Configuration
    "AudioPipelineConfig",
    "AudioTurnDetectorConfig",
    "InterruptionConfig",
    "LLMConfig",
    "STTConfig",
    "TextTurnDetectorConfig",
    "TTSConfig",
    "TurnDetectionConfig",
    "VADConfig",
    "VoiceStackConfig",
    "create_default_config",
    # Components
    "ConversationContext",
    "CustomAgentSession",
    # Factories
    "create_llm",
    "create_stt",
    "create_tts",
    "create_turn_detector",
    "create_vad",
]
