"""Speech-to-Text implementations."""

from .base import BaseSTT
from .factory import create_stt

__all__ = ["BaseSTT", "create_stt"]
