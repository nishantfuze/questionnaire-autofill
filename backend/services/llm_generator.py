"""LLM-based answer generator using Claude API."""

import json
import logging
import re
from typing import List, Optional, Tuple

import config
from models import EvidenceSnippet, MatchResult, KnowledgeEntry

logger = logging.getLogger(__name__)

# System prompt for the LLM
SYSTEM_PROMPT = """You are "Bank Questionnaire Autofill Agent". Your job is to answer questionnaire questions ONLY using the provided EVIDENCE SNIPPETS (retrieved from our knowledge base). Treat evidence as the only source of truth.

CRITICAL RULES
1) Do not use general knowledge. Do not guess.
2) If the evidence does not explicitly contain the answer, output:
   Answer = "Insufficient information in provided documents."
   Confidence <= 39
3) Every answer MUST include citations to the evidence snippets used.
4) Prefer exact phrasing from evidence. Only paraphrase lightly to fit the question.
5) If multiple evidence snippets conflict, surface the conflict, choose the most authoritative, and reduce confidence.

CONFIDENCE SCORING RUBRIC
- 90–100: Explicit answer appears verbatim or near-verbatim in evidence; correct scope; no ambiguity.
- 70–89: Evidence strongly supports answer but needs small inference or mapping.
- 40–69: Partial support; missing key details; answer is incomplete.
- 0–39: Not supported / insufficient evidence.

OUTPUT FORMAT (STRICT JSON ONLY)
Return a JSON object EXACTLY in this schema:

{
  "answer": "string",
  "confidence_score": 0,
  "confidence_label": "High|Medium|Low|Insufficient",
  "citations": [
    "[DocName > Section > Locator]"
  ],
  "notes": "string (optional; only if conflicts/assumptions/need follow-up)"
}

DO NOT output anything else. Only valid JSON."""


def format_evidence_snippets(snippets: List[EvidenceSnippet]) -> str:
    """Format evidence snippets for the prompt."""
    formatted = []
    for i, snippet in enumerate(snippets, 1):
        formatted.append(f"""--- Snippet {i} ---
doc_name: {snippet.doc_name}
section: {snippet.section}
locator: {snippet.locator}
text: {snippet.text}
""")
    return "\n".join(formatted)


def create_user_prompt(question: str, category: Optional[str], snippets: List[EvidenceSnippet]) -> str:
    """Create the user prompt with question and evidence."""
    evidence_text = format_evidence_snippets(snippets) if snippets else "No evidence snippets found."

    category_line = f"Category/Section: {category}" if category else "Category/Section: Not specified"

    return f"""Question: {question}
{category_line}

EVIDENCE_SNIPPETS:
{evidence_text}"""


class LLMGenerator:
    """Generates answers using Claude API based on retrieved evidence."""

    def __init__(self):
        self.api_key = config.ANTHROPIC_API_KEY
        self.model = config.LLM_MODEL
        self.max_tokens = config.LLM_MAX_TOKENS
        self.temperature = config.LLM_TEMPERATURE
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.error("anthropic package not installed. Run: pip install anthropic")
                raise
        return self._client

    def is_available(self) -> bool:
        """Check if LLM is configured and available."""
        return bool(self.api_key)

    def generate_answer(
        self,
        question: str,
        evidence_snippets: List[EvidenceSnippet],
        category: Optional[str] = None
    ) -> Tuple[str, int, str, List[str], Optional[str]]:
        """
        Generate an answer using Claude based on evidence snippets.

        Returns:
            Tuple of (answer, confidence_score, confidence_label, citations, notes)
        """
        if not self.is_available():
            logger.warning("LLM not available (no API key). Falling back to simple matching.")
            return self._fallback_answer(evidence_snippets)

        if not evidence_snippets:
            return (
                "Insufficient information in provided documents.",
                0,
                "Insufficient",
                [],
                "No relevant evidence found in knowledge base."
            )

        user_prompt = create_user_prompt(question, category, evidence_snippets)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            response_text = response.content[0].text.strip()
            return self._parse_response(response_text, evidence_snippets)

        except Exception as e:
            logger.error(f"LLM API error: {e}")
            return self._fallback_answer(evidence_snippets)

    def _parse_response(
        self,
        response_text: str,
        evidence_snippets: List[EvidenceSnippet]
    ) -> Tuple[str, int, str, List[str], Optional[str]]:
        """Parse the JSON response from the LLM."""
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                response_text = json_match.group()

            data = json.loads(response_text)

            answer = data.get("answer", "")
            confidence_score = int(data.get("confidence_score", 0))
            confidence_label = data.get("confidence_label", "Insufficient")
            citations = data.get("citations", [])
            notes = data.get("notes")

            # Validate confidence label
            if confidence_label not in ["High", "Medium", "Low", "Insufficient"]:
                if confidence_score >= 90:
                    confidence_label = "High"
                elif confidence_score >= 70:
                    confidence_label = "Medium"
                elif confidence_score >= 40:
                    confidence_label = "Low"
                else:
                    confidence_label = "Insufficient"

            return (answer, confidence_score, confidence_label, citations, notes)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response text: {response_text}")
            return self._fallback_answer(evidence_snippets)

    def _fallback_answer(
        self,
        evidence_snippets: List[EvidenceSnippet]
    ) -> Tuple[str, int, str, List[str], Optional[str]]:
        """Fallback to using top evidence snippet directly."""
        if not evidence_snippets:
            return (
                "Insufficient information in provided documents.",
                0,
                "Insufficient",
                [],
                "No evidence found."
            )

        top_snippet = evidence_snippets[0]
        citation = f"[{top_snippet.doc_name} > {top_snippet.section} > {top_snippet.locator}]"

        # Simple confidence based on similarity
        similarity = top_snippet.similarity_score
        confidence_score = int(similarity * 100)

        if confidence_score >= 90:
            confidence_label = "High"
        elif confidence_score >= 70:
            confidence_label = "Medium"
        elif confidence_score >= 40:
            confidence_label = "Low"
        else:
            confidence_label = "Insufficient"

        return (
            top_snippet.text,
            confidence_score,
            confidence_label,
            [citation],
            "Fallback: LLM unavailable, using top evidence snippet directly."
        )
