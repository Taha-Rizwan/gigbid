"""
Simple drift monitoring using Evidently.

For each incoming request the raw feature dict is stored as a JSON line.
Periodically (or on demand) the stored data is compared against a reference
dataset (the training data) and a drift score is computed.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
from evidently.dashboard import Dashboard
from evidently.tabs import DataDriftTab

from .config import LOG_DIR, DRIFT_THRESHOLD

logger = logging.getLogger(__name__)

# Path to the file that accumulates request payloads
REQUEST_LOG = LOG_DIR / "requests.jsonl"

# Path to the reference dataset (should be a CSV exported from the training pipeline)
REFERENCE_DATA = LOG_DIR / "reference.csv"


def log_request(payload: Dict[str, Any]) -> None:
    """
    Append a single request payload to the JSON‑lines log.
    """
    with REQUEST_LOG.open("a", encoding="utf-8") as f:
        json.dump(payload, f)
        f.write("\n")


def _load_requests() -> pd.DataFrame:
    """
    Load all logged request payloads into a DataFrame.
    """
    if not REQUEST_LOG.exists():
        return pd.DataFrame()
    records = []
    with REQUEST_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return pd.DataFrame(records)


def compute_drift() -> float:
    """
    Compute a simple drift metric (Evidently's data drift score) between the
    reference data and the logged requests. Returns a float in [0, 1].
    """
    if not REFERENCE_DATA.exists():
        logger.warning("Reference data not found; cannot compute drift.")
        return 0.0

    reference = pd.read_csv(REFERENCE_DATA)
    current = _load_requests()
    if current.empty:
        logger.info("No new requests to compare; drift is 0.")
        return 0.0

    dashboard = Dashboard(tabs=[DataDriftTab])
    dashboard.calculate(reference, current)
    # Evidently stores the overall drift score in the tab's metric dict
    drift_score = dashboard.tabs[0].metric["drift_score"]
    return drift_score


def check_and_alert() -> None:
    """
    Compute drift and log an alert if the score exceeds DRIFT_THRESHOLD.
    """
    score = compute_drift()
    if score > DRIFT_THRESHOLD:
        logger.warning(
            f"Data drift detected! Score={score:.3f} exceeds threshold={DRIFT_THRESHOLD}"
        )
    else:
        logger.info(f"Drift score {score:.3f} within acceptable limits.")
