"""
FastAPI entry point for the credit‑scoring service.

Endpoints:
* POST /predict – returns a credit score for the supplied applicant data.
* POST /promote – promotes a specific model version to the active stage.
* GET /health – simple health check.
"""

import logging
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from .model_manager import get_latest_model_uri, load_model, promote_model
from .drift_monitor import log_request, check_and_alert

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scoring-service")

app = FastAPI(title="Credit Scoring Service")


class PredictRequest(BaseModel):
    # Example fields; real models may require more
    age: int
    income: float
    credit_history_years: int
    existing_debt: float
    employment_status: str


class PromoteRequest(BaseModel):
    model_name: str
    version: int


# Cache the loaded model to avoid re‑loading on every request
_current_model = None
_current_model_name = "credit_scoring_model"


def _load_active_model():
    global _current_model
    uri = get_latest_model_uri(_current_model_name)
    if uri is None:
        raise RuntimeError("No active model found in the registry.")
    _current_model = load_model(uri)


@app.on_event("startup")
def startup_event():
    logger.info("Starting scoring service – loading active model.")
    try:
        _load_active_model()
        logger.info("Model loaded successfully.")
    except Exception as exc:
        logger.error(f"Failed to load model: {exc}")
        raise


@app.post("/predict")
async def predict(request: PredictRequest):
    """
    Return a credit score for the supplied applicant data.
    The request payload is also logged for drift monitoring.
    """
    payload = request.dict()
    log_request(payload)

    if _current_model is None:
        raise HTTPException(status_code=503, detail="Model not available")

    # The model expects a DataFrame with a single row
    import pandas as pd

    df = pd.DataFrame([payload])
    try:
        # Assume the model returns a single float score
        score = _current_model.predict(df)[0]
    except Exception as exc:
        logger.exception("Model prediction failed")
        raise HTTPException(status_code=500, detail=str(exc))

    # After each prediction we optionally check drift (could be throttled)
    check_and_alert()

    return {"score": float(score)}


@app.post("/promote")
async def promote(req: PromoteRequest):
    """
    Promote a specific model version to the active stage.
    """
    success = promote_model(req.model_name, req.version)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to promote {req.model_name} version {req.version}",
        )
    # Reload the newly promoted model
    try:
        _load_active_model()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Promotion succeeded but model reload failed: {exc}",
        )
    return {"status": "promoted", "model": req.model_name, "version": req.version}


@app.get("/health")
def health():
    """Simple health check."""
    return {"status": "ok"}


if __name__ == "__main__":
    # Run with: uvicorn src.main:app --host 0.0.0.0 --port 8000
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=False)
