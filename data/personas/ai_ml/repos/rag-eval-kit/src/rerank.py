"""Second‑stage re‑ranking using a cross‑encoder.

The cross‑encoder scores (question, clause) pairs; higher scores indicate
greater relevance.  The model is loaded lazily on first use.
"""

import os
from typing import List, Dict

from sentence_transformers import CrossEncoder

_model: CrossEncoder | None = None


def _load_model() -> CrossEncoder:
    """Load the cross‑encoder model; cached for subsequent calls."""
    global _model
    if _model is None:
        model_name = os.getenv(
            "RERANK_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        _model = CrossEncoder(model_name)
    return _model


def rerank_candidates(
    query: str, candidates: List[Dict], top_k: int = 1
) -> List[Dict]:
    """Return the *top_k* candidates re‑scored by the cross‑encoder."""
    if not candidates:
        return []

    model = _load_model()
    pairs = [(query, cand["text"]) for cand in candidates]
    scores = model.predict(pairs)

    for cand, sc in zip(candidates, scores):
        cand["score"] = sc

    ranked = sorted(candidates, key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]
