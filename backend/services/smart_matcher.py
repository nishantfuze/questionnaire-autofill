"""Smart matching service that extracts concepts and finds relevant answers without LLM."""

import re
import logging
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict

from models import KnowledgeEntry, MatchResult, EvidenceSnippet
from services.knowledge_index import KnowledgeIndex
import config

logger = logging.getLogger(__name__)

# Concept mappings: question patterns → relevant answer keywords
CONCEPT_MAPPINGS = {
    # Frontend/Backend questions
    "frontend": ["front-end", "frontend", "ui", "user interface", "mobile app", "web app", "customer journey", "ux"],
    "backend": ["back-end", "backend", "api", "server", "infrastructure"],
    "api_platform": ["api-first", "rest api", "apis", "websocket", "integration"],
    "build_develop": ["develop", "build", "implement", "create", "ownership"],

    # Hosting questions
    "hosting": ["host", "deploy", "cloud", "aws", "saas", "on-premise", "on prem", "infrastructure"],
    "mashreq_host": ["mashreq host", "bank host"],
    "fuze_host": ["fuze host", "hosted on", "aws", "cloud"],
    "on_prem": ["on-premise", "on prem", "self-hosted", "private cloud"],

    # SDK/Integration
    "sdk": ["sdk", "library", "connector", "not recommend sdk", "single point of failure"],

    # Community/Resources
    "community": ["community", "resources", "partnerships", "bank partners", "wio", "adcb"],

    # SSO/Auth
    "sso": ["sso", "single sign", "oauth", "authentication", "jwt"],
    "ci_cd": ["ci/cd", "cicd", "pipeline", "deployment", "devops"],

    # Analytics
    "analytics": ["analytics", "reporting", "metrics", "kpi", "dashboard"],

    # Custody
    "custody": ["custody", "wallet", "hsm", "mpc", "fireblocks", "segregat"],

    # Trading
    "trading": ["trading", "order", "execution", "coins", "crypto", "asset"],
    "charting": ["chart", "technical indicator", "graph"],

    # Compliance
    "kyc_aml": ["kyc", "aml", "compliance", "regulatory"],

    # Settlement
    "settlement": ["settlement", "reconciliation", "transaction"],

    # Staking
    "staking": ["staking", "yield", "savings", "earn"],

    # Bank integration
    "bank_integration": ["casa", "fiat", "deposit", "withdrawal", "bank integration"],
}

# Question patterns that indicate "ask Mashreq" - be careful not to match product questions
MASHREQ_PATTERNS = [
    r"what.*mashreq.*use",
    r"does mashreq.*have.*team",
    r"mashreq.*dedicated.*team",
    r"mashreq.*pipeline",
    r"what.*sso.*mashreq",
    r"mashreq.*ci/cd",
    r"what is mashreq'?s",
    r"mashreq'?s\s+(ci|cd|sso|team|pipeline)",
]

# Product-related terms - if question contains these, it's likely asking about Fuze's capabilities
PRODUCT_TERMS = ["on prem", "on-prem", "sdk", "api", "host", "deploy", "integration", "prem"]

# Keywords that boost relevance
BOOST_KEYWORDS = {
    "frontend": ["bank owns", "bank retains", "control over ui", "customer journey", "api-first", "bank builds", "ownership"],
    "backend": ["api-first", "rest api", "websocket", "infrastructure"],
    "hosting": ["aws", "cloud", "me-central", "uae", "saas", "hosted on", "public cloud"],
    "sdk": ["not recommend sdk", "rest api", "single point of failure", "not recommend", "webhook", "do not recommend", "api-first"],
    "community": ["wio", "adcb", "ruya", "partnerships", "bank partners"],
    "analytics": ["kpi", "metrics", "reporting", "dashboard", "track", "fuzeOS", "grafana"],
    "build_develop": ["bank owns", "bank develops", "ownership", "api-first", "integrate"],
    "on_prem": ["cloud-hosted", "aws", "public cloud", "me-central", "saas solution", "hosted on"],
    "fuze_host": ["aws", "me-central", "public cloud", "hosted on", "saas"],
    "sso": ["authentication", "oauth", "jwt", "single sign"],
    "ci_cd": ["ci/cd", "pipeline", "deployment", "automated", "docker", "ecs"],
    "custody": ["fireblocks", "hsm", "mpc", "wallet", "segregat", "cold storage"],
}


