"""Retriever factory: the deployed variant comes from agent/config.yaml (rag.variant), which is
set from evals/results/rag_variants.json, never by default."""

from __future__ import annotations

import asyncio
import importlib
import threading

from agent.settings import config
from rag.index.store import EvidenceIndex
from rag.ingest.loaders import load_persona
from rag.types import Doc
from rag.variants.base import PipelineConfig, Query, Retriever

VARIANTS = [
    "v0_naive", "v1_decompose", "v2_hybrid", "v3_rerank", "v4_outcome",
    "v5_multivector", "v6_contextual", "v7_hyde", "v8_corrective",
]

_indexes: dict[tuple, EvidenceIndex] = {}
_extra_docs: dict[tuple[str, str], list[Doc]] = {}  # (tenant, persona) -> uploads
_lock = threading.Lock()


def pipeline(name: str | None = None) -> PipelineConfig:
    name = name or config()["rag"]["variant"]
    return importlib.import_module(f"rag.variants.{name}").PIPELINE


def _key(persona_id: str, cfg: PipelineConfig, tenant: str, embed_model: str | None) -> tuple:
    return (tenant, persona_id, cfg.scheme, cfg.contextual, embed_model)


async def aget_index(persona_id: str, cfg: PipelineConfig, tenant: str = "public",
                     embed_model: str | None = None) -> EvidenceIndex:
    key = _key(persona_id, cfg, tenant, embed_model)
    if key in _indexes:
        return _indexes[key]
    docs = load_persona(persona_id) + _extra_docs.get((tenant, persona_id), [])
    rag = config()["rag"]
    contextual = None
    if cfg.contextual:
        from rag.ingest.chunking import structured_chunks
        from rag.variants.llm_steps import contextual_lines

        contextual = {}
        for d in docs:
            contextual |= await contextual_lines(d, structured_chunks(d, rag["chunk_size"], multivector=True))
    idx = await asyncio.to_thread(
        EvidenceIndex.build, persona_id, docs, cfg.scheme, rag["chunk_size"], rag["chunk_overlap"],
        embed_model, contextual,
    )
    with _lock:
        _indexes[key] = idx
    return idx


def get_index(persona_id: str, cfg: PipelineConfig, tenant: str = "public", embed_model: str | None = None) -> EvidenceIndex:
    key = _key(persona_id, cfg, tenant, embed_model)
    if key not in _indexes:
        asyncio.run(aget_index(persona_id, cfg, tenant, embed_model))
    return _indexes[key]


async def aget_retriever(persona_id: str, variant: str | None = None, tenant: str = "public",
                         embed_model: str | None = None) -> Retriever:
    cfg = pipeline(variant)
    return Retriever(cfg, await aget_index(persona_id, cfg, tenant, embed_model))


def add_user_docs(tenant: str, persona_id: str, docs: list[Doc]) -> int:
    """Incremental re-index: new uploads are added to every cached index for this tenant."""
    _extra_docs.setdefault((tenant, persona_id), []).extend(docs)
    added = 0
    for (t, p, scheme, _ctx, _m), idx in list(_indexes.items()):
        if t == tenant and p == persona_id:
            added += idx.add_docs(docs, scheme)
    return added


async def search(persona_id: str, text: str, requirements: list[str] | None = None, k: int | None = None,
                 variant: str | None = None, filters: dict | None = None, tenant: str = "public"):
    r = await aget_retriever(persona_id, variant, tenant)
    return await r.aretrieve(Query(persona_id, text, requirements or [], k or config()["rag"]["k"], filters))
