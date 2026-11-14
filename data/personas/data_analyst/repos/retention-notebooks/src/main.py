# %%
"""
Entry point for the retention‑onboarding analysis.

It loads the raw sign‑up data, prepares weekly cohorts, fits a
Kaplan‑Meier survival model for each onboarding variant and saves the
resulting plots.
"""

import os
from pathlib import Path

from data_loader import load_signups
from analysis import prepare_cohorts, fit_survival_models
from visualisation import plot_retention_curve, plot_survival_comparison

# Configuration --------------------------------------------------------------
DATA_PATH = os.getenv("RETENTION_DATA_PATH", "data/signups.csv")
OUTPUT_DIR = Path(os.getenv("RETENTION_OUTPUT_DIR", "output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Main workflow ---------------------------------------------------------------
def main() -> None:
    """Run the full analysis pipeline."""
    # Load raw data
    df = load_signups(DATA_PATH)

    # Create weekly cohorts and label onboarding variant
    cohorts = prepare_cohorts(df)

    # Fit survival models per variant
    models = fit_survival_models(cohorts)

    # Plot retention curve (overall)
    plot_retention_curve(cohorts, output_path=OUTPUT_DIR / "weekly_retention.png")

    # Plot survival comparison between variants
    plot_survival_comparison(models, output_path=OUTPUT_DIR / "survival_comparison.png")

    print(f"Plots saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
