"""Conversation context manager for turn detection and LLM."""

from __future__ import annotations

import json
import time
from collections import deque
from typing import Any, Literal

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
        role: Literal["user", "assistant", "system", "tool_call", "tool_result"],
        content: str,
        metadata: dict | None = None,
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        """
        Add a new turn to the conversation.

        Args:
            role:         Speaker role.
            content:      Turn content (transcript, response, or tool result).
            metadata:     Optional metadata dict.
            tool_calls:   For role="tool_call": list of call dicts
                          ``{"name": str, "args": dict, "id": str}``.
            tool_call_id: For role="tool_result": id of the call this answers.
        """
        turn = ConversationTurn(
            role=role,
            content=content,
            timestamp=time.time(),
            metadata=metadata or {},
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
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
            messages.append(
                LLMMessage(
                    role="system",
                    content=system_prompt,
                )
            )

        # Convert turns to messages
        for turn in self._turns:
            messages.append(
                LLMMessage(
                    role=turn.role,
                    content=turn.content,
                )
            )

        return messages

    def dump_transcript(self) -> list[dict[str, Any]]:
        """
        Return the full conversation as a list of plain dicts, suitable for
        logging, storing in a database, or sending to an analytics service.

        Each dict has at minimum:
            - ``role``      : "system" | "user" | "assistant" |
                              "tool_call" | "tool_result"
            - ``content``   : str
            - ``timestamp`` : float (unix seconds)

        tool_call entries also have:
            - ``tool_calls``: list of {"name": str, "args": dict, "id": str}

        tool_result entries also have:
            - ``tool_call_id``: str
        """
        records = []
        for turn in self._turns:
            record: dict[str, Any] = {
                "role": turn.role,
                "content": turn.content,
                "timestamp": turn.timestamp,
            }
            if turn.tool_calls:
                record["tool_calls"] = turn.tool_calls
            if turn.tool_call_id:
                record["tool_call_id"] = turn.tool_call_id
            if turn.metadata:
                record["metadata"] = turn.metadata
            records.append(record)
        return records

    def dump_transcript_json(self, indent: int = 2) -> str:
        """Return the transcript as a formatted JSON string."""
        return json.dumps(self.dump_transcript(), indent=indent, default=str)

    def clear(self) -> None:
        """Clear all conversation history."""
        self._turns.clear()

    def __len__(self) -> int:
        """Get the number of turns in the conversation."""
        return len(self._turns)

    def __repr__(self) -> str:
        """String representation of conversation context."""
        return f"ConversationContext(turns={len(self._turns)}, max_turns={self._max_turns})"
