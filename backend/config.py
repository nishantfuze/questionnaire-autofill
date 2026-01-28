"""Configuration settings for the questionnaire autofill backend."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT

# Knowledge base files to load
KNOWLEDGE_BASE_FILES = [
    "Questions_for_bidder_Questions.csv",
    "Trading_Vendor_Questions_IT_Questions.csv",
    "rbgplatformquestionnaire_questionnaire.csv",
    "TPRMDueDiligenceResidualRiskTemplate_Due_Dilgence_Template.csv",
    "TPRMDueDiligenceResidualRiskTemplate_KYTP.csv",
]

# TF-IDF settings
MIN_DF = 1
MAX_DF = 0.95
NGRAM_RANGE = (1, 2)

# Confidence score thresholds
CONFIDENCE_HIGH = 90
CONFIDENCE_MEDIUM = 70
CONFIDENCE_LOW = 40

# Domain keywords for bonus scoring
DOMAIN_KEYWORDS = [
    "kyc", "aml", "compliance", "regulatory", "security", "api", "encryption",
    "authentication", "authorization", "custody", "wallet", "blockchain",
    "crypto", "trading", "settlement", "audit", "risk", "gdpr", "pii",
    "integration", "sso", "mfa", "rbac", "backup", "disaster recovery",
]

# Abbreviation expansions
ABBREVIATIONS = {
    "kyc": "know your customer",
    "aml": "anti money laundering",
    "cft": "counter financing of terrorism",
    "pii": "personally identifiable information",
    "gdpr": "general data protection regulation",
    "sso": "single sign on",
    "mfa": "multi factor authentication",
    "rbac": "role based access control",
    "api": "application programming interface",
    "sdk": "software development kit",
    "saas": "software as a service",
    "vapt": "vulnerability assessment penetration testing",
    "siem": "security information event management",
    "ids": "intrusion detection system",
    "ips": "intrusion prevention system",
    "tls": "transport layer security",
    "jwt": "json web token",
    "oauth": "open authorization",
    "rest": "representational state transfer",
    "bcp": "business continuity planning",
    "dr": "disaster recovery",
    "rpo": "recovery point objective",
    "rto": "recovery time objective",
    "hsm": "hardware security module",
    "mpc": "multi party computation",
}

# Server settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# LLM settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5.1")
LLM_MAX_TOKENS = 1024
LLM_TEMPERATURE = 0.0  # Deterministic for consistency

# RAG settings
TOP_K_EVIDENCE = 5  # Number of evidence snippets to retrieve
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"  # Toggle LLM vs simple matching
