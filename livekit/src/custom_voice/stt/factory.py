"""Factory for creating STT instances."""

from __future__ import annotations

from typing import Any, Literal

from ..config import STTConfig
from ..protocols import STTProtocol
from .assemblyai import AssemblyAISTT
from .deepgram import DeepgramSTT


def create_stt(
    provider: str,
    *,
    model: str | None = None,
    language: str | None = None,
    transport: Literal["websocket", "http"] = "websocket",
    config: STTConfig | None = None,
    **kwargs: Any,
) -> STTProtocol:
    """
    Create an STT instance.
    
    Args:
        provider: STT provider name ("deepgram", "whisper", etc.)
        model: Model identifier (overrides config)
        language: Language code (overrides config)
        transport: Transport protocol ("websocket" or "http")
        config: STTConfig object (alternative to individual params)
        **kwargs: Additional provider-specific parameters
        
    Returns:
        STT instance implementing STTProtocol
        
    Raises:
        ValueError: If provider is not supported
    """
    # Use config if provided
    if config:
        provider = config.provider
        model = model or config.model
        language = language or config.language
        transport = config.transport
        kwargs.update(config.extra_params)
    
    # Create instance based on provider
    if provider == "deepgram":
        if not model:
            model = "nova-3"
        
        return DeepgramSTT(
            model=model,
            language=language,
            transport=transport,
            **kwargs,
        )
    
    elif provider == "assemblyai":
        if not model:
            model = "universal-streaming-english"
        
        return AssemblyAISTT(
            model=model,
            language=language,
            **kwargs,
        )
    
    # Add more providers here
    # elif provider == "whisper":
    #     return WhisperSTT(...)
    # elif provider == "google":
    #     return GoogleSTT(...)
    
    else:
        raise ValueError(
            f"Unsupported STT provider: {provider}. "
            f"Supported providers: deepgram, assemblyai"
        )
