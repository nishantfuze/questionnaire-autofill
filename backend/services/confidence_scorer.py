"""Confidence scoring service for match quality assessment."""

import logging
from typing import Tuple

import config

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """Calculates confidence scores for question matches."""

    def calculate(
        self,
        similarity_score: float,
        question: str,
        answer: str,
        is_ambiguous: bool = False
    ) -> Tuple[int, str]:
        """
        Calculate confidence score from similarity and other factors.

        Returns:
            Tuple of (score 0-100, level string)
        """
        # Base score: map similarity (0.0-1.0) to (0-100)
        base_score = int(similarity_score * 100)

        # Apply bonuses and penalties
        adjustments = 0

        # Bonus for domain keyword match
        question_lower = question.lower()
        for keyword in config.DOMAIN_KEYWORDS:
            if keyword in question_lower:
                adjustments += 5
                break  # Only apply bonus once

        # Penalty if answer is too short
        if len(answer) < 50:
            adjustments -= 10
        elif len(answer) < 100:
            adjustments -= 5

        # Penalty if ambiguous (top 2 scores are similar)
        if is_ambiguous:
            adjustments -= 5

        # Bonus if answer contains relevant terms from question
        question_terms = set(question_lower.split())
        answer_lower = answer.lower()
        matching_terms = sum(1 for term in question_terms if len(term) > 4 and term in answer_lower)
        if matching_terms >= 3:
            adjustments += 5

        # Calculate final score, clamped to 0-100
        final_score = max(0, min(100, base_score + adjustments))

        # Determine confidence level
        confidence_level = self._get_level(final_score)

        return final_score, confidence_level

    def _get_level(self, score: int) -> str:
        """Get confidence level string from score."""
        if score >= config.CONFIDENCE_HIGH:
            return "High"
        elif score >= config.CONFIDENCE_MEDIUM:
            return "Medium"
        elif score >= config.CONFIDENCE_LOW:
            return "Low"
        else:
            return "Requires Human Attention"
