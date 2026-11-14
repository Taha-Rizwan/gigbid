import os
import pandas as pd
import plotly.graph_objects as go

def aggregate_agree_disagree(df: pd.DataFrame) -> dict:
    """
    For each question column, compute the weighted sum of 'agree' (value 1)
    and 'disagree' (value 0). Returns a dict:
        {question_name: {"agree": weighted_agree, "disagree": weighted_disagree}}
    """
    result = {}
    response_cols = [c for c in df.columns if c not in {"respondent_id", "neighbourhood", "neighbourhood_weight"}]
    for col in response_cols:
        agree = df[col].sum()
        # Total weight for the column is sum of weights (ignoring NaN)
        total_weight = df[col].notna().sum() * df["neighbourhood_weight"].mean()
        disagree = total_weight - agree
        result[col] = {"agree": agree, "disagree": disagree}
    return result

def make_bar_chart(question: str, data: dict, output_dir: str) -> None:
    """
    Create a Plotly bar chart for a single question and save as HTML.
    """
    fig = go.Figure(
        data=[
            go.Bar(name="Agree", x=["Agree"], y=[data["agree"]]),
            go.Bar(name="Disagree", x=["Disagree"], y=[data["disagree"]]),
        ]
    )
    fig.update_layout(
        title_text=f"Survey results – {question}",
        barmode="stack",
        yaxis_title="Weighted responses",
    )
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{question}.html")
    fig.write_html(out_path)

def visualise_all(aggregated: dict, output_dir: str = "output") -> None:
    """
    Generate charts for all questions in the aggregated dict.
    """
    for question, data in aggregated.items():
        make_bar_chart(question, data, output_dir)
