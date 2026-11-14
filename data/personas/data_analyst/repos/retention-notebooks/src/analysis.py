# %%
"""
Functions that transform raw data into analysis‑ready structures
and fit survival models.
"""

import pandas as pd
from lifelines import KaplanMeierFitter
from typing import Dict

def prepare_cohorts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a weekly cohort column and keep only columns needed for modelling.

    Parameters
    ----------
    df: pd.DataFrame
        Output of :func:`data_loader.load_signups`.

    Returns
    -------
    pd.DataFrame
        Columns: user_id, cohort_week (datetime), onboarding_variant,
        duration, event_observed.
    """
    # Cohort is the Monday of the signup week
    df["cohort_week"] = df["signup_date"].dt.to_period("W").apply(lambda p: p.start_time)

    cohort_df = df[
        [
            "user_id",
            "cohort_week",
            "onboarding_variant",
            "duration",
            "event_observed",
        ]
    ].copy()
    return cohort_df

def fit_survival_models(cohort_df: pd.DataFrame) -> Dict[str, KaplanMeierFitter]:
    """
    Fit a Kaplan‑Meier curve for each onboarding variant.

    Parameters
    ----------
    cohort_df: pd.DataFrame
        Result of :func:`prepare_cohorts`.

    Returns
    -------
    dict
        Mapping variant name → fitted ``KaplanMeierFitter``.
    """
    kmf_dict: Dict[str, KaplanMeierFitter] = {}
    for variant, sub in cohort_df.groupby("onboarding_variant"):
        kmf = KaplanMeierFitter()
        kmf.fit(
            durations=sub["duration"],
            event_observed=sub["event_observed"],
            label=variant,
        )
        kmf_dict[variant] = kmf
    return kmf_dict
