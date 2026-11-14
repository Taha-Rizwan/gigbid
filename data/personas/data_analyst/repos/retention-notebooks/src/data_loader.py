# %%
"""
Utility functions for loading raw sign‑up data.

The expected CSV format:
    user_id, signup_date, onboarding_variant, churn_date
- signup_date and churn_date are ISO‑8601 strings.
- churn_date may be empty for active users.
"""

import pandas as pd
from datetime import datetime

def _parse_date(date_str: str) -> pd.Timestamp | pd.NaT:
    """Parse a date string, returning NaT for empty values."""
    if not date_str or pd.isna(date_str):
        return pd.NaT
    return pd.to_datetime(date_str, utc=True)

def load_signups(csv_path: str) -> pd.DataFrame:
    """
    Load sign‑up data from a CSV file.

    Parameters
    ----------
    csv_path: str
        Path to the CSV containing raw sign‑up records.

    Returns
    -------
    pd.DataFrame
        Columns: user_id (str), signup_date (Timestamp),
        onboarding_variant (str), churn_date (Timestamp or NaT).
    """
    df = pd.read_csv(csv_path, dtype={"user_id": str, "onboarding_variant": str})
    df["signup_date"] = df["signup_date"].apply(_parse_date)
    df["churn_date"] = df["churn_date"].apply(_parse_date)

    # Derive churn indicator and duration in days
    df["event_observed"] = ~df["churn_date"].isna()
    df["duration"] = (
        (df["churn_date"].fillna(pd.Timestamp.utcnow()) - df["signup_date"])
        .dt.days
    )
    return df
