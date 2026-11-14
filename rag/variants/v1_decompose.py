"""V1: Requirement decomposition: one retrieval per extracted requirement, then merge (RRF)."""

from rag.variants.base import PipelineConfig

PIPELINE = PipelineConfig("v1_decompose", decompose=True)
