"""Factory for creating VAD instances."""

from __future__ import annotations

from typing import Any

from ..config import VADConfig
from ..protocols import VADProtocol
from .silero import SileroVAD


def create_vad(
    provider: str,
    *,
    threshold: float | None = None,
    config: VADConfig | None = None,
    **kwargs: Any,
) -> VADProtocol:
    """
    Create a VAD instance.
    
    Args:
        provider: VAD provider name ("silero", "webrtc", etc.)
        threshold: Speech probability threshold (overrides config)
        config: VADConfig object (alternative to individual params)
        **kwargs: Additional provider-specific parameters
        
    Returns:
        VAD instance implementing VADProtocol
        
    Raises:
        ValueError: If provider is not supported
    """
    # Use config if provided
    if config:
        provider = config.provider
        threshold = threshold if threshold is not None else config.threshold
        kwargs.update(config.extra_params)
    
    # Create instance based on provider
    if provider == "silero":
        return SileroVAD(
            threshold=threshold or 0.5,
            **kwargs,
        )
    
    # Add more providers here
    # elif provider == "webrtc":
    #     return WebRTCVAD(...)
    
    else:
        raise ValueError(
            f"Unsupported VAD provider: {provider}. "
            f"Supported providers: silero"
        )
