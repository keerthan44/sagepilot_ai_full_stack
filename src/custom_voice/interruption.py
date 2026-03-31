"""Interruption detection and handling."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from .config import InterruptionConfig
from .protocols import VADSignal

logger = logging.getLogger("custom-agent")

if TYPE_CHECKING:
    from .protocols import LLMProtocol, TTSProtocol


class InterruptionHandler:
    """
    Manages interruption detection and handling.
    
    Monitors VAD during agent speaking to detect user interruptions,
    handles false interruptions (echo, AEC warmup), and cancels
    ongoing TTS/LLM generation.
    """
    
    def __init__(
        self,
        config: InterruptionConfig,
        llm: LLMProtocol | None = None,
        tts: TTSProtocol | None = None,
    ):
        """
        Initialize interruption handler.
        
        Args:
            config: Interruption configuration
            llm: LLM instance (for cancellation)
            tts: TTS instance (for cancellation)
        """
        self._config = config
        self._llm = llm
        self._tts = tts
        
        # State tracking
        self._agent_speaking = False
        self._interruption_start_time: float | None = None
        self._speech_duration = 0.0
        self._word_count = 0
        self._aec_warmup_active = False
        self._aec_warmup_end_time: float | None = None
        
        # False interruption tracking
        self._false_interruption_timer: asyncio.TimerHandle | None = None
        self._interrupted = False
    
    def set_agent_speaking(self, speaking: bool) -> None:
        """
        Update agent speaking state.
        
        Args:
            speaking: Whether agent is currently speaking
        """
        self._agent_speaking = speaking
        logger.debug("InterruptionHandler: agent_speaking=%s", speaking)
        
        if speaking:
            # Start AEC warmup when agent starts speaking
            if self._config.aec_warmup_duration > 0:
                self._aec_warmup_active = True
                self._aec_warmup_end_time = time.time() + self._config.aec_warmup_duration
                logger.debug("InterruptionHandler: AEC warmup active (duration=%.2fs)", self._config.aec_warmup_duration)
        else:
            # Reset state when agent stops speaking
            self._aec_warmup_active = False
            self._aec_warmup_end_time = None
            self._interruption_start_time = None
            self._speech_duration = 0.0
            self._word_count = 0
            self._interrupted = False
    
    def process_vad_signal(self, vad_signal: VADSignal) -> bool:
        """
        Process VAD signal and detect interruptions.
        
        Args:
            vad_signal: VAD signal from user audio
            
        Returns:
            True if valid interruption detected, False otherwise
        """
        if not self._config.enabled:
            return False
        
        if not self._agent_speaking:
            return False
        
        # Check AEC warmup
        if self._aec_warmup_active:
            if self._aec_warmup_end_time and time.time() < self._aec_warmup_end_time:
                # Still in AEC warmup period, ignore interruptions
                logger.debug("InterruptionHandler: ignoring speech during AEC warmup")
                return False
            else:
                # AEC warmup expired
                self._aec_warmup_active = False
                logger.debug("InterruptionHandler: AEC warmup expired")
        
        # Detect speech
        if vad_signal.is_speech:
            # User is speaking during agent speech
            if self._interruption_start_time is None:
                # Start tracking interruption
                self._interruption_start_time = time.time()
                logger.debug("InterruptionHandler: user speech detected, tracking interruption")
            else:
                # Update interruption duration
                self._speech_duration = time.time() - self._interruption_start_time
            
            # Check if interruption meets criteria
            if self._speech_duration >= self._config.min_interruption_duration:
                # Valid interruption detected
                if not self._interrupted:
                    self._interrupted = True
                    self._cancel_false_interruption_timer()
                    logger.info(
                        "InterruptionHandler: valid interruption detected (duration=%.3fs, min=%.3fs)",
                        self._speech_duration,
                        self._config.min_interruption_duration,
                    )
                    return True
        
        else:
            # No speech detected
            if self._interruption_start_time is not None:
                # Speech ended, might be false interruption
                if self._speech_duration < self._config.min_interruption_duration:
                    # Too short, likely false interruption
                    logger.debug(
                        "InterruptionHandler: false interruption (duration=%.3fs < min=%.3fs)",
                        self._speech_duration,
                        self._config.min_interruption_duration,
                    )
                    self._handle_false_interruption()
                
                # Reset tracking
                self._interruption_start_time = None
                self._speech_duration = 0.0
        
        return False
    
    def _handle_false_interruption(self) -> None:
        """Handle potential false interruption."""
        if not self._config.resume_on_false_interruption:
            return
        
        # Start timer for false interruption timeout
        if self._config.false_interruption_timeout > 0:
            self._cancel_false_interruption_timer()
            
            loop = asyncio.get_event_loop()
            self._false_interruption_timer = loop.call_later(
                self._config.false_interruption_timeout,
                self._on_false_interruption_timeout,
            )
    
    def _on_false_interruption_timeout(self) -> None:
        """Called when false interruption timeout expires."""
        # Resume agent speaking if it was a false interruption
        # This would be handled by the session layer
        pass
    
    def _cancel_false_interruption_timer(self) -> None:
        """Cancel false interruption timer."""
        if self._false_interruption_timer:
            self._false_interruption_timer.cancel()
            self._false_interruption_timer = None
    
    async def interrupt(self, force: bool = False) -> None:
        """
        Interrupt ongoing TTS/LLM generation.
        
        Args:
            force: Force interruption even if not interruptible
        """
        if not self._config.enabled and not force:
            logger.debug("InterruptionHandler: interrupt called but disabled")
            return
        
        logger.info("InterruptionHandler: interrupting TTS/LLM")
        
        # Cancel TTS
        if self._tts:
            logger.debug("InterruptionHandler: cancelling TTS")
            await self._tts.cancel()
        
        # Cancel LLM
        if self._llm:
            logger.debug("InterruptionHandler: cancelling LLM")
            await self._llm.cancel()
        
        self._interrupted = True
    
    def reset(self) -> None:
        """Reset interruption state."""
        logger.debug("InterruptionHandler: resetting state")
        self._agent_speaking = False
        self._interruption_start_time = None
        self._speech_duration = 0.0
        self._word_count = 0
        self._aec_warmup_active = False
        self._aec_warmup_end_time = None
        self._interrupted = False
        self._cancel_false_interruption_timer()
    
    @property
    def is_interrupted(self) -> bool:
        """Check if currently interrupted."""
        return self._interrupted
