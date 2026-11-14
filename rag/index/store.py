"""Evidence index: dense (in-memory numpy or pgvector) + BM25, scoped per tenant and persona."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import bm25s
import numpy as np

from rag.index.embeddings import embed
from rag.ingest.chunking import fixed_chunks, structured_chunks
from rag.types import Chunk, Doc

_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")


def tokenize(text: str) -> list[str]:
    return [t.strip(".-") for t in _TOKEN.findall(text.lower()) if len(t.strip(".-")) > 1]


@dataclass
class EvidenceIndex:
    """All chunks of one persona's corpus, under one chunking scheme."""

    persona_id: str
    docs: dict[str, Doc]
    chunks: list[Chunk]
    embed_model: str | None = None
    matrix: np.ndarray | None = None
    _bm25: bm25s.BM25 | None = field(default=None, repr=False)

    @classmethod
    def build(cls, persona_id: str, docs: list[Doc], scheme: str = "structured",
              chunk_size: int = 600, overlap: int = 80, embed_model: str | None = None,
              contextual: dict[str, str] | None = None) -> EvidenceIndex:
        chunks: list[Chunk] = []
        for d in docs:
            if scheme == "fixed":
                chunks += fixed_chunks(d, chunk_size, overlap)
            else:
                chunks += structured_chunks(d, chunk_size, multivector=scheme == "multivector")
        if contextual:
            for c in chunks:
                c.context = contextual.get(c.chunk_id, "")
        idx = cls(persona_id, {d.evidence_id: d for d in docs}, chunks, embed_model)
        idx.refresh()
        return idx

    def refresh(self) -> None:
        self.matrix = embed([c.embed_text for c in self.chunks], self.embed_model)
        corpus = [tokenize(c.embed_text) for c in self.chunks]
        self._bm25 = bm25s.BM25()
        self._bm25.index(corpus, show_progress=False)

    def add_docs(self, docs: list[Doc], scheme: str = "multivector") -> int:
        """Incremental re-indexing when the user adds work in the UI."""
        new = []
        for d in docs:
            self.docs[d.evidence_id] = d
            new += fixed_chunks(d) if scheme == "fixed" else structured_chunks(d, multivector=scheme == "multivector")
        self.chunks += new
        self.refresh()
        return len(new)

    def _mask(self, filters: dict | None) -> np.ndarray:
        mask = np.ones(len(self.chunks), dtype=bool)
        if not filters:
            return mask
        for i, c in enumerate(self.chunks):
            d = self.docs[c.evidence_id]
            if (t := filters.get("types")) and d.type not in t:
                mask[i] = False
            if (o := filters.get("outcomes")) and d.type == "proposal" and d.outcome not in o:
                mask[i] = False
            if (s := filters.get("since")) and d.date and str(d.date) < s:
                mask[i] = False
        return mask

    def dense(self, query: str, k: int, filters: dict | None = None) -> list[tuple[Chunk, float]]:
        q = embed([query], self.embed_model, query=True)[0]
        scores = self.matrix @ q
        scores[~self._mask(filters)] = -np.inf
        top = np.argsort(-scores)[:k]
        return [(self.chunks[i], float(scores[i])) for i in top if np.isfinite(scores[i])]

    def sparse(self, query: str, k: int, filters: dict | None = None) -> list[tuple[Chunk, float]]:
        toks = tokenize(query)
        if not toks:
            return []
        scores = np.asarray(self._bm25.get_scores(toks), dtype=np.float32)
        scores[~self._mask(filters)] = -np.inf
        top = np.argsort(-scores)[:k]
        return [(self.chunks[i], float(scores[i])) for i in top if np.isfinite(scores[i]) and scores[i] > 0]


class PgVectorStore:
    """Persistent chunk store in Postgres + pgvector, scoped by tenant. Used in deployment so
    uploads survive restarts and every query filters on tenant_id."""

    DDL = """
    create extension if not exists vector;
    create table if not exists evidence_chunks (
      tenant_id text not null, persona_id text not null, chunk_id text not null,
      evidence_id text not null, kind text, text text not null, meta jsonb,
      doc jsonb, embedding vector(%d), primary key (tenant_id, chunk_id));
    create index if not exists evidence_chunks_tp on evidence_chunks (tenant_id, persona_id);
    """

    def __init__(self, dsn: str, dim: int = 384):
        self.dsn, self.dim = dsn, dim

    def _conn(self):
        import psycopg
        from pgvector.psycopg import register_vector

        con = psycopg.connect(self.dsn, autocommit=True)
        register_vector(con)
        return con

    def migrate(self) -> None:
        with self._conn() as con:
            con.execute(self.DDL % self.dim)

    def upsert(self, tenant_id: str, index: EvidenceIndex, chunk_ids: set[str] | None = None) -> int:
        rows = [
            (tenant_id, c.persona_id, c.chunk_id, c.evidence_id, c.kind, c.text, json.dumps(c.meta),
             json.dumps(index.docs[c.evidence_id].__dict__, default=str), index.matrix[i])
            for i, c in enumerate(index.chunks)
            if chunk_ids is None or c.chunk_id in chunk_ids
        ]
        with self._conn() as con, con.cursor() as cur:
            cur.executemany(
                """insert into evidence_chunks values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   on conflict (tenant_id, chunk_id) do update set text=excluded.text,
                   embedding=excluded.embedding, meta=excluded.meta, doc=excluded.doc""",
                rows,
            )
        return len(rows)

    def load_docs(self, tenant_id: str, persona_id: str) -> list[Doc]:
        with self._conn() as con:
            rows = con.execute(
                "select distinct on (evidence_id) doc from evidence_chunks where tenant_id=%s and persona_id=%s",
                (tenant_id, persona_id),
            ).fetchall()
        return [Doc(**r[0]) for r in rows]

    def dense(self, tenant_id: str, persona_id: str, qvec: np.ndarray, k: int) -> list[tuple[str, str, float]]:
        with self._conn() as con:
            rows = con.execute(
                """select chunk_id, evidence_id, 1 - (embedding <=> %s) as score from evidence_chunks
                   where tenant_id=%s and persona_id=%s order by embedding <=> %s limit %s""",
                (qvec, tenant_id, persona_id, qvec, k),
            ).fetchall()
        return [(r[0], r[1], float(r[2])) for r in rows]
