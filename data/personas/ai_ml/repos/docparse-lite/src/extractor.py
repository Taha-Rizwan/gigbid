"""
Core extraction logic.
1. Convert PDF pages to images using pdfplumber.
2. Run OCR via Tesseract to obtain raw text.
3. Send the text to OpenAI with a function‑calling schema.
4. Validate the returned JSON against DocumentFields.
5. Return the validated model and a confidence score.
"""

import os
import json
import logging
from pathlib import Path
from typing import Tuple, Optional

import pdfplumber
import pytesseract
import openai
from pydantic import ValidationError

from .schema import DocumentFields
from .config import OPENAI_API_KEY, CONFIDENCE_THRESHOLD

openai.api_key = OPENAI_API_KEY
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def pdf_to_text(pdf_path: Path) -> str:
    """Extract raw text from a PDF using pdfplumber + Tesseract OCR."""
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            # Render page as an image (png bytes) for OCR
            pil_image = page.to_image(resolution=300).original
            ocr_text = pytesseract.image_to_string(pil_image, lang="eng")
            texts.append(ocr_text)
            logger.debug("OCR page %s: %d chars", page_number, len(ocr_text))
    return "\n".join(texts)

def call_llm(text: str) -> Tuple[dict, float]:
    """
    Call OpenAI's function‑calling endpoint.
    Returns a tuple of (parsed JSON dict, confidence).
    Confidence is a simple heuristic: proportion of fields present.
    """
    function_schema = {
        "name": "extract_fields",
        "description": "Extract the 18 required fields from the supplied document text.",
        "parameters": {
            "type": "object",
            "properties": {field: {"type": "string"} for field in DocumentFields.model_fields},
            "required": list(DocumentFields.model_fields.keys()),
        },
    }

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": text}],
        functions=[function_schema],
        function_call={"name": "extract_fields"},
    )
    # Extract function call arguments
    arguments = response["choices"][0]["message"]["function_call"]["arguments"]
    data = json.loads(arguments)

    # Simple confidence: fraction of required fields that are non‑empty strings
    present = sum(1 for v in data.values() if isinstance(v, str) and v.strip())
    confidence = present / len(DocumentFields.model_fields)
    return data, confidence

def extract_document(pdf_path: Path) -> Tuple[Optional[DocumentFields], float]:
    """
    End‑to‑end extraction for a single PDF.
    Returns a validated DocumentFields instance (or None) and the confidence score.
    """
    raw_text = pdf_to_text(pdf_path)
    llm_data, confidence = call_llm(raw_text)

    try:
        validated = DocumentFields(**llm_data)
        return validated, confidence
    except ValidationError as e:
        logger.warning("Validation failed for %s: %s", pdf_path.name, e)
        return None, confidence
