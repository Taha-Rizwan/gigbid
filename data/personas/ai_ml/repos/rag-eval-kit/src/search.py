"""First‑stage retrieval utilities.

Provides a blended BM25 + Pinecone vector search.  The BM25 index lives in a
SQLite table ``clauses`` with columns (doc_id TEXT, clause_id INTEGER,
text TEXT, bm25_vector BLOB).  Vector embeddings are stored in Pinecone.
"""

import os
import sqlite3
from typing import List, Dict

import pinecone
import openai

# Initialise Pinecone client once
pinecone.init(api_key=os.getenv("PINECONE_API_KEY"), environment="us-west1-gcp")
index = pinecone.Index(os.getenv("PINECONE_INDEX"))


def _embed(text: str) -> List[float]:
    """Return OpenAI embedding for *text*."""
    resp = openai.Embedding.create(
        model="text-embedding-ada-002", input=text
    )
    return resp["data"][0]["embedding"]


def _bm25_search(query: str, conn: sqlite3.Connection, top_k: int) -> List[Dict]:
    """Simple BM25 search using SQLite FTS5."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT doc_id, clause_id, text, bm25(clauses) AS score
        FROM clauses
        WHERE clauses MATCH ?
        ORDER BY score LIMIT ?
        """,
        (query, top_k),
    )
    rows = cur.fetchall()
    return [
        {"doc_id": r[0], "clause_id": r[1], "text": r[2], "score": -r[3]}
        for r in rows
    ]


def _vector_search(query: str, top_k: int) -> List[Dict]:
    """Search Pinecone for nearest neighbours of the query embedding."""
    embed = _embed(query)
    results = index.query(vector=embed, top_k=top_k, include_metadata=True)
    hits = []
    for match in results.matches:
        meta = match.metadata
        hits.append(
            {
                "doc_id": meta["doc_id"],
                "clause_id": meta["clause_id"],
                "text": meta["text"],
                "score": match.score,
            }
        )
    return hits


def first_stage_retrieval(query: str, top_k: int = 20) -> List[Dict]:
    """Blend BM25 and vector results, deduplicate, and return a combined list."""
    # Open a read‑only connection to the local SQLite FTS index
    conn = sqlite3.connect("data/clauses.db")
    bm25_hits = _bm25_search(query, conn, top_k=top_k)
    conn.close()

    vector_hits = _vector_search(query, top_k=top_k)

    # Merge while preserving the best score for each unique clause
    merged: Dict[str, Dict] = {}
    for hit in bm25_hits + vector_hits:
        key = f"{hit['doc_id']}#{hit['clause_id']}"
        if key not in merged or hit["score"] > merged[key]["score"]:
            merged[key] = hit

    # Return sorted list (highest score first)
    return sorted(merged.values(), key=lambda x: x["score"], reverse=True)
