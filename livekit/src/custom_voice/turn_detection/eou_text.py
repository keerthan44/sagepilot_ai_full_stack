"""Text-based end-of-utterance turn detection."""

from __future__ import annotations

import re

from ..protocols import ConversationTurn
from .base import TextTurnDetector


class EOUTextTurnDetector(TextTurnDetector):
    """
    Text-based turn detector using end-of-utterance patterns.
    
    Analyzes linguistic patterns, punctuation, and semantic completeness
    to determine turn completion. Similar to LiveKit EOU model but simplified.
    """
    
    def __init__(
        self,
        *,
        threshold: float = 0.7,
        context_window_turns: int = 4,
    ):
        """
        Initialize EOU text turn detector.
        
        Args:
            threshold: Turn completion probability threshold
            context_window_turns: Number of conversation turns to consider
        """
        super().__init__(
            threshold=threshold,
            context_window_turns=context_window_turns,
        )
        
        # Patterns that indicate end of utterance
        self._terminal_punctuation = re.compile(r'[.!?]$')
        self._question_words = {
            'what', 'when', 'where', 'who', 'whom', 'whose', 'why', 'which', 'how',
            'can', 'could', 'would', 'should', 'will', 'do', 'does', 'did', 'is', 'are',
        }
    
    async def process_transcript(
        self,
        transcript: str,
        is_final: bool,
        conversation_context: list[ConversationTurn],
    ) -> float:
        """
        Process transcript and return turn completion probability.
        
        Args:
            transcript: Current transcript text
            is_final: Whether this is a final transcript
            conversation_context: Recent conversation turns for context
            
        Returns:
            Turn completion probability (0.0 to 1.0)
        """
        if not transcript or not transcript.strip():
            return 0.0
        
        # Only process final transcripts for turn detection
        if not is_final:
            return 0.0
        
        transcript = transcript.strip()
        
        # Calculate probability based on multiple signals
        probability = 0.0
        signals = []
        
        # Signal 1: Terminal punctuation (strong indicator)
        if self._terminal_punctuation.search(transcript):
            signals.append(0.8)
        
        # Signal 2: Question detection
        if self._is_question(transcript):
            signals.append(0.7)
        
        # Signal 3: Length-based heuristic
        word_count = len(transcript.split())
        if word_count >= 5:  # Reasonable utterance length
            signals.append(0.6)
        elif word_count >= 10:  # Longer utterance
            signals.append(0.8)
        
        # Signal 4: Context-based analysis
        context_signal = self._analyze_context(transcript, conversation_context)
        if context_signal > 0:
            signals.append(context_signal)
        
        # Aggregate signals
        if signals:
            probability = sum(signals) / len(signals)
        
        return min(probability, 1.0)
    
    def _is_question(self, text: str) -> bool:
        """Check if text is a question."""
        # Check for question mark
        if '?' in text:
            return True
        
        # Check for question words at start
        words = text.lower().split()
        if words and words[0] in self._question_words:
            return True
        
        return False
    
    def _analyze_context(
        self,
        transcript: str,
        conversation_context: list[ConversationTurn],
    ) -> float:
        """
        Analyze conversation context to determine turn probability.
        
        Args:
            transcript: Current transcript
            conversation_context: Recent conversation turns
            
        Returns:
            Context-based probability signal (0.0 to 1.0)
        """
        if not conversation_context:
            return 0.5  # Neutral if no context
        
        # Get last few turns
        recent_turns = conversation_context[-self._context_window_turns:]
        
        # Check if this follows a question from assistant
        if recent_turns:
            last_turn = recent_turns[-1]
            if last_turn.role == "assistant" and '?' in last_turn.content:
                # User is likely responding to a question
                return 0.7
        
        # Check for conversational patterns
        transcript_lower = transcript.lower()
        
        # Affirmative/negative responses
        if transcript_lower in {'yes', 'no', 'yeah', 'nope', 'sure', 'okay', 'ok'}:
            return 0.9
        
        # Greetings/farewells
        if any(word in transcript_lower for word in ['hello', 'hi', 'hey', 'goodbye', 'bye', 'thanks', 'thank you']):
            return 0.8
        
        return 0.5  # Default neutral
