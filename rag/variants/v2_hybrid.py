"""V2: Hybrid BM25 + dense with reciprocal rank fusion; exact tool names survive."""

from rag.variants.base import PipelineConfig

PIPELINE = PipelineConfig("v2_hybrid", hybrid=True)
