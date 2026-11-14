"""
Utility functions for fetching and loading order data.

The functions are deliberately lightweight – they make a GET request to
the Shopify API, normalise the JSON into a list of dictionaries and then
bulk‑insert the rows into Snowflake.
"""

import os
import json
import logging
from typing import List, Dict

import requests
import snowflake.connector
from snowflake.connector.cursor import SnowflakeCursor

# Environment variables (set by the Airflow connection or the runner)
SHOPIFY_TOKEN = os.getenv("SHOPIFY_TOKEN")
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA")

def _get_snowflake_connection() -> snowflake.connector.SnowflakeConnection:
    """Create a Snowflake connection using credentials from env."""
    return snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        account=SNOWFLAKE_ACCOUNT,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
    )

def fetch_orders(since_id: int = None) -> List[Dict]:
    """
    Pull orders from Shopify.

    Parameters
    ----------
    since_id: optional last order ID processed; if supplied the API returns
    only newer records.

    Returns
    -------
    List of order dictionaries ready for transformation.
    """
    headers = {"X-Shopify-Access-Token": SHOPIFY_TOKEN}
    params = {"status": "any", "limit": 250}
    if since_id:
        params["since_id"] = since_id

    url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/2023-04/orders.json"
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    orders = response.json().get("orders", [])
    logging.info("Fetched %d orders from Shopify", len(orders))
    return orders

def _transform_order(order: Dict) -> Dict:
    """Flatten a Shopify order into the columns we store."""
    return {
        "order_id": order["id"],
        "created_at": order["created_at"],
        "total_price": float(order["total_price"]),
        "currency": order["currency"],
        "customer_id": order["customer"]["id"] if order.get("customer") else None,
        "line_items": json.dumps(order["line_items"]),
    }

def load_orders(orders: List[Dict]) -> None:
    """
    Bulk‑load a list of transformed orders into Snowflake.

    The target table is ``RAW_ORDERS`` in the configured schema.
    """
    if not orders:
        logging.info("No orders to load.")
        return

    transformed = [_transform_order(o) for o in orders]

    insert_sql = """
        INSERT INTO RAW_ORDERS (
            ORDER_ID,
            CREATED_AT,
            TOTAL_PRICE,
            CURRENCY,
            CUSTOMER_ID,
            LINE_ITEMS
        ) VALUES (%(order_id)s, %(created_at)s, %(total_price)s,
                  %(currency)s, %(customer_id)s, %(line_items)s)
    """

    conn = _get_snowflake_connection()
    try:
        with conn.cursor() as cur:  # type: SnowflakeCursor
            cur.executemany(insert_sql, transformed)
        conn.commit()
        logging.info("Loaded %d orders into Snowflake.", len(transformed))
    finally:
        conn.close()
