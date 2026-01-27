"""FastAPI application for the Bank Questionnaire Autofill Agent."""

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from services.knowledge_index import KnowledgeIndex
from services.text_matcher import TextMatcher
from services.confidence_scorer import ConfidenceScorer
from services.csv_processor import CSVProcessor
from services.llm_generator import LLMGenerator
from models import ProcessingStatus
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global services
knowledge_index: KnowledgeIndex = None
text_matcher: TextMatcher = None
csv_processor: CSVProcessor = None
llm_generator: LLMGenerator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    global knowledge_index, text_matcher, csv_processor, llm_generator

    # Startup: Load knowledge base
    logger.info("Starting application...")
    logger.info("Loading knowledge base...")

    knowledge_index = KnowledgeIndex()
    entries_loaded = knowledge_index.load_all()
    logger.info(f"Knowledge base loaded with {entries_loaded} entries")

    confidence_scorer = ConfidenceScorer()

    # Initialize LLM generator if API key is available
    llm_generator = LLMGenerator()
    if llm_generator.is_available():
        logger.info(f"LLM enabled with model: {config.LLM_MODEL}")
    else:
        logger.warning("LLM not available (no ANTHROPIC_API_KEY). Using simple matching.")

    text_matcher = TextMatcher(knowledge_index, confidence_scorer, llm_generator)
    csv_processor = CSVProcessor()

    logger.info(f"Application startup complete (LLM: {'enabled' if config.USE_LLM and llm_generator.is_available() else 'disabled'})")

    yield

    # Shutdown
    logger.info("Application shutting down...")


app = FastAPI(
    title="Bank Questionnaire Autofill Agent",
    description="API for automatically filling bank questionnaires using a knowledge base",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "knowledge_base_entries": len(knowledge_index.entries) if knowledge_index else 0,
        "llm_enabled": config.USE_LLM and llm_generator is not None and llm_generator.is_available(),
        "llm_model": config.LLM_MODEL if config.USE_LLM else None
    }


@app.get("/api/v1/knowledge-base/stats")
async def knowledge_base_stats():
    """Get statistics about the loaded knowledge base."""
    if not knowledge_index:
        raise HTTPException(status_code=503, detail="Knowledge base not loaded")

    # Count entries by document
    doc_counts = {}
    section_counts = {}

    for entry in knowledge_index.entries:
        doc_counts[entry.document_name] = doc_counts.get(entry.document_name, 0) + 1

        section_key = f"{entry.document_name}:{entry.section}"
        section_counts[section_key] = section_counts.get(section_key, 0) + 1

    return {
        "total_entries": len(knowledge_index.entries),
        "documents": doc_counts,
        "sections_count": len(section_counts),
        "vocabulary_size": len(knowledge_index.vectorizer.vocabulary_) if knowledge_index.vectorizer else 0
    }


async def generate_streaming_response(
    file_content: bytes,
    filename: str
) -> AsyncGenerator[str, None]:
    """Generate streaming response with progress updates and CSV output."""

    def status_line(state: str, progress: int, message: str, output_filename: str = None) -> str:
        status = ProcessingStatus(
            state=state,
            progress=progress,
            message=message,
            output_filename=output_filename
        )
        return json.dumps(status.model_dump(exclude_none=True)) + "\n"

    try:
        # Step 1: Parse input file
        yield status_line("processing", 10, "Parsing input file...")

        try:
            rows, original_df = csv_processor.parse_input(file_content, filename)
        except ValueError as e:
            yield status_line("error", 0, f"Error parsing file: {str(e)}")
            return

        if not rows:
            yield status_line("error", 0, "No valid questions found in the input file")
            return

        yield status_line("processing", 20, f"Found {len(rows)} questions to process")

        # Step 2: Match questions
        results = []
        for i, row in enumerate(rows):
            progress = 20 + int((i / len(rows)) * 60)
            yield status_line("processing", progress, f"Matching question {i + 1}/{len(rows)}...")

            result = text_matcher.match(row.question)
            results.append(result)

        yield status_line("processing", 85, "Generating output file...")

        # Step 3: Generate output CSV
        output_csv = csv_processor.generate_output(original_df, rows, results)

        # Calculate summary stats
        high_conf = sum(1 for r in results if r.confidence_level == "High")
        medium_conf = sum(1 for r in results if r.confidence_level == "Medium")
        low_conf = sum(1 for r in results if r.confidence_level == "Low")
        insufficient = sum(1 for r in results if r.confidence_level == "Insufficient")

        output_filename = filename.replace(".csv", "_filled.csv")

        yield status_line(
            "ready",
            100,
            f"Ready to download. High: {high_conf}, Medium: {medium_conf}, Low: {low_conf}, Insufficient: {insufficient}",
            output_filename
        )

        # Output the CSV after delimiter
        yield "---CSV---\n"
        yield output_csv

    except Exception as e:
        logger.error(f"Error processing file: {e}", exc_info=True)
        yield status_line("error", 0, f"Error processing file: {str(e)}")


@app.post("/api/v1/questionnaire/fill")
async def fill_questionnaire(file: UploadFile = File(...)):
    """
    Fill a questionnaire CSV with answers from the knowledge base.

    Returns a streaming response with:
    - JSON status lines showing progress
    - Delimiter: ---CSV---
    - CSV output with filled answers
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

    return StreamingResponse(
        generate_streaming_response(file_content, file.filename),
        media_type="text/plain",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-cache"
        }
    )


@app.post("/api/v1/questionnaire/fill-json")
async def fill_questionnaire_json(file: UploadFile = File(...)):
    """
    Fill a questionnaire CSV and return JSON response.

    Alternative endpoint for clients that prefer JSON over streaming.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

    try:
        rows, original_df = csv_processor.parse_input(file_content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not rows:
        raise HTTPException(status_code=400, detail="No valid questions found in the input file")

    # Match all questions
    results = []
    match_results = []
    for row in rows:
        result = text_matcher.match(row.question)
        match_results.append(result)
        results.append({
            "question": row.question,
            "answer": result.matched_entry.answer if result.matched_entry else "",
            "confidence_score": result.confidence_score,
            "confidence_level": result.confidence_level,
            "evidence": result.evidence,
            "citations": result.citations,
            "notes": result.notes,
            "similarity_score": round(result.similarity_score, 4)
        })

    # Generate CSV output
    output_csv = csv_processor.generate_output(original_df, rows, match_results)

    return JSONResponse({
        "total_questions": len(rows),
        "results": results,
        "csv_output": output_csv,
        "summary": {
            "high": sum(1 for r in results if r["confidence_level"] == "High"),
            "medium": sum(1 for r in results if r["confidence_level"] == "Medium"),
            "low": sum(1 for r in results if r["confidence_level"] == "Low"),
            "insufficient": sum(1 for r in results if r["confidence_level"] == "Insufficient")
        }
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
