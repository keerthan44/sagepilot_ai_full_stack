"""Voice Activity Detection implementations."""

from .base import BaseVAD
from .factory import create_vad

__all__ = ["BaseVAD", "create_vad"]
