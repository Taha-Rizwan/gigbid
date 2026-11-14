"""Composable retrieval pipeline. Each variant file is a preset of these switches, so the full
comparison and the one-component-at-a-time ablation run from the same code."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace

from agent.handoffs import EvidenceItem
from agent.settings import config
from rag.index.embeddings import rerank
from rag.index.store import EvidenceIndex
from rag.types import Chunk


@dataclass(frozen=True)
class PipelineConfig:
    name: str
    scheme: str = "structured"   # fixed (V0) | structured | multivector (V5)
    decompose: bool = False      # V1: one retrieval per requirement
    hybrid: bool = False         # V2: BM25 + dense, reciprocal rank fusion
    rerank: bool = False         # V3: cross-encoder
    outcome: bool = False        # V4: boost evidence from proposals that won / got replies
    contextual: bool = False     # V6: generated context line per chunk
    hyde: bool = False           # V7: retrieve with a hypothetical ideal proposal
    corrective: bool = False     # V8: grade, re-query, refuse

    def without(self, **flags) -> PipelineConfig:
        return replace(self, name=f"{self.name}-" + "-".join(k for k, v in flags.items() if not v), **flags)


@dataclass
class Query:
    persona_id: str
    job_text: str
    requirements: list[str] = field(default_factory=list)
    k: int = 5
    filters: dict | None = None


def rrf(lists: list[list[tuple[Chunk, float]]], k: int = 60) -> list[tuple[Chunk, float]]:
    scores: dict[str, float] = defaultdict(float)
    by_id: dict[str, Chunk] = {}
    for lst in lists:
        for rank, (c, _) in enumerate(lst):
            scores[c.chunk_id] += 1.0 / (k + rank + 1)
            by_id[c.chunk_id] = c
    return sorted(((by_id[i], s) for i, s in scores.items()), key=lambda x: -x[1])


def to_items(index: EvidenceIndex, ranked: list[tuple[Chunk, float]], k: int) -> list[EvidenceItem]:
    """Collapse chunks to evidence items (best chunk per item), keep the top k items."""
    best: dict[str, tuple[Chunk, float]] = {}
    for c, s in ranked:
        if c.evidence_id not in best or s > best[c.evidence_id][1]:
            best[c.evidence_id] = (c, s)
    items = sorted(best.values(), key=lambda x: -x[1])[:k]
    out = []
    for c, s in items:
        d = index.docs[c.evidence_id]
        out.append(EvidenceItem(
            evidence_id=d.evidence_id, type=d.type, title=d.title, snippet=c.text[:500],
            source=d.source, project=d.project, date=d.date, outcome=d.outcome, score=round(s, 4),
        ))
    return out


class Retriever:
    def __init__(self, cfg: PipelineConfig, index: EvidenceIndex):
        self.cfg, self.index = cfg, index
        self.rag = config()["rag"]

    def _one(self, text: str, n: int, filters: dict | None) -> list[tuple[Chunk, float]]:
        dense = self.index.dense(text, n, filters)
        if not self.cfg.hybrid:
            return dense
        return rrf([dense, self.index.sparse(text, n, filters)], self.rag["rrf_k"])

    def candidates(self, q: Query) -> list[tuple[Chunk, float]]:
        n = self.rag["rerank_candidates"] if self.cfg.rerank else max(q.k * 4, 20)
        if self.cfg.decompose and q.requirements:
            per_req = [self._one(r, n, q.filters) for r in q.requirements]
            # fuse across requirements so every requirement gets a voice in the top k
            return rrf(per_req, self.rag["rrf_k"])
        return self._one(q.job_text, n, q.filters)

    def apply_rerank(self, q: Query, cands: list[tuple[Chunk, float]]) -> list[tuple[Chunk, float]]:
        cands = cands[: self.rag["rerank_candidates"]]
        if self.cfg.decompose and q.requirements:
            # score each candidate against its best-matching requirement
            best: dict[str, float] = {}
            for r in q.requirements:
                for (c, _), s in zip(cands, rerank(r, [c.text for c, _ in cands]), strict=True):
                    best[c.chunk_id] = max(best.get(c.chunk_id, -1e9), s)
            return sorted(((c, best[c.chunk_id]) for c, _ in cands), key=lambda x: -x[1])
        scores = rerank(q.job_text[:2000], [c.text for c, _ in cands])
        return sorted(zip([c for c, _ in cands], scores, strict=True), key=lambda x: -x[1])

    def apply_outcome(self, ranked: list[tuple[Chunk, float]]) -> list[tuple[Chunk, float]]:
        boost = self.rag["outcome_boost"]
        won_text = " ".join(
            d.text.lower() for d in self.index.docs.values() if d.type == "proposal" and d.outcome in ("won", "replied")
        )
        out = []
        scale = max((abs(s) for _, s in ranked), default=1.0) or 1.0
        for c, s in ranked:
            d = self.index.docs[c.evidence_id]
            b = boost.get(d.outcome, 0.0) if d.type == "proposal" else 0.0
            if d.type != "proposal" and d.project and d.project.lower() in won_text:
                b += boost["replied"] / 2  # cited by proposals that worked
            out.append((c, s + b * scale))
        return sorted(out, key=lambda x: -x[1])

    async def aretrieve(self, q: Query) -> list[EvidenceItem]:
        """Async entry point: adds the LLM-backed steps (V7 HyDE, V8 corrective) when enabled."""
        import asyncio

        if self.cfg.hyde:
            from rag.variants.llm_steps import hyde_text

            q = replace(q, job_text=await hyde_text(q.job_text))
        if self.cfg.corrective:
            from rag.variants.v8_corrective import corrective_retrieve

            items, _ = await corrective_retrieve(self, q)
            return items
        return await asyncio.to_thread(self.retrieve, q)

    def retrieve(self, q: Query) -> list[EvidenceItem]:
        ranked = self.candidates(q)
        if self.cfg.rerank:
            ranked = self.apply_rerank(q, ranked)
        if self.cfg.outcome:
            ranked = self.apply_outcome(ranked)
        return to_items(self.index, ranked, q.k)
