"""Factory for creating TTS instances."""

from __future__ import annotations

from typing import Any, Literal

from ..config import TTSConfig
from ..protocols import TTSProtocol
from .cartesia import CartesiaTTS
from .elevenlabs import ElevenLabsTTS


def create_tts(
    provider: str,
    *,
    model: str | None = None,
    voice: str | None = None,
    transport: Literal["websocket", "http"] = "websocket",
    config: TTSConfig | None = None,
    **kwargs: Any,
) -> TTSProtocol:
    """
    Create a TTS instance.
    
    Args:
        provider: TTS provider name ("cartesia", "elevenlabs", etc.)
        model: Model identifier (overrides config)
        voice: Voice identifier (overrides config)
        transport: Transport protocol ("websocket" or "http")
        config: TTSConfig object (alternative to individual params)
        **kwargs: Additional provider-specific parameters
        
    Returns:
        TTS instance implementing TTSProtocol
        
    Raises:
        ValueError: If provider is not supported or voice is missing
    """
    # Use config if provided
    if config:
        provider = config.provider
        model = model or config.model
        voice = voice or config.voice
        transport = config.transport
        kwargs.update(config.extra_params)
    
    # Voice is required
    if not voice:
        raise ValueError("Voice identifier is required for TTS")
    
    # Create instance based on provider
    if provider == "cartesia":
        if not model:
            model = "sonic-3"
        
        return CartesiaTTS(
            model=model,
            voice=voice,
            transport=transport,
            **kwargs,
        )
    
    elif provider == "elevenlabs":
        if not model:
            model = "eleven_turbo_v2_5"
        
        return ElevenLabsTTS(
            voice_id=voice,
            model=model,
            **kwargs,
        )
    
    else:
        raise ValueError(
            f"Unsupported TTS provider: {provider}. "
            f"Supported providers: cartesia, elevenlabs"
        )
