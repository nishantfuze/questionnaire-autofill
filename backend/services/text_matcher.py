"""Text matching service for question similarity with LLM-based answer generation."""

import re
import logging
from typing import Optional, List

from models import KnowledgeEntry, MatchResult, EvidenceSnippet
from services.knowledge_index import KnowledgeIndex
from services.confidence_scorer import ConfidenceScorer
from services.llm_generator import LLMGenerator
import config

logger = logging.getLogger(__name__)


class TextMatcher:
    """Matches input questions against the knowledge base and generates answers."""

    def __init__(
        self,
        knowledge_index: KnowledgeIndex,
        confidence_scorer: ConfidenceScorer,
        llm_generator: Optional[LLMGenerator] = None
    ):
        self.knowledge_index = knowledge_index
        self.confidence_scorer = confidence_scorer
        self.llm_generator = llm_generator
        self.use_llm = config.USE_LLM and llm_generator is not None

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

    def retrieve_evidence(self, question: str, top_k: int = None) -> List[EvidenceSnippet]:
        """Retrieve evidence snippets for a question."""
        if top_k is None:
            top_k = config.TOP_K_EVIDENCE

        processed_question = self.preprocess(question)
        results = self.knowledge_index.search(processed_question, top_k=top_k)

        snippets = []
        for entry, score in results:
            snippet = EvidenceSnippet(
                doc_name=entry.document_name,
                section=entry.section,
                locator=f"Row {entry.row_number}",
                text=entry.answer,
                similarity_score=score
            )
            snippets.append(snippet)

        return snippets

    def match(self, question: str, category: Optional[str] = None) -> MatchResult:
        """Match a question against the knowledge base and generate an answer."""
        if not question or len(question.strip()) < 5:
            return MatchResult(
                matched_entry=None,
                similarity_score=0.0,
                confidence_score=0,
                confidence_level="Insufficient",
                evidence="",
                citations=[],
                notes="Question too short or empty."
            )

        # Retrieve evidence snippets
        evidence_snippets = self.retrieve_evidence(question)

        if not evidence_snippets:
            return MatchResult(
                matched_entry=None,
                similarity_score=0.0,
                confidence_score=0,
                confidence_level="Insufficient",
                evidence="",
                citations=[],
                notes="No relevant evidence found in knowledge base."
            )

        # Get top match for backward compatibility
        top_snippet = evidence_snippets[0]
        top_entry = self._snippet_to_entry(top_snippet)

        # Use LLM if available and enabled
        if self.use_llm and self.llm_generator and self.llm_generator.is_available():
            answer, confidence_score, confidence_level, citations, notes = \
                self.llm_generator.generate_answer(question, evidence_snippets, category)

            # Create a synthetic entry with the LLM-generated answer
            result_entry = KnowledgeEntry(
                id=top_entry.id if top_entry else 0,
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

        # Fallback to simple matching (original behavior)
        return self._simple_match(question, evidence_snippets, top_entry)

    def _simple_match(
        self,
        question: str,
        evidence_snippets: List[EvidenceSnippet],
        top_entry: Optional[KnowledgeEntry]
    ) -> MatchResult:
        """Simple matching without LLM (original behavior)."""
        if not evidence_snippets or not top_entry:
            return MatchResult(
                matched_entry=None,
                similarity_score=0.0,
                confidence_score=0,
                confidence_level="Insufficient",
                evidence="",
                citations=[],
                notes=None
            )

        top_snippet = evidence_snippets[0]

        # Check for ambiguity (top 2 scores are similar)
        is_ambiguous = False
        if len(evidence_snippets) > 1:
            top_score = top_snippet.similarity_score
            second_score = evidence_snippets[1].similarity_score
            if top_score > 0 and (top_score - second_score) / top_score < 0.1:
                is_ambiguous = True

        # Calculate confidence score
        confidence_score, confidence_level = self.confidence_scorer.calculate(
            similarity_score=top_snippet.similarity_score,
            question=question,
            answer=top_entry.answer,
            is_ambiguous=is_ambiguous
        )

        # Format evidence citation
        citation = f"[{top_entry.document_name} > {top_entry.section} > Row {top_entry.row_number}]"

        return MatchResult(
            matched_entry=top_entry,
            similarity_score=top_snippet.similarity_score,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            evidence=citation,
            citations=[citation],
            notes=None
        )

    def _snippet_to_entry(self, snippet: EvidenceSnippet) -> Optional[KnowledgeEntry]:
        """Convert an evidence snippet back to a knowledge entry."""
        # Search for the original entry in the knowledge index
        for entry in self.knowledge_index.entries:
            if (entry.document_name == snippet.doc_name and
                entry.section == snippet.section and
                entry.answer == snippet.text):
                return entry

        # If not found, create a synthetic entry
        row_num = 0
        if snippet.locator.startswith("Row "):
            try:
                row_num = int(snippet.locator.replace("Row ", ""))
            except ValueError:
                pass

        return KnowledgeEntry(
            id=0,
            document_name=snippet.doc_name,
            section=snippet.section,
            row_number=row_num,
            question="",
            answer=snippet.text
        )

    def batch_match(self, questions: List[str]) -> List[MatchResult]:
        """Match multiple questions against the knowledge base."""
        return [self.match(q) for q in questions]
