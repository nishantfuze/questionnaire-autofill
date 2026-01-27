"""Text matching service for question similarity."""

import re
import logging
from typing import Optional, Tuple, List

from models import KnowledgeEntry, MatchResult
from services.knowledge_index import KnowledgeIndex
from services.confidence_scorer import ConfidenceScorer
import config

logger = logging.getLogger(__name__)


class TextMatcher:
    """Matches input questions against the knowledge base."""

    def __init__(self, knowledge_index: KnowledgeIndex, confidence_scorer: ConfidenceScorer):
        self.knowledge_index = knowledge_index
        self.confidence_scorer = confidence_scorer

    def preprocess(self, text: str) -> str:
        """Preprocess text for matching."""
        if not text:
            return ""

        # Lowercase
        text = text.lower()

        # Expand abbreviations
        for abbrev, expansion in config.ABBREVIATIONS.items():
            # Match whole word abbreviations
            pattern = r'\b' + re.escape(abbrev) + r'\b'
            text = re.sub(pattern, f"{abbrev} {expansion}", text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove special characters but keep alphanumeric and spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def match(self, question: str) -> MatchResult:
        """Match a question against the knowledge base."""
        if not question or len(question.strip()) < 5:
            return MatchResult(
                matched_entry=None,
                similarity_score=0.0,
                confidence_score=0,
                confidence_level="Insufficient",
                evidence=""
            )

        # Preprocess the question
        processed_question = self.preprocess(question)

        # Search the knowledge base
        results = self.knowledge_index.search(processed_question, top_k=3)

        if not results:
            return MatchResult(
                matched_entry=None,
                similarity_score=0.0,
                confidence_score=0,
                confidence_level="Insufficient",
                evidence=""
            )

        # Get top match
        top_entry, top_score = results[0]

        # Check for ambiguity (top 2 scores are similar)
        is_ambiguous = False
        if len(results) > 1:
            second_score = results[1][1]
            if top_score > 0 and (top_score - second_score) / top_score < 0.1:
                is_ambiguous = True

        # Calculate confidence score
        confidence_score, confidence_level = self.confidence_scorer.calculate(
            similarity_score=top_score,
            question=question,
            answer=top_entry.answer,
            is_ambiguous=is_ambiguous
        )

        # Format evidence citation
        evidence = f"[{top_entry.document_name} > {top_entry.section} > Row {top_entry.row_number}]"

        return MatchResult(
            matched_entry=top_entry,
            similarity_score=top_score,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            evidence=evidence
        )

    def batch_match(self, questions: List[str]) -> List[MatchResult]:
        """Match multiple questions against the knowledge base."""
        return [self.match(q) for q in questions]
