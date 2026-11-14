"""
Functions for extracting customer data from Shopify and email engagement
from Klaviyo, then loading both into Snowflake.

Both sources share the same ``CUSTOMER_ID`` key, allowing downstream
joins.
"""

import os
import json
import logging
from typing import List, Dict

import requests
import snowflake.connector

# Re‑use the same env vars as in load_orders.py
SHOPIFY_TOKEN = os.getenv("SHOPIFY_TOKEN")
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
KLAVIYO_TOKEN = os.getenv("KLAVIYO_TOKEN")
KLAVIYO_LIST_ID = os.getenv("KLAVIYO_LIST_ID")

SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA")

def _sf_conn():
    return snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        account=SNOWFLAKE_ACCOUNT,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
    )

def fetch_shopify_customers(since_id: int = None) -> List[Dict]:
    """Pull customers from Shopify."""
    headers = {"X-Shopify-Access-Token": SHOPIFY_TOKEN}
    params = {"limit": 250}
    if since_id:
        params["since_id"] = since_id

    url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/2023-04/customers.json"
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    customers = resp.json().get("customers", [])
    logging.info("Fetched %d Shopify customers", len(customers))
    return customers

def fetch_klaviyo_engagement() -> List[Dict]:
    """Pull email engagement metrics for the configured list."""
    headers = {"Authorization": f"Klaviyo-API-Key {KLAVIYO_TOKEN}"}
    url = f"https://a.klaviyo.com/api/v2/list/{KLAVIYO_LIST_ID}/members/all"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    logging.info("Fetched %d Klaviyo members", len(data))
    return data

def _transform_customer(cust: Dict) -> Dict:
    return {
        "customer_id": cust["id"],
        "email": cust.get("email"),
        "first_name": cust.get("first_name"),
        "last_name": cust.get("last_name"),
        "created_at": cust["created_at"],
        "tags": json.dumps(cust.get("tags", [])),
    }

def _transform_engagement(member: Dict) -> Dict:
    return {
        "customer_id": member["id"],
        "email": member.get("email"),
        "last_open": member.get("last_open"),
        "last_click": member.get("last_click"),
        "profile": json.dumps(member.get("profile", {})),
    }

def load_customers(customers: List[Dict]) -> None:
    """Insert Shopify customers into RAW_CUSTOMERS."""
    if not customers:
        logging.info("No Shopify customers to load.")
        return

    rows = [_transform_customer(c) for c in customers]
    insert_sql = """
        INSERT INTO RAW_CUSTOMERS (
            CUSTOMER_ID, EMAIL, FIRST_NAME, LAST_NAME,
            CREATED_AT, TAGS
        ) VALUES (%(customer_id)s, %(email)s, %(first_name)s,
                  %(last_name)s, %(created_at)s, %(tags)s)
    """
    conn = _sf_conn()
    try:
        with conn.cursor() as cur:
            cur.executemany(insert_sql, rows)
        conn.commit()
        logging.info("Loaded %d customers into Snowflake.", len(rows))
    finally:
        conn.close()

def load_engagement(engagement: List[Dict]) -> None:
    """Insert Klaviyo engagement rows into RAW_ENGAGEMENT."""
    if not engagement:
        logging.info("No engagement records to load.")
        return

    rows = [_transform_engagement(m) for m in engagement]
    insert_sql = """
        INSERT INTO RAW_ENGAGEMENT (
            CUSTOMER_ID, EMAIL, LAST_OPEN, LAST_CLICK, PROFILE
        ) VALUES (%(customer_id)s, %(email)s, %(last_open)s,
                  %(last_click)s, %(profile)s)
    """
    conn = _sf_conn()
    try:
        with conn.cursor() as cur:
            cur.executemany(insert_sql, rows)
        conn.commit()
        logging.info("Loaded %d engagement rows into Snowflake.", len(rows))
    finally:
        conn.close()