class SmartMatcher:
    """Smart matching that extracts concepts and finds relevant answers."""

    def __init__(self, knowledge_index: KnowledgeIndex):
        self.knowledge_index = knowledge_index
        self._build_answer_index()

    def _build_answer_index(self):
        """Build an inverted index of keywords to entries."""
        self.keyword_to_entries: Dict[str, List[Tuple[int, float]]] = defaultdict(list)

        for i, entry in enumerate(self.knowledge_index.entries):
            text = f"{entry.question} {entry.answer}".lower()

            # Index by concept keywords
            for concept, keywords in CONCEPT_MAPPINGS.items():
                for kw in keywords:
                    if kw.lower() in text:
                        # Weight by how prominent the keyword is
                        count = text.count(kw.lower())
                        weight = min(count * 0.2, 1.0)
                        self.keyword_to_entries[concept].append((i, weight))

    def _extract_concepts(self, question: str) -> List[str]:
        """Extract relevant concepts from a question."""
        question_lower = question.lower()
        concepts = []

        # Check for each concept
        for concept, keywords in CONCEPT_MAPPINGS.items():
            for kw in keywords:
                if kw.lower() in question_lower:
                    concepts.append(concept)
                    break

        # Special detection for frontend/backend questions
        if any(w in question_lower for w in ["front end", "frontend", "fe ", "f/e", "ui build"]):
            concepts.append("frontend")
        if any(w in question_lower for w in ["back end", "backend", "be ", "b/e"]):
            concepts.append("backend")
        if "api platform" in question_lower or "api only" in question_lower:
            concepts.append("api_platform")
            concepts.append("frontend")
        if "host" in question_lower:
            concepts.append("hosting")
        if "who" in question_lower and ("develop" in question_lower or "build" in question_lower):
            concepts.append("build_develop")
            concepts.append("frontend")

        # Special detection for on-prem questions (asking about deployment model)
        if "on prem" in question_lower or "on-prem" in question_lower or "premise" in question_lower:
            concepts.append("on_prem")
            concepts.append("hosting")
            concepts.append("fuze_host")

        # Special detection for SDK questions
        if "sdk" in question_lower:
            concepts.append("sdk")
            concepts.append("api_platform")

        return list(set(concepts))

    def _is_mashreq_question(self, question: str) -> bool:
        """Check if this is a question about Mashreq's preferences/capabilities."""
        question_lower = question.lower()

        # Questions that compare options (Mashreq vs Fuze) are NOT Mashreq-only questions
        if " or " in question_lower and "fuze" in question_lower:
            return False

        # Questions about product features (on-prem, SDK, etc.) are product questions, not Mashreq questions
        # "Does Mashreq want SDK?" → asking if Fuze provides SDK
        # "Does Mashreq want on prem?" → asking if Fuze supports on-prem
        if any(term in question_lower for term in PRODUCT_TERMS):
            return False

        for pattern in MASHREQ_PATTERNS:
            if re.search(pattern, question_lower):
                return True

        # Specific Mashreq-only questions (internal to bank)
        mashreq_indicators = [
            "mashreq's ci/cd",
            "mashreq's sso",
            "mashreq's team",
            "mashreq's pipeline",
            "what sso does mashreq",
            "what is mashreq's ci/cd",
            "what is mashreq's pipeline",
            "mashreq have a dedicated",
            "mashreq have a fe team",
            "mashreq have a frontend team",
        ]

        for indicator in mashreq_indicators:
            if indicator in question_lower:
                return True

        # Detect "What SSO/CI-CD does Mashreq use?" pattern
        if "what" in question_lower and "mashreq" in question_lower:
            if any(term in question_lower for term in ["sso", "ci/cd", "pipeline"]):
                if "fuze" not in question_lower:
                    return True

        return False

    def _score_entry_for_concepts(self, entry: KnowledgeEntry, concepts: List[str], question: str) -> float:
        """Score an entry based on how well it matches the concepts."""
        score = 0.0
        answer_lower = entry.answer.lower()
        question_lower = question.lower()

        for concept in concepts:
            # Check boost keywords
            if concept in BOOST_KEYWORDS:
                for boost_kw in BOOST_KEYWORDS[concept]:
                    if boost_kw.lower() in answer_lower:
                        score += 0.3

            # Check concept keywords in answer
            if concept in CONCEPT_MAPPINGS:
                for kw in CONCEPT_MAPPINGS[concept]:
                    if kw.lower() in answer_lower:
                        score += 0.1

        # Bonus for answers that directly address common question patterns
        if "frontend" in concepts or "api_platform" in concepts:
            if "bank owns" in answer_lower or "bank retains" in answer_lower:
                score += 0.5
            if "api-first" in answer_lower:
                score += 0.4
            if "control over" in answer_lower and "ui" in answer_lower:
                score += 0.4

        if "hosting" in concepts:
            if "aws" in answer_lower and ("me-central" in answer_lower or "uae" in answer_lower):
                score += 0.5
            if "cloud" in answer_lower and "host" in answer_lower:
                score += 0.3

        if "sdk" in concepts:
            if "not recommend" in answer_lower and "sdk" in answer_lower:
                score += 0.8
            if "single point of failure" in answer_lower:
                score += 0.6
            if "do not recommend" in answer_lower:
                score += 0.5
            # Also boost API-first answers for SDK questions
            if "api-first" in answer_lower:
                score += 0.3

        if "on_prem" in concepts or "fuze_host" in concepts:
            # Questions about on-prem should find answers about cloud hosting
            if "hosted on" in answer_lower and "aws" in answer_lower:
                score += 0.8
            if "public cloud" in answer_lower:
                score += 0.6
            if "me-central" in answer_lower:
                score += 0.5
            if "saas" in answer_lower and ("deployed" in answer_lower or "solution" in answer_lower):
                score += 0.5

        if "community" in concepts:
            if "wio" in answer_lower or "adcb" in answer_lower:
                score += 0.5

        return score

    def match(self, question: str, category: Optional[str] = None) -> MatchResult:
        """Match a question to the best answer using concept-based matching."""

        # Check if this is a Mashreq question
        if self._is_mashreq_question(question):
            return MatchResult(
                matched_entry=None,
                similarity_score=0.0,
                confidence_score=0,
                confidence_level="Requires Human Attention",
                evidence="",
                citations=[],
                notes="This is a question for Mashreq to confirm internally."
            )

        # Extract concepts from the question
        concepts = self._extract_concepts(question)

        # Get TF-IDF results
        tfidf_results = self.knowledge_index.search(question, top_k=10)

        if not tfidf_results:
            return MatchResult(
                matched_entry=None,
                similarity_score=0.0,
                confidence_score=0,
                confidence_level="Requires Human Attention",
                evidence="",
                citations=[],
                notes="No relevant evidence found."
            )

        # Re-score based on concepts
        scored_results = []
        for entry, tfidf_score in tfidf_results:
            concept_score = self._score_entry_for_concepts(entry, concepts, question)
            # Combine scores: 40% TF-IDF, 60% concept matching
            combined_score = 0.4 * tfidf_score + 0.6 * concept_score
            scored_results.append((entry, combined_score, tfidf_score))

        # Sort by combined score
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # Get best result
        best_entry, best_score, tfidf_score = scored_results[0]

        # Calculate confidence
        if best_score >= 0.7:
            confidence_score = min(int(best_score * 100), 95)
            confidence_level = "High" if confidence_score >= 90 else "Medium"
        elif best_score >= 0.4:
            confidence_score = int(best_score * 100)
            confidence_level = "Medium" if confidence_score >= 70 else "Low"
        else:
            confidence_score = max(int(best_score * 100), 20)
            confidence_level = "Low" if confidence_score >= 40 else "Requires Human Attention"

        citation = f"[{best_entry.document_name} > {best_entry.section} > Row {best_entry.row_number}]"

        return MatchResult(
            matched_entry=best_entry,
            similarity_score=best_score,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            evidence=citation,
            citations=[citation],
            notes=f"Concepts matched: {', '.join(concepts)}" if concepts else None
        )
