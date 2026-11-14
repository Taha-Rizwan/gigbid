import os
from pathlib import Path
from .weighting import load_survey, apply_weights
from .visualisation import aggregate_agree_disagree, visualise_all

def main() -> None:
    """
    Entry point for the survey‑toolkit.
    Reads the CSV path from the SURVEY_CSV environment variable,
    processes the data, and writes HTML charts to the output folder.
    """
    csv_path = os.getenv("SURVEY_CSV")
    if not csv_path:
        raise EnvironmentError("Please set the SURVEY_CSV environment variable to the survey CSV file.")
    if not Path(csv_path).exists():
        raise FileNotFoundError(f"Survey file not found: {csv_path}")

    # Load and weight the data
    raw_df = load_survey(csv_path)
    weighted_df = apply_weights(raw_df)

    # Aggregate and visualise
    aggregated = aggregate_agree_disagree(weighted_df)
    visualise_all(aggregated, output_dir="output")
    print(f"Charts generated in the 'output' directory ({len(aggregated)} files).")

if __name__ == "__main__":
    main()
