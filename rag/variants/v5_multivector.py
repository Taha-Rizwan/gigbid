"""V5: Multi-vector items: summary, README and code indexed separately, returned as one project."""

from rag.variants.base import PipelineConfig

PIPELINE = PipelineConfig("v5_multivector", scheme="multivector", hybrid=True)
