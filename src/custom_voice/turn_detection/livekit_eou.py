"""LiveKit EOU (End-of-Utterance) turn detection.

Wraps the official LiveKit turn detector plugin for use in the custom voice stack.
Uses the EnglishModel for English-only turn detection with ML-based context awareness.
"""

from __future__ import annotations

import logging

from livekit.agents import llm as lk_llm
from livekit.plugins.turn_detector.english import EnglishModel

from ..protocols import ConversationTurn
from .base import TextTurnDetector

logger = logging.getLogger("custom-agent")


class LiveKitEOUTurnDetector(TextTurnDetector):
    """
    LiveKit EOU turn detector - uses the official LiveKit turn detection model.
    
    This is a context-aware ML model (Qwen2.5-0.5B-Instruct based) that analyzes
    conversation history to predict end-of-turn with high accuracy:
    - True positive rate: 99.3% (correctly identifies turn complete)
    - True negative rate: 87.0% (correctly identifies user will continue)
    
    The model runs locally on CPU and requires ~400MB of model weights.
    Inference latency is typically 50-160ms per turn.
    """
    
    def __init__(
        self,
        *,
        threshold: float = 0.5,
        context_window_turns: int = 6,  # LiveKit uses up to 6 turns
        unlikely_threshold: float | None = None,
    ):
        """
        Initialize LiveKit EOU turn detector.
        
        Args:
            threshold: Turn completion probability threshold (0.0 to 1.0)
            context_window_turns: Number of conversation turns to consider (max 6)
            unlikely_threshold: Optional custom threshold for the model
                              (overrides the default per-language tuned threshold)
        """
        super().__init__(
            threshold=threshold,
            context_window_turns=min(context_window_turns, 6),  # LiveKit max is 6
        )
        
        # Lazy initialization - model is created on first use (requires job context)
        self._model: EnglishModel | None = None
        self._unlikely_threshold = unlikely_threshold
        logger.info(
            "LiveKitEOUTurnDetector: initialized (threshold=%.2f, context_turns=%d)",
            threshold,
            self._context_window_turns,
        )
    
    def _ensure_model(self) -> EnglishModel:
        """Ensure the model is initialized (lazy initialization)."""
        if self._model is None:
            try:
                self._model = EnglishModel(unlikely_threshold=self._unlikely_threshold)
                logger.info("LiveKitEOUTurnDetector: model loaded (type=%s)", self._model.model)
            except Exception:
                logger.exception("LiveKitEOUTurnDetector: failed to load model")
                raise
        return self._model
    
    async def process_transcript(
        self,
        transcript: str,
        is_final: bool,
        conversation_context: list[ConversationTurn],
    ) -> float:
        """
        Process transcript and return turn completion probability using LiveKit model.
        
        Args:
            transcript: Current transcript text
            is_final: Whether this is a final transcript
            conversation_context: Recent conversation turns for context
            
        Returns:
            Turn completion probability (0.0 to 1.0)
        """
        if not transcript or not transcript.strip():
            return 0.0
        
        # Only process final transcripts
        if not is_final:
            return 0.0
        
        # Convert our conversation context to LiveKit ChatContext format
        chat_ctx = self._build_chat_context(transcript, conversation_context)
        
        try:
            # Ensure model is loaded (lazy initialization)
            model = self._ensure_model()
            
            # Call the LiveKit model for prediction
            probability = await model.predict_end_of_turn(chat_ctx, timeout=3.0)
            
            logger.debug(
                "LiveKitEOUTurnDetector: prediction=%.3f for transcript=%r (context_turns=%d)",
                probability,
                transcript[:50],
                len(conversation_context),
            )
            
            return probability
        
        except Exception:
            logger.exception("LiveKitEOUTurnDetector: prediction failed, defaulting to 0.5")
            return 0.5  # Default to neutral probability on error
    
    def _build_chat_context(
        self,
        current_transcript: str,
        conversation_context: list[ConversationTurn],
    ) -> lk_llm.ChatContext:
        """
        Build LiveKit ChatContext from our conversation history.
        
        The LiveKit model expects a ChatContext with the conversation history
        plus the current user utterance (not yet in the history).
        
        Args:
            current_transcript: The current user transcript being evaluated
            conversation_context: Recent conversation turns
            
        Returns:
            LiveKit ChatContext object
        """
        chat_ctx = lk_llm.ChatContext()
        
        # Add recent conversation history (up to context_window_turns)
        recent_turns = conversation_context[-self._context_window_turns:] if conversation_context else []
        
        for turn in recent_turns:
            if turn.role == "system":
                # Skip system messages for turn detection
                continue
            elif turn.role == "user":
                chat_ctx.add_message(role="user", content=turn.content)
            elif turn.role == "assistant":
                chat_ctx.add_message(role="assistant", content=turn.content)
        
        # Add the current user utterance being evaluated
        # (this is the key input the model uses to predict if the turn is complete)
        chat_ctx.add_message(role="user", content=current_transcript)
        
        return chat_ctx
