"""Knowledge base indexing service using TF-IDF with improved retrieval."""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from models import KnowledgeEntry
import config

logger = logging.getLogger(__name__)


class KnowledgeIndex:
    """Indexes and searches the knowledge base using TF-IDF on both questions and answers."""

    def __init__(self):
        self.entries: List[KnowledgeEntry] = []
        self.question_vectorizer: Optional[TfidfVectorizer] = None
        self.answer_vectorizer: Optional[TfidfVectorizer] = None
        self.combined_vectorizer: Optional[TfidfVectorizer] = None
        self.question_matrix = None
        self.answer_matrix = None
        self.combined_matrix = None
        self._entry_id_counter = 0

    def load_all(self) -> int:
        """Load all knowledge base CSV files. Returns total entries loaded."""
        total_loaded = 0
        for filename in config.KNOWLEDGE_BASE_FILES:
            filepath = config.KNOWLEDGE_BASE_DIR / filename
            if filepath.exists():
                count = self._load_file(filepath)
                logger.info(f"Loaded {count} entries from {filename}")
                total_loaded += count
            else:
                logger.warning(f"Knowledge base file not found: {filepath}")

        if self.entries:
            self._build_index()

        logger.info(f"Total knowledge base entries: {len(self.entries)}")
        return len(self.entries)

    def _load_file(self, filepath: Path) -> int:
        """Load a single knowledge base CSV file."""
        doc_name = filepath.stem
        entries_before = len(self.entries)

        try:
            df = pd.read_csv(filepath, encoding='utf-8', on_bad_lines='skip')
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
            return 0

        # Detect file structure and extract Q&A pairs
        if "Questions_for_bidder_Questions" in doc_name:
            self._parse_questions_for_bidder(df, doc_name)
        elif "Trading_Vendor_Questions_IT_Questions" in doc_name:
            self._parse_trading_vendor(df, doc_name)
        elif "rbgplatformquestionnaire" in doc_name:
            self._parse_rbg_platform(df, doc_name)
        elif "Due_Dilgence_Template" in doc_name:
            self._parse_due_diligence(df, doc_name)
        elif "KYTP" in doc_name:
            self._parse_kytp(df, doc_name)
        else:
            self._parse_generic(df, doc_name)

        return len(self.entries) - entries_before

    def _parse_questions_for_bidder(self, df: pd.DataFrame, doc_name: str):
        """Parse Questions_for_bidder_Questions.csv format."""
        current_section = "General"

        for idx, row in df.iterrows():
            first_col = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            second_col = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""

            if first_col and not second_col:
                current_section = first_col
                continue

            if len(row) > 3:
                question = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                answer = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""

                if question and answer and question.lower() != "questions" and len(question) > 10:
                    self._add_entry(doc_name, current_section, idx + 2, question, answer)

    def _parse_trading_vendor(self, df: pd.DataFrame, doc_name: str):
        """Parse Trading_Vendor_Questions_IT_Questions.csv format."""
        current_section = "General"

        for idx, row in df.iterrows():
            first_col = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""

            if first_col and (len(row) < 2 or pd.isna(row.iloc[1]) or str(row.iloc[1]).strip() == ""):
                current_section = first_col
                continue

            if len(row) > 2:
                question = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                answer = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""

                if question and answer and question.lower() != "question" and len(question) > 10:
                    self._add_entry(doc_name, current_section, idx + 2, question, answer)

    def _parse_rbg_platform(self, df: pd.DataFrame, doc_name: str):
        """Parse rbgplatformquestionnaire_questionnaire.csv format."""
        current_section = "General"

        for idx, row in df.iterrows():
            sl_no = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            param = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""

            if sl_no and len(sl_no) == 1 and sl_no.isalpha():
                current_section = param if param else sl_no
                continue

            if len(row) > 3:
                question = param
                answer = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""

                if question and answer and question.lower() != "parameters" and len(question) > 10:
                    self._add_entry(doc_name, current_section, idx + 2, question, answer)

    def _parse_due_diligence(self, df: pd.DataFrame, doc_name: str):
        """Parse TPRMDueDiligenceResidualRiskTemplate_Due_Dilgence_Template.csv format."""
        current_section = "General"

        for idx, row in df.iterrows():
            risk_domain = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""

            if risk_domain and risk_domain.upper() == risk_domain and len(risk_domain) > 2:
                current_section = risk_domain

            if len(row) > 4:
                question = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                answer = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""

                if question and answer and "due diligence" not in question.lower()[:20] and len(question) > 10:
                    self._add_entry(doc_name, current_section, idx + 2, question, answer)

    def _parse_kytp(self, df: pd.DataFrame, doc_name: str):
        """Parse TPRMDueDiligenceResidualRiskTemplate_KYTP.csv format."""
        for idx, row in df.iterrows():
            if len(row) > 3:
                question = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                answer = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""

                if (question and answer and
                    question.lower() != "question" and
                    "<please provide" not in answer.lower() and
                    len(question) > 10):
                    self._add_entry(doc_name, "KYTP", idx + 2, question, answer)

    def _parse_generic(self, df: pd.DataFrame, doc_name: str):
        """Generic parser for unknown CSV formats."""
        columns = df.columns.tolist()
        question_col = None
        answer_col = None

        for i, col in enumerate(columns):
            col_lower = str(col).lower()
            if 'question' in col_lower or 'query' in col_lower:
                question_col = i
            elif 'answer' in col_lower or 'response' in col_lower:
                answer_col = i

        if question_col is None:
            question_col = 0 if len(columns) > 0 else None
        if answer_col is None:
            answer_col = 1 if len(columns) > 1 else None

        if question_col is not None and answer_col is not None:
            for idx, row in df.iterrows():
                question = str(row.iloc[question_col]).strip() if pd.notna(row.iloc[question_col]) else ""
                answer = str(row.iloc[answer_col]).strip() if pd.notna(row.iloc[answer_col]) else ""

                if question and answer and len(question) > 10:
                    self._add_entry(doc_name, "General", idx + 2, question, answer)

    def _add_entry(self, doc_name: str, section: str, row_number: int, question: str, answer: str):
        """Add an entry to the knowledge base."""
        if not answer or len(answer) < 5:
            return

        self._entry_id_counter += 1
        entry = KnowledgeEntry(
            id=self._entry_id_counter,
            document_name=doc_name,
            section=section,
            row_number=row_number,
            question=question,
            answer=answer
        )
        self.entries.append(entry)

    def _build_index(self):
        """Build TF-IDF indexes for questions, answers, and combined."""
        questions = [entry.question for entry in self.entries]
        answers = [entry.answer for entry in self.entries]
        # Combined: question + answer for semantic matching
        combined = [f"{entry.question} {entry.answer}" for entry in self.entries]

        # Question index
        self.question_vectorizer = TfidfVectorizer(
            min_df=config.MIN_DF,
            max_df=config.MAX_DF,
            ngram_range=config.NGRAM_RANGE,
            stop_words='english',
            lowercase=True
        )
        self.question_matrix = self.question_vectorizer.fit_transform(questions)

        # Answer index - for finding answers that contain relevant information
        self.answer_vectorizer = TfidfVectorizer(
            min_df=config.MIN_DF,
            max_df=config.MAX_DF,
            ngram_range=config.NGRAM_RANGE,
            stop_words='english',
            lowercase=True
        )
        self.answer_matrix = self.answer_vectorizer.fit_transform(answers)

        # Combined index - best of both worlds
        self.combined_vectorizer = TfidfVectorizer(
            min_df=config.MIN_DF,
            max_df=config.MAX_DF,
            ngram_range=config.NGRAM_RANGE,
            stop_words='english',
            lowercase=True
        )
        self.combined_matrix = self.combined_vectorizer.fit_transform(combined)

        logger.info(f"Built TF-IDF indexes - Q vocab: {len(self.question_vectorizer.vocabulary_)}, "
                   f"A vocab: {len(self.answer_vectorizer.vocabulary_)}, "
                   f"Combined vocab: {len(self.combined_vectorizer.vocabulary_)}")

    @property
    def vectorizer(self):
        """Backward compatibility - return combined vectorizer."""
        return self.combined_vectorizer

    def get_entry_by_id(self, entry_id: int) -> Optional[KnowledgeEntry]:
        """Get an entry by its ID."""
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def search(self, query: str, top_k: int = 5) -> List[Tuple[KnowledgeEntry, float]]:
        """
        Search using multiple strategies and combine results.
        Returns list of (entry, similarity_score) tuples.
        """
        if not self.combined_vectorizer or self.combined_matrix is None:
            return []

        # Strategy 1: Search questions
        q_scores = self._search_matrix(query, self.question_vectorizer, self.question_matrix)

        # Strategy 2: Search answers (find answers containing query concepts)
        a_scores = self._search_matrix(query, self.answer_vectorizer, self.answer_matrix)

        # Strategy 3: Search combined
        c_scores = self._search_matrix(query, self.combined_vectorizer, self.combined_matrix)

        # Weighted combination: prioritize question match, then combined, then answer
        combined_scores = np.zeros(len(self.entries))
        for i in range(len(self.entries)):
            # Question match is most important (0.5), combined (0.3), answer (0.2)
            combined_scores[i] = (0.5 * q_scores[i] + 0.3 * c_scores[i] + 0.2 * a_scores[i])

        # Get top-k indices
        top_indices = combined_scores.argsort()[-top_k:][::-1]

        results = []
        for idx in top_indices:
            if combined_scores[idx] > 0:
                results.append((self.entries[idx], float(combined_scores[idx])))

        return results

    def _search_matrix(self, query: str, vectorizer: TfidfVectorizer, matrix) -> np.ndarray:
        """Search a single TF-IDF matrix."""
        try:
            query_vector = vectorizer.transform([query])
            return (matrix @ query_vector.T).toarray().flatten()
        except Exception:
            return np.zeros(len(self.entries))

    def search_by_keywords(self, keywords: List[str], top_k: int = 5) -> List[Tuple[KnowledgeEntry, float]]:
        """Search by specific keywords in answers."""
        scores = np.zeros(len(self.entries))

        for i, entry in enumerate(self.entries):
            answer_lower = entry.answer.lower()
            question_lower = entry.question.lower()

            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in answer_lower:
                    scores[i] += 1.0
                if kw_lower in question_lower:
                    scores[i] += 0.5

        # Normalize
        max_score = scores.max() if scores.max() > 0 else 1
        scores = scores / max_score

        top_indices = scores.argsort()[-top_k:][::-1]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((self.entries[idx], float(scores[idx])))

        return results
