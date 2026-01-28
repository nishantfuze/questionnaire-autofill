"""LLM-based answer generator using OpenAI API."""

import json
import logging
import re
from typing import List, Optional, Tuple

import config
from models import EvidenceSnippet, MatchResult, KnowledgeEntry

logger = logging.getLogger(__name__)

# System prompt for the LLM
SYSTEM_PROMPT = """You are "Bank Questionnaire Autofill Agent". Your job is to answer questionnaire questions ONLY using the provided EVIDENCE SNIPPETS from Fuze's knowledge base.

CRITICAL RULES:
1) ONLY use information from the evidence snippets. Do not use general knowledge or guess.
2) If the evidence does not contain the answer, respond: "Requires Human Attention information in provided documents."
3) If the question is asking about MASHREQ's capabilities/preferences (not Fuze's), respond: "This is a question for Mashreq to confirm internally." with confidence 0.
4) Every answer MUST cite the evidence snippets used.
5) Prefer exact phrasing from evidence. Synthesize multiple snippets when helpful.
6) Match the question's INTENT, not just keywords. A question about "frontend" needs frontend-related answers.

QUESTION TYPES TO HANDLE:
- "Does Fuze do X?" → Find evidence about Fuze's capabilities
- "Does Mashreq want X?" where X is a PRODUCT FEATURE (SDK, on-prem, API, hosting, etc.) → Answer with Fuze's capability/recommendation for X. Example: "Does Mashreq want SDK?" → answer with Fuze's SDK policy
- "Does Mashreq want X?" or "What does Mashreq use?" where X is INTERNAL (team, SSO, CI/CD pipeline) → Answer: "This is a question for Mashreq to confirm internally."
- "Who does X?" → Determine if Fuze or the bank handles it based on evidence
- "Can X be hosted by Y?" → Find hosting/deployment evidence

IMPORTANT: Questions about product features (SDK, on-prem, hosting, API integration) should be answered with Fuze's capabilities, NOT flagged as "Mashreq internal questions".

EXAMPLES:
- "Does Mashreq want on prem?" → Answer: "Fuze offers a SaaS solution hosted on AWS. On-premise deployment is not the standard model." (This is asking about Fuze's deployment options, NOT Mashreq's internal preference)
- "Does Mashreq want SDK?" → Answer: "Fuze does not recommend SDK integration as it introduces a single point of failure. Instead, Fuze provides REST APIs." (This is asking about Fuze's SDK policy, NOT Mashreq's preference)

CONFIDENCE SCORING (be generous when evidence supports the answer):
- 90-100: Evidence directly answers the question (even if synthesized from multiple snippets)
- 75-89: Evidence strongly supports the answer with minor gaps
- 50-74: Evidence partially answers but missing some details
- 0-49: Evidence doesn't answer the question / insufficient / question is for Mashreq

When the evidence DOES contain relevant information that answers the question, score 85+ even if it requires synthesis.

OUTPUT FORMAT (STRICT JSON):
{
  "answer": "string",
  "confidence_score": 0-100,
  "confidence_label": "High|Medium|Low|Requires Human Attention",
  "citations": ["[DocName > Section > Row X]"],
  "notes": "optional string for conflicts or follow-ups"
}

Return ONLY valid JSON. No other text."""


def format_evidence_snippets(snippets: List[EvidenceSnippet]) -> str:
    """Format evidence snippets for the prompt."""
    formatted = []
    for i, snippet in enumerate(snippets, 1):
        formatted.append(f"""--- Snippet {i} (similarity: {snippet.similarity_score:.2f}) ---
doc_name: {snippet.doc_name}
section: {snippet.section}
locator: {snippet.locator}
text: {snippet.text[:1500]}{"..." if len(snippet.text) > 1500 else ""}
""")
    return "\n".join(formatted)


def create_user_prompt(question: str, category: Optional[str], snippets: List[EvidenceSnippet]) -> str:
    """Create the user prompt with question and evidence."""
    evidence_text = format_evidence_snippets(snippets) if snippets else "No evidence snippets found."

    category_line = f"Category/Section: {category}" if category else ""

    return f"""Question: {question}
{category_line}

EVIDENCE_SNIPPETS:
{evidence_text}

Analyze the evidence and provide the best answer. Remember:
- Match the question's INTENT, not just keywords
- If asking about Mashreq's preferences/systems → "This is a question for Mashreq"
- If evidence doesn't answer the specific question → "Requires Human Attention information"
- Cite all evidence used"""


class LLMGenerator:
    """Generates answers using OpenAI API based on retrieved evidence."""

    def __init__(self):
        self.api_key = config.OPENAI_API_KEY
        self.model = config.LLM_MODEL
        self.max_tokens = config.LLM_MAX_TOKENS
        self.temperature = config.LLM_TEMPERATURE
        self._client = None

    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.error("openai package not installed. Run: pip install openai")
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
        Generate an answer using OpenAI based on evidence snippets.

        Returns:
            Tuple of (answer, confidence_score, confidence_label, citations, notes)
        """
        if not self.is_available():
            logger.warning("LLM not available (no API key). Falling back to simple matching.")
            return self._fallback_answer(evidence_snippets)

        if not evidence_snippets:
            return (
                "Requires Human Attention information in provided documents.",
                0,
                "Requires Human Attention",
                [],
                "No relevant evidence found in knowledge base."
            )

        user_prompt = create_user_prompt(question, category, evidence_snippets)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ]
            )

            response_text = response.choices[0].message.content.strip()
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
            confidence_label = data.get("confidence_label", "Requires Human Attention")
            citations = data.get("citations", [])
            notes = data.get("notes")

            # Validate confidence label
            if confidence_label not in ["High", "Medium", "Low", "Requires Human Attention"]:
                if confidence_score >= 90:
                    confidence_label = "High"
                elif confidence_score >= 70:
                    confidence_label = "Medium"
                elif confidence_score >= 40:
                    confidence_label = "Low"
                else:
                    confidence_label = "Requires Human Attention"

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
                "Requires Human Attention information in provided documents.",
                0,
                "Requires Human Attention",
                [],
                "No evidence found."
            )

        top_snippet = evidence_snippets[0]
        citation = f"[{top_snippet.doc_name} > {top_snippet.section} > {top_snippet.locator}]"

        # Simple confidence based on similarity
        similarity = top_snippet.similarity_score
        confidence_score = int(min(similarity * 100, 60))  # Cap at 60 for fallback

        if confidence_score >= 90:
            confidence_label = "High"
        elif confidence_score >= 70:
            confidence_label = "Medium"
        elif confidence_score >= 40:
            confidence_label = "Low"
        else:
            confidence_label = "Requires Human Attention"

        return (
            top_snippet.text,
            confidence_score,
            confidence_label,
            [citation],
            "Fallback: LLM unavailable, using top evidence snippet. Enable LLM for better accuracy."
        )
