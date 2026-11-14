"""
Package initialisation for the Fernway nightly loads.

The package contains a small Airflow DAG that pulls data from three
sources (orders, customers and email engagement), transforms the payloads
into Snowflake‑compatible rows and writes them into a single warehouse
schema.  All configuration is read from environment variables.
"""
