"""Factory for creating LLM instances."""

from __future__ import annotations

from typing import Any

from ..config import LLMConfig
from ..protocols import LLMProtocol
from .openai import OpenAILLM


def create_llm(
    provider: str,
    *,
    model: str | None = None,
    temperature: float | None = None,
    config: LLMConfig | None = None,
    **kwargs: Any,
) -> LLMProtocol:
    """
    Create an LLM instance.
    
    Args:
        provider: LLM provider name ("openai", "anthropic", etc.)
        model: Model identifier (overrides config)
        temperature: Sampling temperature (overrides config)
        config: LLMConfig object (alternative to individual params)
        **kwargs: Additional provider-specific parameters
        
    Returns:
        LLM instance implementing LLMProtocol
        
    Raises:
        ValueError: If provider is not supported
    """
    # Use config if provided
    if config:
        provider = config.provider
        model = model or config.model
        temperature = temperature if temperature is not None else config.temperature
        kwargs.update(config.extra_params)
    
    # Create instance based on provider
    if provider == "openai":
        if not model:
            model = "gpt-4.1-mini"
        
        return OpenAILLM(
            model=model,
            temperature=temperature or 0.7,
            **kwargs,
        )
    
    # Add more providers here
    # elif provider == "anthropic":
    #     return AnthropicLLM(...)
    # elif provider == "google":
    #     return GoogleLLM(...)
    
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported providers: openai"
        )
