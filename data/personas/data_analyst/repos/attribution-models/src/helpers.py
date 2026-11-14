"""
Utility helpers for the attribution pipeline.

Only lightweight functions are kept here to avoid pulling heavy
dependencies into the dbt models.
"""

import os
from typing import List

def get_env_list(var_name: str, delimiter: str = ",") -> List[str]:
    """
    Read a comma‑separated environment variable and return a list of stripped strings.
    Returns an empty list if the variable is not set.
    """
    raw = os.getenv(var_name, "")
    return [item.strip() for item in raw.split(delimiter) if item.strip()]
