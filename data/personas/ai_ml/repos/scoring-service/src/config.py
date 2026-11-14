"""
Configuration handling for the scoring service.

All values are read from environment variables; defaults are provided for local
development. No secrets are hard‑coded.
"""

import os
from pathlib import Path

# MLflow tracking server URL
MLFLOW_TRACKING_URI: str = os.getenv(
    "MLFLOW_TRACKING_URI", "http://localhost:5000"
)

# Which stage of the model registry is considered the active model.
# Typical values: "Staging", "Production"
ACTIVE_MODEL_STAGE: str = os.getenv("ACTIVE_MODEL_STAGE", "Staging")

# Threshold for Evidently drift detection (0‑1). When the drift score exceeds
# this value an alert is logged.
DRIFT_THRESHOLD: float = float(os.getenv("DRIFT_THRESHOLD", "0.15"))

# Directory where request logs are stored (used by the drift monitor)
LOG_DIR: Path = Path(os.getenv("LOG_DIR", "./logs")).expanduser().resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)
