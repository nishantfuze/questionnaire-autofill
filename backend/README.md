# Bank Questionnaire Autofill Agent - Backend

A Python + FastAPI backend service that processes uploaded questionnaires against a knowledge base and returns filled CSVs with confidence scores and evidence citations.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload

# Or run directly
python main.py
```

The server will start at `http://localhost:8000`.

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### Knowledge Base Stats
```bash
curl http://localhost:8000/api/v1/knowledge-base/stats
```

### Fill Questionnaire (Streaming)
```bash
curl -X POST http://localhost:8000/api/v1/questionnaire/fill \
  -F "file=@../RFP_Queries_-_test_Table.csv"
```

Response format:
```
{"state": "processing", "progress": 10, "message": "Parsing input file..."}
{"state": "processing", "progress": 50, "message": "Matching question 5/10..."}
{"state": "ready", "progress": 100, "message": "Ready to download.", "output_filename": "filled_questionnaire.csv"}
---CSV---
Question,Answer,Confidence Score,Evidence
"What is your KYC process?","Fuze follows...",92,"[Questions_for_bidder > Regulatory > Row 23]"
```

### Fill Questionnaire (JSON)
```bash
curl -X POST http://localhost:8000/api/v1/questionnaire/fill-json \
  -F "file=@../RFP_Queries_-_test_Table.csv"
```

Returns a JSON object with all results.

## Architecture

```
backend/
├── main.py                    # FastAPI app + startup
├── config.py                  # Configuration
├── models.py                  # Pydantic schemas
├── services/
│   ├── knowledge_index.py     # Knowledge base indexing (TF-IDF)
│   ├── text_matcher.py        # Question matching
│   ├── csv_processor.py       # CSV parsing/generation
│   └── confidence_scorer.py   # Scoring logic
├── requirements.txt
└── README.md
```

## Confidence Scoring

- **High (90-100)**: Strong match, can be used directly
- **Medium (70-89)**: Good match, review recommended
- **Low (40-69)**: Weak match, manual verification needed
- **Insufficient (0-39)**: No reliable match found

Scoring factors:
- Base: TF-IDF cosine similarity (0-100)
- +5: Domain keyword match
- -10: Answer too short (<50 chars)
- -5: Ambiguous match (top 2 scores similar)
- +5: Answer contains question terms

## Knowledge Base Files

The system automatically loads these CSV files from the parent directory:
- `Questions_for_bidder_Questions.csv`
- `Trading_Vendor_Questions_IT_Questions.csv`
- `rbgplatformquestionnaire_questionnaire.csv`
- `TPRMDueDiligenceResidualRiskTemplate_Due_Dilgence_Template.csv`
- `TPRMDueDiligenceResidualRiskTemplate_KYTP.csv`
