"""V6: Contextual retrieval: a generated context line prepended to each chunk."""

from rag.variants.base import PipelineConfig

PIPELINE = PipelineConfig("v6_contextual", scheme="multivector", hybrid=True, contextual=True)
