"""Factory for creating turn detector instances."""

from __future__ import annotations

from typing import Any

from ..config import AudioTurnDetectorConfig, TextTurnDetectorConfig
from ..protocols import AudioTurnDetectorProtocol, TextTurnDetectorProtocol
from .eou_text import EOUTextTurnDetector
from .livekit_eou import LiveKitEOUTurnDetector
from .vad_based import VADBasedTurnDetector


def create_turn_detector(
    detector_type: str,
    *,
    config: AudioTurnDetectorConfig | TextTurnDetectorConfig | None = None,
    **kwargs: Any,
) -> AudioTurnDetectorProtocol | TextTurnDetectorProtocol:
    """
    Create a turn detector instance.
    
    Args:
        detector_type: Turn detector type ("vad", "eou", etc.)
        config: Turn detector config object
        **kwargs: Additional detector-specific parameters
        
    Returns:
        Turn detector instance
        
    Raises:
        ValueError: If detector type is not supported
    """
    # Use config if provided
    if config:
        detector_type = config.type
        kwargs.update(config.extra_params)
        
        if isinstance(config, AudioTurnDetectorConfig):
            kwargs.setdefault("threshold", config.threshold)
            kwargs.setdefault("silence_duration", config.silence_duration)
        elif isinstance(config, TextTurnDetectorConfig):
            kwargs.setdefault("threshold", config.threshold)
            kwargs.setdefault("context_window_turns", config.context_window_turns)
    
    # Create instance based on type
    if detector_type == "vad":
        return VADBasedTurnDetector(**kwargs)
    
    elif detector_type == "eou":
        return EOUTextTurnDetector(**kwargs)
    
    elif detector_type == "livekit_eou":
        return LiveKitEOUTurnDetector(**kwargs)
    
    # Add more detector types here
    # elif detector_type == "semantic":
    #     return SemanticTurnDetector(**kwargs)
    
    else:
        raise ValueError(
            f"Unsupported turn detector type: {detector_type}. "
            f"Supported types: vad, eou, livekit_eou"
        )
