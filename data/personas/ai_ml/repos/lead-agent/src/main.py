"""Entry point for the lead‑qualification agent.

The script creates a LangGraph workflow, connects to PostgreSQL,
and continuously processes new enquiry records.
"""

import os
import asyncio
import logging
from datetime import datetime, timezone

from src.db import get_new_enquiries, mark_enquiry_processed, insert_lead
from src.workflow import build_workflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


async def process_enquiry(enquiry: dict, workflow) -> None:
    """Run the LangGraph workflow for a single enquiry."""
    logging.info("Processing enquiry %s", enquiry["id"])
    result = await workflow.run(
        {
            "enquiry_text": enquiry["message"],
            "prospect_phone": enquiry["phone"],
            "enquiry_id": enquiry["id"],
        }
    )
    if result.get("approved"):
        lead = {
            "name": result["name"],
            "email": result["email"],
            "phone": result["prospect_phone"],
            "property_type": result["property_type"],
            "budget": result["budget"],
            "source": "sms",
            "created_at": datetime.now(timezone.utc),
        }
        insert_lead(lead)
        logging.info("Lead %s stored", lead["email"])
    else:
        logging.info("Enquiry %s rejected by human reviewer", enquiry["id"])

    mark_enquiry_processed(enquiry["id"])


async def main() -> None:
    """Main loop – poll DB, run workflow, sleep."""
    workflow = await build_workflow()
    while True:
        enquiries = get_new_enquiries()
        if not enquiries:
            await asyncio.sleep(5)
            continue

        tasks = [process_enquiry(e, workflow) for e in enquiries]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
