# survey-toolkit

A lightweight Python toolkit for analysing and visualising beneficiary survey data.

## Purpose
- Apply population weighting to survey responses so that small neighbourhoods are not drowned out.  
- Transform agree/disagree questions into easy‑to‑read charts for non‑technical stakeholders.

## How it works
- **Load** raw CSV data (path supplied via the `SURVEY_CSV` environment variable).  
- **Weight** each response based on the `neighbourhood_weight` column.  
- **Aggregate** agree/disagree answers and produce Plotly bar charts.  
- **Export** the charts as self‑contained HTML files for inclusion in reports.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install pandas plotly
```

## Usage
```bash
export SURVEY_CSV=path/to/survey.csv
python -m src.main
```
The toolkit will create an `output/` folder containing one HTML file per question.

---
