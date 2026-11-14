"""V4: Outcome-aware ranking: boost evidence from proposals that won or got replies."""

from rag.variants.base import PipelineConfig

PIPELINE = PipelineConfig("v4_outcome", decompose=True, hybrid=True, rerank=True, outcome=True)
