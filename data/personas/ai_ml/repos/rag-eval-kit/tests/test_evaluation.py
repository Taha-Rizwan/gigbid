"""Integration test that evaluates the assistant against a static answer key."""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

# Path to the (synthetic) answer key – 120 entries of the form
# {"question": "...", "answer": "...", "citation": "..."}
ANSWER_KEY_PATH = Path(__file__).parent.parent / "data" / "answers.json"


def load_answer_key():
    with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("entry", load_answer_key())
def test_question(entry):
    """Run a single question through the API and record success metrics."""
    resp = client.post("/answer", json={"question": entry["question"]})
    assert resp.status_code == 200, f"API error: {resp.text}"
    data = resp.json()

    # Exact‑match on answer text (ignoring case & surrounding whitespace)
    answer_match = data["answer"].strip().lower() == entry["answer"].strip().lower()

    # Citation must be present and non‑empty
    citation_ok = bool(data["citation"])

    # Store results on the request object for later aggregation
    entry["__result"] = {
        "answer_match": answer_match,
        "citation_ok": citation_ok,
    }


def test_aggregate_results():
    """After all per‑question tests have run, compute overall metrics."""
    key = load_answer_key()
    total = len(key)
    correct = sum(1 for e in key if e.get("__result", {}).get("answer_match"))
    cited = sum(1 for e in key if e.get("__result", {}).get("citation_ok"))

    accuracy = correct / total * 100
    unsupported = (total - cited) / total * 100

    print(f"\nAccuracy: {accuracy:.1f}%")
    print(f"Unsupported citations: {unsupported:.1f}%")

    # Simple assertions mirroring the project claim
    assert accuracy >= 85.0, "Accuracy fell below expected threshold"
    assert unsupported < 1.0, "Too many answers without citations"
