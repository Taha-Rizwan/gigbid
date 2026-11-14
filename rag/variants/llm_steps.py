"""LLM-backed retrieval steps: HyDE (V7) and contextual chunk lines (V6). Cached on disk."""

from __future__ import annotations

import hashlib
import json

from langchain_core.messages import HumanMessage

from agent import llm
from agent.settings import ROOT
from rag.types import Chunk, Doc

CACHE_DIR = ROOT / "data" / "cache" / "rag_llm"


def _cached(kind: str, key: str):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{kind}-{hashlib.sha256(key.encode()).hexdigest()[:32]}.json"
    return path, (json.loads(path.read_text(encoding="utf-8")) if path.exists() else None)


async def hyde_text(job_text: str) -> str:
    path, hit = _cached("hyde", job_text)
    if hit:
        return hit
    out = await llm.text(
        "fit_matcher",
        llm.prompt_messages("hyde", f"<job_post>\n{job_text[:3000]}\n</job_post>"),
    )
    path.write_text(json.dumps(out), encoding="utf-8")
    return out


async def contextual_lines(doc: Doc, chunks: list[Chunk]) -> dict[str, str]:
    """One short line situating each chunk within its source document (Anthropic-style)."""
    out: dict[str, str] = {}
    for c in chunks:
        path, hit = _cached("ctx", f"{doc.evidence_id}|{c.text}")
        if hit is None:
            hit = await llm.text(
                "fit_matcher",
                llm.prompt_messages(
                    "contextual_chunk",
                    f"<document title=\"{doc.title}\">\n{doc.text[:6000]}\n</document>\n<chunk>\n{c.text}\n</chunk>",
                ),
            )
            hit = " ".join(hit.split())[:300]
            path.write_text(json.dumps(hit), encoding="utf-8")
        out[c.chunk_id] = hit
    return out
