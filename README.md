# Bank Questionnaire Autofill Agent

An internal tool that automates filling onboarding questionnaires from regulated banks using a knowledge base of previously completed questionnaires and compliance documents.

## Overview

This tool helps teams respond to bank RFPs, due diligence questionnaires, and compliance assessments by:

1. Building a knowledge index from uploaded internal documents
2. Matching new questions to relevant answers in the knowledge base
3. Generating structured responses with confidence scores and citations

## Features

- **Automated Answer Matching** — Finds the best matching answer from your knowledge base
- **Confidence Scoring** — Each answer includes a confidence score (0-100)
- **Citation Tracking** — Every answer includes source document references
- **TSV Output** — Google Sheets-ready format for easy copy-paste
- **Follow-up Tracking** — Identifies questions that need manual review

## Knowledge Base Documents

| Document | Description |
|----------|-------------|
| `TPRMDueDiligenceResidualRiskTemplate` | Third-Party Risk Management questionnaire (Mashreq) |
| `rbgplatformquestionnaire` | RBG Platform technical questionnaire |
| `Trading_Vendor_Questions_IT` | IT and infrastructure questions |
| `Questions_for_bidder` | Ila Bahrain bidder questionnaire |

## Output Format

Generated responses are saved as TSV files with the following columns:

| Column | Description |
|--------|-------------|
| Question | The original question from the questionnaire |
| Answer | Generated answer from knowledge base |
| Confidence Score | 0-100 rating of answer reliability |
| Evidence | Source citation `[Document > Section > Row]` |

### Confidence Score Guide

| Score | Meaning |
|-------|---------|
| 90-100 | High confidence — explicitly stated in documents |
| 70-89 | Medium confidence — strong match, minor inference |
| 40-69 | Low confidence — partial info, needs confirmation |
| 0-39 | Insufficient — not found in knowledge base |

## Usage

1. Add knowledge documents (CSV/XLSX) to the project folder
2. Provide the blank questionnaire to be filled
3. Run the autofill agent
4. Review the generated TSV output
5. Address any follow-ups flagged by the agent

## Files

```
questionnaire-autofill/
├── README.md
├── .gitignore
├── RFP_Clarifications_Filled.tsv      # Output
├── RFP_Queries_-_test_Table.csv       # Input questionnaire
└── *_*.csv                            # Knowledge base documents
```

## Strict Rules

- Answers are only generated from uploaded knowledge documents
- No hallucination or invented information
- Regulatory/licensing claims are never guessed
- Unanswerable questions are marked as "Insufficient information"

## License

Internal use only.
