# scoring‑service

A lightweight production‑ready service for serving credit‑scoring models.  
It demonstrates how to:

* version and promote models with **MLflow**  
* expose a prediction endpoint via **FastAPI**  
* detect data drift on incoming applications using **Evidently**  
* run continuously in Docker with CI/CD via GitHub Actions (not included in the repo)

## Architecture (high level)

1. **Model registry** – models are stored in an MLflow tracking server.  
2. **FastAPI** – `/predict` returns a score, `/promote` switches the active model.  
3. **Drift monitor** – each request is logged; Evidently computes drift statistics and triggers an alert (logged to stdout) when drift exceeds a configurable threshold.  

## Setup

```bash
# clone the repo
git clone <repo-url>
cd scoring-service

# create a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# install dependencies
pip install -r requirements.txt

# set required environment variables
export MLFLOW_TRACKING_URI=http://localhost:5000
export ACTIVE_MODEL_STAGE=Staging   # or Production
export DRIFT_THRESHOLD=0.15
```

## Running locally

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

* `POST /predict` – JSON body with applicant features, returns a credit score.  
* `POST /promote` – JSON body `{ "model_name": "...", "version": <int> }` promotes the specified version to the active stage.

## Testing

```bash
pytest tests/
```

## Docker

A minimal `Dockerfile` is provided. Build and run:

```bash
docker build -t scoring-service .
docker run -e MLFLOW_TRACKING_URI=... -e DRIFT_THRESHOLD=0.15 -p 8000:8000 scoring-service
```

---  

*Note*: The client is referenced only as “a legal‑tech client” to keep confidentiality.
