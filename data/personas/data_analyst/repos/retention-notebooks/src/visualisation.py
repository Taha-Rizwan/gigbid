# %%
"""
Plotting helpers for retention and survival analysis.
"""

import matplotlib.pyplot as plt
import pandas as pd
from lifelines import KaplanMeierFitter
from typing import Dict

def plot_retention_curve(cohort_df: pd.DataFrame, output_path: Path) -> None:
    """
    Produce a line chart of weekly retention percentages.

    Retention for a week is the proportion of users from that cohort
    still active at the end of the week.
    """
    # Determine week index relative to signup
    cohort_df["week_index"] = (
        (cohort_df["duration"] // 7).astype(int)
    )

    # Aggregate retention per week
    retention = (
        cohort_df.groupby("week_index")["event_observed"]
        .apply(lambda s: 1 - s.mean())  # proportion still active
        .reset_index()
    )

    plt.figure(figsize=(8, 5))
    plt.plot(retention["week_index"], retention[0] * 100, marker="o")
    plt.title("Weekly Retention Curve")
    plt.xlabel("Weeks since signup")
    plt.ylabel("Retention (%)")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def plot_survival_comparison(
    kmf_dict: Dict[str, KaplanMeierFitter], output_path: Path
) -> None:
    """
    Plot Kaplan‑Meier survival curves for each onboarding variant.
    """
    plt.figure(figsize=(8, 5))
    for kmf in kmf_dict.values():
        kmf.plot_survival_function(ci_show=False)

    plt.title("Survival by Onboarding Variant")
    plt.xlabel("Days since signup")
    plt.ylabel("Survival probability")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(title="Variant")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
