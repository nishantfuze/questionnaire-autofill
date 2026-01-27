"""CSV processing service for parsing and generating questionnaire files."""

import io
import logging
from typing import List, Tuple, Optional

import pandas as pd

from models import QuestionnaireRow, MatchResult

logger = logging.getLogger(__name__)


class CSVProcessor:
    """Processes input questionnaires and generates output CSVs."""

    def __init__(self):
        self.question_column: Optional[str] = None
        self.original_columns: List[str] = []

    def parse_input(self, file_content: bytes, filename: str) -> Tuple[List[QuestionnaireRow], pd.DataFrame]:
        """
        Parse input questionnaire CSV.

        Returns:
            Tuple of (list of QuestionnaireRow, original DataFrame)
        """
        # Try to read as CSV with various encodings
        df = None
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                df = pd.read_csv(io.BytesIO(file_content), encoding=encoding, on_bad_lines='skip')
                break
            except Exception:
                continue

        if df is None:
            raise ValueError("Could not parse the CSV file with any supported encoding")

        self.original_columns = df.columns.tolist()

        # Detect question column
        self.question_column = self._detect_question_column(df)

        if not self.question_column:
            raise ValueError("Could not detect question column in the input file")

        logger.info(f"Detected question column: '{self.question_column}'")

        # Extract questionnaire rows
        rows = []
        for idx, row in df.iterrows():
            question = str(row[self.question_column]).strip() if pd.notna(row[self.question_column]) else ""

            if question and len(question) > 5:
                rows.append(QuestionnaireRow(
                    row_number=idx,
                    question=question,
                    original_data=row.to_dict()
                ))

        return rows, df

    def _detect_question_column(self, df: pd.DataFrame) -> Optional[str]:
        """Detect which column contains questions."""
        columns = df.columns.tolist()

        # Priority 1: Look for columns explicitly named question/query
        for col in columns:
            col_lower = str(col).lower()
            if col_lower in ['question', 'questions', 'query', 'queries', 'vendor queries']:
                return col

        # Priority 2: Look for columns containing question/query
        for col in columns:
            col_lower = str(col).lower()
            if 'question' in col_lower or 'query' in col_lower:
                return col

        # Priority 3: Use first column that has mostly text content
        for col in columns:
            sample = df[col].dropna().astype(str)
            if len(sample) > 0:
                avg_len = sample.str.len().mean()
                # Questions tend to be longer text
                if avg_len > 20:
                    return col

        # Fallback: first column
        return columns[0] if columns else None

    def generate_output(
        self,
        original_df: pd.DataFrame,
        rows: List[QuestionnaireRow],
        results: List[MatchResult]
    ) -> str:
        """
        Generate output CSV with original data plus answers, confidence, and evidence.

        Returns:
            CSV content as string
        """
        # Create output DataFrame
        output_data = []

        # Create a mapping of row_number to result
        result_map = {row.row_number: (row, result) for row, result in zip(rows, results)}

        for idx, orig_row in original_df.iterrows():
            row_data = orig_row.to_dict()

            if idx in result_map:
                questionnaire_row, match_result = result_map[idx]

                if match_result.matched_entry:
                    row_data['Answer'] = match_result.matched_entry.answer
                    row_data['Confidence Score'] = match_result.confidence_score
                    row_data['Confidence Level'] = match_result.confidence_level
                    row_data['Evidence'] = match_result.evidence
                else:
                    row_data['Answer'] = ""
                    row_data['Confidence Score'] = 0
                    row_data['Confidence Level'] = "Insufficient"
                    row_data['Evidence'] = ""
            else:
                # Row didn't have a valid question
                row_data['Answer'] = ""
                row_data['Confidence Score'] = ""
                row_data['Confidence Level'] = ""
                row_data['Evidence'] = ""

            output_data.append(row_data)

        output_df = pd.DataFrame(output_data)

        # Ensure column order: original columns + new columns
        new_columns = ['Answer', 'Confidence Score', 'Confidence Level', 'Evidence']
        column_order = self.original_columns + [c for c in new_columns if c not in self.original_columns]
        output_df = output_df.reindex(columns=column_order)

        # Generate CSV string
        output = io.StringIO()
        output_df.to_csv(output, index=False)
        return output.getvalue()

    def generate_summary_output(
        self,
        rows: List[QuestionnaireRow],
        results: List[MatchResult]
    ) -> str:
        """
        Generate a simplified output CSV with just questions, answers, confidence, and evidence.

        Returns:
            CSV content as string
        """
        output_data = []

        for row, result in zip(rows, results):
            row_data = {
                'Question': row.question,
                'Answer': result.matched_entry.answer if result.matched_entry else "",
                'Confidence Score': result.confidence_score,
                'Confidence Level': result.confidence_level,
                'Evidence': result.evidence
            }
            output_data.append(row_data)

        output_df = pd.DataFrame(output_data)

        output = io.StringIO()
        output_df.to_csv(output, index=False)
        return output.getvalue()
