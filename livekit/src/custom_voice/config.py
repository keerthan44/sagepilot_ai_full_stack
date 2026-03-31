"""Configuration system for custom voice stack components."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ============================================================================
# STT Configuration
# ============================================================================

@dataclass
class STTConfig:
    """Configuration for Speech-to-Text component."""
    provider: str  # "deepgram", "whisper", "google", etc.
    model: str
    language: str | None = None
    transport: Literal["websocket", "http"] = "websocket"
    interim_results: bool = True
    sample_rate: int = 16000
    extra_params: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# LLM Configuration
# ============================================================================

@dataclass
class LLMConfig:
    """Configuration for Large Language Model component."""
    provider: str  # "openai", "anthropic", "google", etc.
    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    streaming: bool = True
    extra_params: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# TTS Configuration
# ============================================================================

@dataclass
class TTSConfig:
    """Configuration for Text-to-Speech component."""
    provider: str  # "cartesia", "elevenlabs", "openai", etc.
    model: str
    voice: str
    transport: Literal["websocket", "http"] = "websocket"
    sample_rate: int = 24000
    streaming: bool = True
    extra_params: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# VAD Configuration
# ============================================================================

@dataclass
class VADConfig:
    """Configuration for Voice Activity Detection component."""
    provider: str  # "silero", "webrtc", etc.
    threshold: float = 0.5
    min_speech_duration: float = 0.1  # seconds
    min_silence_duration: float = 0.5  # seconds
    extra_params: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Turn Detection Configuration
# ============================================================================

@dataclass
class AudioTurnDetectorConfig:
    """Configuration for audio-based turn detection."""
    type: str  # "vad", "silence", "custom"
    threshold: float = 0.5
    silence_duration: float = 0.8  # seconds
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextTurnDetectorConfig:
    """Configuration for text-based turn detection."""
    type: str  # "eou", "semantic", "custom"
    threshold: float = 0.5
    context_window_turns: int = 4  # Like LiveKit EOU
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnDetectionConfig:
    """
    Configuration for turn detection.
    
    Supports 4 scenarios:
    1. No detectors (both None): Use default endpointing
    2. Audio only: Use audio turn detector
    3. Text only: Use text turn detector
    4. Both: Use aggregation
    """
    # Optional detectors (can be None)
    audio_detector: AudioTurnDetectorConfig | None = None
    text_detector: TextTurnDetectorConfig | None = None
    
    # Aggregation config (only used when both detectors exist)
    aggregation_strategy: Literal["any", "all", "weighted", "majority"] = "weighted"
    weights: dict[str, float] | None = None  # {"audio": 0.4, "text": 0.6}
    
    # Default endpointing (used when no detectors configured)
    min_endpointing_delay: float = 0.5
    max_endpointing_delay: float = 3.0
    
    def has_audio_detector(self) -> bool:
        """Check if audio turn detector is configured."""
        return self.audio_detector is not None
    
    def has_text_detector(self) -> bool:
        """Check if text turn detector is configured."""
        return self.text_detector is not None
    
    def needs_aggregation(self) -> bool:
        """Check if aggregation is needed (both detectors configured)."""
        return self.has_audio_detector() and self.has_text_detector()


# ============================================================================
# Interruption Configuration
# ============================================================================

@dataclass
class InterruptionConfig:
    """Configuration for interruption handling."""
    enabled: bool = True
    min_interruption_duration: float = 0.3  # seconds (reduced for faster response)
    min_interruption_words: int = 2
    false_interruption_timeout: float = 2.0  # seconds
    resume_on_false_interruption: bool = True
    aec_warmup_duration: float = 0.5  # seconds (AEC = Acoustic Echo Cancellation, reduced from 3.0s)


# ============================================================================
# Audio Pipeline Configuration
# ============================================================================

@dataclass
class AudioPipelineConfig:
    """Configuration for audio pipeline."""
    input_sample_rate: int = 48000  # LiveKit room sample rate
    processing_sample_rate: int = 16000  # STT/VAD processing rate
    output_sample_rate: int = 24000  # TTS output rate
    buffer_size_ms: int = 20  # milliseconds
    channels: int = 1  # mono


# ============================================================================
# Main Voice Stack Configuration
# ============================================================================

@dataclass
class VoiceStackConfig:
    """Complete configuration for the custom voice stack."""
    stt: STTConfig
    llm: LLMConfig
    tts: TTSConfig
    vad: VADConfig
    turn_detection: TurnDetectionConfig
    interruption: InterruptionConfig
    audio_pipeline: AudioPipelineConfig = field(default_factory=AudioPipelineConfig)
    
    # Session options
    preemptive_generation: bool = True
    user_away_timeout: float | None = 15.0  # seconds
    max_tool_steps: int = 3


# ============================================================================
# Factory Helper Functions
# ============================================================================

def create_default_config(
    stt_provider: str = "deepgram",
    llm_provider: str = "openai",
    tts_provider: str = "cartesia",
) -> VoiceStackConfig:
    """
    Create a default voice stack configuration.
    
    Args:
        stt_provider: STT provider name
        llm_provider: LLM provider name
        tts_provider: TTS provider name
        
    Returns:
        Default VoiceStackConfig
    """
    return VoiceStackConfig(
        stt=STTConfig(
            provider=stt_provider,
            model="nova-3" if stt_provider == "deepgram" else "base",
            language="multi",
        ),
        llm=LLMConfig(
            provider=llm_provider,
            model="gpt-4.1-mini" if llm_provider == "openai" else "claude-3-5-sonnet",
        ),
        tts=TTSConfig(
            provider=tts_provider,
            model="sonic-3" if tts_provider == "cartesia" else "default",
            voice="default",
        ),
        vad=VADConfig(
            provider="silero",
        ),
        turn_detection=TurnDetectionConfig(
            audio_detector=AudioTurnDetectorConfig(
                type="vad",
                silence_duration=0.8,
            ),
        ),
        interruption=InterruptionConfig(),
    )
