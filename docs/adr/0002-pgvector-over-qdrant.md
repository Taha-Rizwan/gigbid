# ADR 0002: pgvector in the app's Postgres instead of a separate vector database

- Status: accepted, partly implemented (see Consequences)
- Plan reference: D22 in `PLAN.md`

## Context

The brief requires "one vector store". The corpus is small: three personas with a few hundred
evidence items each, chunked into a few thousand chunks. Tenant isolation (E4) has to hold on every
query. Hosting is free-tier only: one Hugging Face Space plus Neon Postgres (ADR 0007).

## Decision

Use `pgvector` inside the same Postgres that holds the checkpointer and store.

- `rag/index/store.py` `PgVectorStore` defines `evidence_chunks` with a
  `(tenant_id, chunk_id)` primary key and a `vector(384)` column (the dimension of
  `bge-small-en-v1.5`), and queries with `where tenant_id=%s and persona_id=%s order by embedding <=> %s`.
- BM25 for the hybrid variant uses the `bm25s` library in memory (`EvidenceIndex.sparse`).
- Compose and CI use the `pgvector/pgvector:pg16` image. Neon supports the extension.

## Alternatives rejected

- **Qdrant.** A good engine, but an extra container and service to host on a single free Space.
- **Chroma.** Weaker multi-tenancy and persistence story.
- **Pinecone.** Paid and external. Data would leave the stack.
- **Postgres full-text search for the sparse side.** `ts_rank` is not BM25, and V2 is meant to test
  exact keyword matching.

## Consequences

- One fewer service. Tenant filters and metadata filters are plain SQL.
- **As built, the request path does not use `PgVectorStore`.** `rag/retriever.py` builds an
  in-process `EvidenceIndex` (numpy matrix + BM25) per (tenant, persona, chunking scheme) on first
  use, from the persona files on disk. This is fast for a corpus of this size, but the index is
  rebuilt on every process start, and uploaded items are not indexed (see
  `docs/ARCHITECTURE.md` §11). Wiring `PgVectorStore.upsert` / `dense` into `EvidenceIndex` is the
  remaining step.
- Embeddings are cached on disk (`data/cache/embeddings.sqlite`), and the image bakes in the
  models, so the rebuild costs only CPU time.
