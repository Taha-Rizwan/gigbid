"""FastAPI entry point for the contract QA assistant.

The endpoint receives a natural‑language question, runs the RAG pipeline
defined in ``search.py`` and ``rerank.py``, and returns the best clause
together with its source citation.
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .search import first_stage_retrieval
from .rerank import rerank_candidates

app = FastAPI(title="Contract QA Assistant")


class QuestionRequest(BaseModel):
    question: str


class AnswerResponse(BaseModel):
    answer: str
    citation: str
    score: float


@app.post("/answer", response_model=AnswerResponse)
async def answer_question(req: QuestionRequest) -> AnswerResponse:
    """Process a single question and return the top answer."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Empty question")

    # 1️⃣ First‑stage retrieval (BM25 + vector)
    candidates = first_stage_retrieval(req.question, top_k=20)

    if not candidates:
        raise HTTPException(status_code=404, detail="No relevant clauses found")

    # 2️⃣ Re‑rank with cross‑encoder
    ranked = rerank_candidates(req.question, candidates, top_k=1)

    top = ranked[0]
    return AnswerResponse(
        answer=top["text"],
        citation=f"{top['doc_id']}#clause-{top['clause_id']}",
        score=top["score"],
    )
