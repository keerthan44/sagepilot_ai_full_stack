"""Turn signal aggregator for combining multiple turn detectors."""

from __future__ import annotations

from typing import Literal


class TurnAggregator:
    """
    Aggregates turn signals from multiple detectors.
    
    Supports different aggregation strategies for combining audio and text
    turn detection signals.
    """
    
    def __init__(
        self,
        strategy: Literal["any", "all", "weighted", "majority"] = "weighted",
        weights: dict[str, float] | None = None,
    ):
        """
        Initialize turn aggregator.
        
        Args:
            strategy: Aggregation strategy
                - "any": Turn complete if either detector signals
                - "all": Turn complete only if both detectors signal
                - "weighted": Weighted average of probabilities
                - "majority": Threshold-based voting
            weights: Weights for "weighted" strategy (e.g., {"audio": 0.4, "text": 0.6})
        """
        self._strategy = strategy
        self._weights = weights or {"audio": 0.5, "text": 0.5}
        
        # Normalize weights
        total_weight = sum(self._weights.values())
        if total_weight > 0:
            self._weights = {k: v / total_weight for k, v in self._weights.items()}
    
    def aggregate(
        self,
        audio_prob: float | None,
        text_prob: float | None,
        audio_threshold: float = 0.5,
        text_threshold: float = 0.7,
    ) -> bool:
        """
        Aggregate turn signals and decide if turn is complete.
        
        Args:
            audio_prob: Audio turn probability (None if not available)
            text_prob: Text turn probability (None if not available)
            audio_threshold: Threshold for audio signal
            text_threshold: Threshold for text signal
            
        Returns:
            True if turn is complete, False otherwise
        """
        # Handle cases where one or both signals are None
        if audio_prob is None and text_prob is None:
            return False
        
        if audio_prob is None:
            # Only text signal available
            return text_prob >= text_threshold
        
        if text_prob is None:
            # Only audio signal available
            return audio_prob >= audio_threshold
        
        # Both signals available, apply strategy
        if self._strategy == "any":
            # Turn complete if either detector signals
            return (audio_prob >= audio_threshold) or (text_prob >= text_threshold)
        
        elif self._strategy == "all":
            # Turn complete only if both detectors signal
            return (audio_prob >= audio_threshold) and (text_prob >= text_threshold)
        
        elif self._strategy == "weighted":
            # Weighted average of probabilities
            audio_weight = self._weights.get("audio", 0.5)
            text_weight = self._weights.get("text", 0.5)
            
            weighted_prob = (audio_prob * audio_weight) + (text_prob * text_weight)
            
            # Use average of thresholds for comparison
            avg_threshold = (audio_threshold + text_threshold) / 2
            return weighted_prob >= avg_threshold
        
        elif self._strategy == "majority":
            # Majority voting (at least one must exceed threshold)
            audio_vote = audio_prob >= audio_threshold
            text_vote = text_prob >= text_threshold
            
            # At least one must vote for turn complete
            return audio_vote or text_vote
        
        else:
            # Default to weighted strategy
            return self.aggregate(
                audio_prob,
                text_prob,
                audio_threshold,
                text_threshold,
            )
    
    def get_aggregated_probability(
        self,
        audio_prob: float | None,
        text_prob: float | None,
    ) -> float:
        """
        Get aggregated turn probability without thresholding.
        
        Args:
            audio_prob: Audio turn probability (None if not available)
            text_prob: Text turn probability (None if not available)
            
        Returns:
            Aggregated probability (0.0 to 1.0)
        """
        if audio_prob is None and text_prob is None:
            return 0.0
        
        if audio_prob is None:
            return text_prob or 0.0
        
        if text_prob is None:
            return audio_prob or 0.0
        
        # Both available, use weighted average
        audio_weight = self._weights.get("audio", 0.5)
        text_weight = self._weights.get("text", 0.5)
        
        return (audio_prob * audio_weight) + (text_prob * text_weight)
