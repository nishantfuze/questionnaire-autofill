"""Hybrid matcher that combines SmartMatcher's retrieval with LLM synthesis."""

import logging
from typing import Optional, List

from models import KnowledgeEntry, MatchResult, EvidenceSnippet
from services.knowledge_index import KnowledgeIndex
from services.smart_matcher import SmartMatcher
from services.llm_generator import LLMGenerator
import config

logger = logging.getLogger(__name__)


class HybridMatcher:
    """Combines SmartMatcher's concept-based retrieval with LLM-based answer synthesis."""

    def __init__(
        self,
        knowledge_index: KnowledgeIndex,
        smart_matcher: SmartMatcher,
        llm_generator: LLMGenerator
    ):
        self.knowledge_index = knowledge_index
        self.smart_matcher = smart_matcher
        self.llm_generator = llm_generator

    def match(self, question: str, category: Optional[str] = None) -> MatchResult:
        """Match using SmartMatcher's retrieval + LLM synthesis."""

        # First, check if SmartMatcher identifies this as a Mashreq question
        smart_result = self.smart_matcher.match(question, category)

        if smart_result.notes and "Mashreq" in smart_result.notes:
            # This is a question for Mashreq - return as-is
            return smart_result

        # Get top evidence using SmartMatcher's concept-based ranking
        evidence_snippets = self._get_smart_evidence(question, top_k=config.TOP_K_EVIDENCE)

        if not evidence_snippets:
            return MatchResult(
                matched_entry=None,
                similarity_score=0.0,
                confidence_score=0,
                confidence_level="Requires Human Attention",
                evidence="",
                citations=[],
                notes="No relevant evidence found in knowledge base."
            )

        # Use LLM to synthesize the answer
        if self.llm_generator and self.llm_generator.is_available():
            answer, confidence_score, confidence_level, citations, notes = \
                self.llm_generator.generate_answer(question, evidence_snippets, category)

            top_snippet = evidence_snippets[0]
            result_entry = KnowledgeEntry(
                id=0,
                document_name=top_snippet.doc_name,
                section=top_snippet.section,
                row_number=int(top_snippet.locator.replace("Row ", "")) if top_snippet.locator.startswith("Row ") else 0,
                question=question,
                answer=answer
            )

            return MatchResult(
                matched_entry=result_entry,
                similarity_score=top_snippet.similarity_score,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                evidence=citations[0] if citations else "",
                citations=citations,
                notes=notes
            )

        # Fallback to SmartMatcher result if LLM is not available
        return smart_result

    def _get_smart_evidence(self, question: str, top_k: int = 5) -> List[EvidenceSnippet]:
        """Get evidence using SmartMatcher's concept-based scoring."""
        concepts = self.smart_matcher._extract_concepts(question)

        # Get TF-IDF results
        tfidf_results = self.knowledge_index.search(question, top_k=20)

        if not tfidf_results:
            return []

        # Re-score based on concepts (same logic as SmartMatcher)
        scored_results = []
        for entry, tfidf_score in tfidf_results:
            concept_score = self.smart_matcher._score_entry_for_concepts(entry, concepts, question)
            combined_score = 0.4 * tfidf_score + 0.6 * concept_score
            scored_results.append((entry, combined_score))

        # Sort by combined score
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # Convert to evidence snippets
        snippets = []
        for entry, score in scored_results[:top_k]:
            snippet = EvidenceSnippet(
                doc_name=entry.document_name,
                section=entry.section,
                locator=f"Row {entry.row_number}",
                text=entry.answer,
                similarity_score=score
            )
            snippets.append(snippet)

        return snippets
