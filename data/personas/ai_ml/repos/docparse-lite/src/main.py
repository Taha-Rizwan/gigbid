# %%
"""
Batch driver script.
Scans INPUT_DIR for PDFs, extracts fields, validates them and writes a CSV.
Documents with confidence below CONFIDENCE_THRESHOLD are moved to REVIEW_DIR.
Successful extracts are moved to PROCESSED_DIR.
"""

import csv
import logging
from pathlib import Path

from .config import INPUT_DIR, PROCESSED_DIR, REVIEW_DIR, CONFIDENCE_THRESHOLD
from .extractor import extract_document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CSV_HEADER = [
    "file_name",
    "confidence",
    # fields from the schema (order matches DocumentFields)
    "invoice_number",
    "bill_of_lading",
    "shipper_name",
    "consignee_name",
    "origin_port",
    "destination_port",
    "vessel_name",
    "departure_date",
    "arrival_date",
    "cargo_description",
    "gross_weight_kg",
    "net_weight_kg",
    "container_number",
    "freight_amount_usd",
    "insurance_amount_usd",
    "total_amount_usd",
    "payment_terms",
    "notes",
]

def process_batch():
    output_path = PROCESSED_DIR / "extracted.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(CSV_HEADER)

        for pdf_file in INPUT_DIR.glob("*.pdf"):
            logger.info("Processing %s", pdf_file.name)
            record, confidence = extract_document(pdf_file)

            if record is None or confidence < CONFIDENCE_THRESHOLD:
                target = REVIEW_DIR / pdf_file.name
                pdf_file.rename(target)
                logger.info("Moved to review (confidence %.2f)", confidence)
                continue

            row = [pdf_file.name, f"{confidence:.2f}"] + [
                getattr(record, field) for field in CSV_HEADER[2:]
            ]
            writer.writerow(row)

            pdf_file.rename(PROCESSED_DIR / pdf_file.name)
            logger.info("Successfully extracted (confidence %.2f)", confidence)

if __name__ == "__main__":
    process_batch()
# %%
