"""V7: HyDE: retrieve with a hypothetical ideal proposal for the job."""

from rag.variants.base import PipelineConfig

PIPELINE = PipelineConfig("v7_hyde", hybrid=True, hyde=True)
