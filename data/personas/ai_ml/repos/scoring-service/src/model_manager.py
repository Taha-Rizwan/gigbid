"""
Utilities for loading and promoting models from an MLflow model registry.
"""

import mlflow
from mlflow.exceptions import RestException
from typing import Optional
from .config import MLFLOW_TRACKING_URI, ACTIVE_MODEL_STAGE

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)


def get_latest_model_uri(model_name: str) -> Optional[str]:
    """
    Return the URI of the latest model version that is in the configured
    ACTIVE_MODEL_STAGE. If no model is found, None is returned.
    """
    try:
        client = mlflow.tracking.MlflowClient()
        # List all versions for the model
        versions = client.search_model_versions(f"name='{model_name}'")
        # Filter by stage and pick the highest version number
        staged = [
            v for v in versions if v.current_stage == ACTIVE_MODEL_STAGE
        ]
        if not staged:
            return None
        latest = max(staged, key=lambda v: int(v.version))
        return latest.source
    except RestException as e:
        # In production we would log this; here we just return None
        return None


def promote_model(model_name: str, version: int, stage: str = ACTIVE_MODEL_STAGE) -> bool:
    """
    Promote a given model version to the active stage.
    Returns True on success, False otherwise.
    """
    client = mlflow.tracking.MlflowClient()
    try:
        client.transition_model_version_stage(
            name=model_name,
            version=str(version),
            stage=stage,
            archive_existing_versions=True,
        )
        return True
    except RestException:
        return False


def load_model(model_uri: str):
    """
    Load a model from the given MLflow URI using pyfunc.
    """
    return mlflow.pyfunc.load_model(model_uri)
