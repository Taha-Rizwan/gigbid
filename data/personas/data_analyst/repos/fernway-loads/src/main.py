"""
Airflow DAG that orchestrates the nightly load for the Fernway brand.

The DAG runs at 02:30 am UTC, retries up to three times and, if a run
fails, a back‑fill can be triggered manually.  All tasks are idempotent
so re‑running does not duplicate data.
"""

import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Import the helper modules defined above
from .load_orders import fetch_orders, load_orders
from .load_customers import (
    fetch_shopify_customers,
    fetch_klaviyo_engagement,
    load_customers,
    load_engagement,
)

default_args = {
    "owner": "hannah.kowalski",
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

dag = DAG(
    dag_id="fernway_nightly_load",
    default_args=default_args,
    description="Nightly extraction of orders, customers and email data",
    schedule_interval="30 2 * * *",  # 02:30 UTC daily
    start_date=datetime(2022, 9, 1),
    catchup=False,
    max_active_runs=1,
)

def _load_orders(**context):
    """Fetch new orders and push them to Snowflake."""
    # In a real deployment we would store the last processed ID in XCom or a table.
    orders = fetch_orders()
    load_orders(orders)

def _load_customers(**context):
    """Fetch Shopify customers and load them."""
    customers = fetch_shopify_customers()
    load_customers(customers)

def _load_engagement(**context):
    """Fetch Klaviyo engagement and load it."""
    engagement = fetch_klaviyo_engagement()
    load_engagement(engagement)

task_orders = PythonOperator(
    task_id="load_orders",
    python_callable=_load_orders,
    dag=dag,
)

task_customers = PythonOperator(
    task_id="load_customers",
    python_callable=_load_customers,
    dag=dag,
)

task_engagement = PythonOperator(
    task_id="load_engagement",
    python_callable=_load_engagement,
    dag=dag,
)

# Simple linear flow – all three can run in parallel.
task_orders >> task_customers >> task_engagement
