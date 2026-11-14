import os
import pandas as pd

def load_survey(csv_path: str) -> pd.DataFrame:
    """
    Load the raw survey CSV into a DataFrame.
    Expected columns:
        - respondent_id
        - neighbourhood
        - neighbourhood_weight (float)
        - <question columns> (e.g. q1_agree, q2_disagree)
    """
    df = pd.read_csv(csv_path)
    return df

def apply_weights(df: pd.DataFrame) -> pd.DataFrame:
    """
    Multiply each response row by its neighbourhood weight.
    The weight column must be named 'neighbourhood_weight'.
    """
    weight_col = "neighbourhood_weight"
    if weight_col not in df.columns:
        raise ValueError(f"Missing required column '{weight_col}'")
    # Create a copy to avoid mutating the original DataFrame
    weighted = df.copy()
    # All non‑weight columns are treated as categorical responses.
    response_cols = [c for c in weighted.columns if c not in {"respondent_id", "neighbourhood", weight_col}]
    for col in response_cols:
        # Convert to numeric where possible; NaNs stay as NaN
        weighted[col] = pd.to_numeric(weighted[col], errors="coerce")
        weighted[col] = weighted[col] * weighted[weight_col]
    return weighted
