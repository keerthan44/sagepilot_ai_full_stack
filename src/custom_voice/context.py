"""Conversation context manager for turn detection and LLM."""

from __future__ import annotations

import time
from collections import deque
from typing import Literal

from .protocols import ConversationTurn, LLMMessage


class ConversationContext:
    """
    Manages conversation history for turn detection and LLM.
    
    Maintains a sliding window of recent turns for efficient access by
    text-based turn detectors, while also keeping full history for LLM.
    """
    
    def __init__(self, max_turns: int | None = None):
        """
        Initialize conversation context.
        
        Args:
            max_turns: Maximum number of turns to keep (None = unlimited)
        """
        self._turns: deque[ConversationTurn] = deque(maxlen=max_turns)
        self._max_turns = max_turns
    
    def add_turn(
        self,
        role: Literal["user", "assistant", 'system'],
        content: str,
        metadata: dict | None = None,
    ) -> None:
        """
        Add a new turn to the conversation.
        
        Args:
            role: Speaker role (user or assistant)
            content: Turn content (transcript or response)
            metadata: Optional metadata (duration, confidence, etc.)
        """
        turn = ConversationTurn(
            role=role,
            content=content,
            timestamp=time.time(),
            metadata=metadata or {},
        )
        self._turns.append(turn)
    
    def get_last_n_turns(self, n: int) -> list[ConversationTurn]:
        """
        Get the last N turns from the conversation.
        
        Args:
            n: Number of recent turns to retrieve
            
        Returns:
            List of recent conversation turns (most recent last)
        """
        if n <= 0:
            return []
        
        # Convert deque to list and get last n items
        turns_list = list(self._turns)
        return turns_list[-n:] if len(turns_list) >= n else turns_list
    
    def get_full_history(self) -> list[ConversationTurn]:
        """
        Get the complete conversation history.
        
        Returns:
            List of all conversation turns
        """
        return list(self._turns)
    
    def to_llm_messages(
        self,
        system_prompt: str | None = None,
    ) -> list[LLMMessage]:
        """
        Convert conversation turns to LLM message format.
        
        Args:
            system_prompt: Optional system prompt to prepend
            
        Returns:
            List of LLM messages
        """
        messages: list[LLMMessage] = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append(LLMMessage(
                role="system",
                content=system_prompt,
            ))
        
        # Convert turns to messages
        for turn in self._turns:
            messages.append(LLMMessage(
                role=turn.role,
                content=turn.content,
            ))
        
        return messages
    
    def clear(self) -> None:
        """Clear all conversation history."""
        self._turns.clear()
    
    def __len__(self) -> int:
        """Get the number of turns in the conversation."""
        return len(self._turns)
    
    def __repr__(self) -> str:
        """String representation of conversation context."""
        return f"ConversationContext(turns={len(self._turns)}, max_turns={self._max_turns})"
