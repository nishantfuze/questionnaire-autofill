# Bank Questionnaire Autofill Agent

An internal tool that automates filling onboarding questionnaires from regulated banks using a knowledge base of previously completed questionnaires and compliance documents.

## Overview

This tool helps teams respond to bank RFPs, due diligence questionnaires, and compliance assessments by:

1. Building a knowledge index from uploaded internal documents
2. Matching new questions to relevant answers using hybrid AI matching
3. Generating structured responses with confidence scores and citations

## Architecture

```
questionnaire-tool/
├── backend/                    # FastAPI backend (Python)
│   ├── main.py                # API endpoints
│   ├── config.py              # Configuration
│   ├── models.py              # Pydantic schemas
│   └── services/
│       ├── knowledge_index.py  # TF-IDF indexing
│       ├── smart_matcher.py    # Concept-based retrieval
│       ├── hybrid_matcher.py   # SmartMatcher + LLM synthesis
│       ├── llm_generator.py    # OpenAI GPT integration
│       └── csv_processor.py    # CSV parsing/output
├── frontend/                   # Next.js frontend
│   ├── app/page.tsx           # Main UI
│   ├── components/            # React components
│   └── lib/                   # API client utilities
└── *.csv                      # Knowledge base documents
```

## Features

- **Hybrid AI Matching** — Combines concept-based retrieval with LLM synthesis
- **RAG Architecture** — LLM answers ONLY from knowledge base, no hallucination
- **Confidence Scoring** — Each answer includes a confidence score (0-100)
- **Citation Tracking** — Every answer includes source document references
- **Smart Question Detection** — Identifies questions that require human attention
- **Web Interface** — Drag-and-drop CSV upload with real-time progress

## Quick Start

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt

# Create .env file with your OpenAI API key
echo "OPENAI_API_KEY=your-key-here" > .env
echo "USE_LLM=true" >> .env
echo "LLM_MODEL=gpt-5.1" >> .env

# Start server
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev -- -p 3001
```

### 3. Access the Application

- **Frontend**: http://localhost:3001
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Configuration

Environment variables (`.env` file in backend/):

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `USE_LLM` | Enable LLM synthesis | `true` |
| `LLM_MODEL` | OpenAI model to use | `gpt-5.1` |

## Confidence Score Guide

| Score | Level | Meaning |
|-------|-------|---------|
| 90-100 | High | Directly answered from knowledge base |
| 75-89 | Medium | Strong support with minor inference |
| 50-74 | Low | Partial information, needs review |
| 0-49 | Requires Human Attention | Not found or internal question |

## Knowledge Base Documents

| Document | Description |
|----------|-------------|
| `Questions_for_bidder_Questions.csv` | Business/functional Q&A |
| `Trading_Vendor_Questions_IT_Questions.csv` | IT infrastructure Q&A |
| `rbgplatformquestionnaire_questionnaire.csv` | Platform capabilities |
| `TPRMDueDiligenceResidualRiskTemplate_Due_Dilgence_Template.csv` | Risk/compliance Q&A |
| `TPRMDueDiligenceResidualRiskTemplate_KYTP.csv` | KYTP form data |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with LLM status |
| `/api/v1/questionnaire/fill` | POST | Fill questionnaire (streaming) |
| `/api/v1/questionnaire/fill-json` | POST | Fill questionnaire (JSON response) |
| `/api/v1/knowledge-base/stats` | GET | Knowledge base statistics |

## How It Works

1. **Evidence Retrieval**: SmartMatcher uses concept-based ranking to find relevant answers from the knowledge base
2. **LLM Synthesis**: GPT synthesizes a coherent answer from the retrieved evidence
3. **Citation**: Every answer includes citations to source documents
4. **Validation**: Questions about internal matters (e.g., "What SSO does Mashreq use?") are flagged as requiring human attention

## Strict Rules

- Answers are only generated from uploaded knowledge documents
- No hallucination or invented information
- Regulatory/licensing claims are never guessed
- Unanswerable questions are marked as "Requires Human Attention"

## License

Internal use only.
