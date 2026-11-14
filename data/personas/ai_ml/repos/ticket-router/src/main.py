import os
import json
import logging
from pathlib import Path
from celery import group
from .worker import route_ticket
from .config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_pending_tickets() -> list[dict]:
    """
    Dummy loader – in a real system this would poll a message queue or DB.
    Returns a list of dicts with ``id`` and ``text`` keys.
    """
    sample_path = Path(__file__).parent / "sample_tickets.json"
    if not sample_path.exists():
        logger.warning("No sample tickets found; exiting.")
        return []
    with sample_path.open() as f:
        return json.load(f)

def dispatch_tickets(tickets: list[dict]) -> None:
    """
    Submit tickets to Celery workers in batches.
    """
    if not tickets:
        logger.info("No tickets to process.")
        return

    batch = []
    for ticket in tickets:
        batch.append(route_ticket.s(ticket["id"], ticket["text"]))
        if len(batch) >= Config.BATCH_SIZE:
            group(batch).apply_async()
            batch.clear()
    if batch:
        group(batch).apply_async()
    logger.info("Dispatched %d tickets for routing.", len(tickets))

if __name__ == "__main__":
    pending = load_pending_tickets()
    dispatch_tickets(pending)
