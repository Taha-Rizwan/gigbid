"""V0: Naive dense baseline: fixed chunks, top-k cosine on the whole job post."""

from rag.variants.base import PipelineConfig

PIPELINE = PipelineConfig("v0_naive", scheme="fixed")
