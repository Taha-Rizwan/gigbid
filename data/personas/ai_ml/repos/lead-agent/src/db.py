"""Simple PostgreSQL helper functions.

All queries are deliberately minimal and use psycopg2‑binary.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

_DSN = os.getenv("DATABASE_URL")
if not _DSN:
    raise RuntimeError("DATABASE_URL not set")

_conn = psycopg2.connect(_DSN, cursor_factory=RealDictCursor)
_conn.autocommit = True


def get_new_enquiries():
    """Return a list of unprocessed enquiry rows."""
    with _conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, message, phone
            FROM enquiries
            WHERE processed = FALSE
            ORDER BY received_at ASC
            LIMIT 10;
            """
        )
        return cur.fetchall()


def mark_enquiry_processed(enquiry_id: int):
    """Flag an enquiry as processed."""
    with _conn.cursor() as cur:
        cur.execute(
            "UPDATE enquiries SET processed = TRUE WHERE id = %s;",
            (enquiry_id,),
        )


def insert_lead(lead: dict):
    """Insert a qualified lead into the leads table."""
    with _conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO leads
                (name, email, phone, property_type, budget, source, created_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s);
            """,
            (
                lead["name"],
                lead["email"],
                lead["phone"],
                lead["property_type"],
                lead["budget"],
                lead["source"],
                lead["created_at"],
            ),
        )
