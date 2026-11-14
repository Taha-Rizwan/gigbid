import os
from pathlib import Path

class Config:
    """Configuration loaded from environment variables."""
    # Model artefacts
    MODEL_PATH: Path = Path(os.getenv("MODEL_PATH", "models/ticket_router.onnx"))
    # Celery broker / backend
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    # Batch size for inference
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "32"))
    # Minimum confidence to accept a routing decision
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
