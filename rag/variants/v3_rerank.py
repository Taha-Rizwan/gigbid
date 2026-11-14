"""V3: Cross-encoder reranking of the hybrid candidates for precision at small k."""

from rag.variants.base import PipelineConfig

PIPELINE = PipelineConfig("v3_rerank", hybrid=True, rerank=True)
