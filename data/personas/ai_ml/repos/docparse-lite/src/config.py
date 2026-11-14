"""
Configuration handling for docparse‑lite.
All sensitive values are read from environment variables.
"""

import os
from pathlib import Path

# Directory containing input PDFs
INPUT_DIR = Path(os.getenv("DP_INPUT_DIR", "data/input"))

# Directory where processed PDFs are moved after successful extraction
PROCESSED_DIR = Path(os.getenv("DP_PROCESSED_DIR", "data/processed"))

# Directory for PDFs that need manual review
REVIEW_DIR = Path(os.getenv("DP_REVIEW_DIR", "data/review"))

# OpenAI API key – must be set in the environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Minimum confidence (0‑1) required to accept a field automatically
CONFIDENCE_THRESHOLD = float(os.getenv("DP_CONFIDENCE_THRESHOLD", "0.85"))

# Ensure directories exist
for _dir in (INPUT_DIR, PROCESSED_DIR, REVIEW_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
