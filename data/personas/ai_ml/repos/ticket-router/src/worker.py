import os
import json
import logging
from celery import Celery
import redis
from .model import TicketRouterModel
from .config import Config

# Initialise Celery app
app = Celery("ticket_router", broker=Config.REDIS_URL, backend=Config.REDIS_URL)

# Initialise Redis client for storing routing results
redis_client = redis.Redis.from_url(Config.REDIS_URL)

# Load model once per worker process
model = TicketRouterModel()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.task
def route_ticket(ticket_id: str, ticket_text: str) -> None:
    """
    Classify a ticket and store the routing decision in Redis.
    The key is `ticket:{ticket_id}` and the value is a JSON payload:
    {"label": "...", "confidence": ...}
    """
    logger.info("Routing ticket %s", ticket_id)
    label, confidence = model.predict([ticket_text])[0]

    if confidence < Config.CONFIDENCE_THRESHOLD:
        label = "unassigned"
        logger.info(
            "Confidence %.2f below threshold – marking as unassigned",
            confidence,
        )

    payload = json.dumps({"label": label, "confidence": confidence})
    redis_key = f"ticket:{ticket_id}"
    redis_client.set(redis_key, payload)
    logger.info("Stored routing result for %s -> %s (%.2f)", ticket_id, label, confidence)
