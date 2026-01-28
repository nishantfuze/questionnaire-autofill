"""Pydantic models for the questionnaire autofill backend."""

from typing import Optional, List
from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    """A single Q&A entry from the knowledge base."""
    id: int
    document_name: str
    section: str
    row_number: int
    question: str
    answer: str


class EvidenceSnippet(BaseModel):
    """An evidence snippet retrieved from the knowledge base."""
    doc_name: str
    section: str
    locator: str
    text: str
    similarity_score: float = 0.0


class MatchResult(BaseModel):
    """Result of matching a question against the knowledge base."""
    matched_entry: Optional[KnowledgeEntry] = None
    similarity_score: float = 0.0
    confidence_score: int = 0
    confidence_level: str = "Requires Human Attention"
    evidence: str = ""
    citations: List[str] = []
    notes: Optional[str] = None


class ProcessingStatus(BaseModel):
    """Status update during questionnaire processing."""
    state: str = Field(..., description="processing, ready, or error")
    progress: int = Field(..., ge=0, le=100)
    message: str
    output_filename: Optional[str] = None


class QuestionnaireRow(BaseModel):
    """A row from the input questionnaire."""
    row_number: int
    question: str
    original_data: dict
