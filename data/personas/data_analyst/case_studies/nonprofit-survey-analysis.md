---
evidence_id: data_analyst:case:nonprofit-survey-analysis
title: Beneficiary survey analysis for a food charity
project: Riverbank Food Trust - Beneficiary survey analysis for a food charity
client_industry: non-profit
date: 2023-11
skills:
- survey analysis
- data visualisation
- reporting
outcome: findings went into the grant report; funding renewed for three years
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1377426569
---

# Beneficiary survey analysis for a food charity

When Riverbank Food Trust approached me in November 2023, they were struggling to make sense of a large beneficiary survey that covered dozens of small neighbourhoods across the city. The raw data was a mix of multiple‑choice and free‑text answers, and the trustees needed a concise, non‑technical summary to support their upcoming grant application. I started by cleaning the dataset, standardising the response formats and removing any duplicate entries. This gave me a solid foundation to build on, ensuring that the subsequent analysis would be reliable.

The first challenge was to make sure that the voices of smaller communities were not lost in the aggregate figures. I applied a weighting scheme that gave each neighbourhood a proportional influence based on its size, so that the results reflected the true distribution of beneficiaries rather than being dominated by the larger areas. This approach meant that the insights were fair and balanced, and it also gave the trustees confidence that every part of the charity’s reach was represented.

Next, I turned the agree/disagree questions into a series of clean, colour‑coded charts that highlighted trends at a glance. By converting the Likert‑scale responses into visual summaries, the board could instantly see where the charity was performing well and where improvements were needed. I used Python to orchestrate the data transformations and to generate the final visualisations, which were then embedded in an interactive dashboard. Plotly helped to create the responsive charts that allowed trustees to hover over points for more detail without being overwhelmed by raw numbers.

Beyond the visual side, I performed a cohort analysis to track how satisfaction levels changed over time for different beneficiary groups. This revealed that recent outreach programmes had significantly lifted satisfaction in the western districts, while the eastern areas still lagged behind. I compiled these findings into a concise narrative, linking each insight to a specific recommendation for future programme focus. The final report was packaged in a format that the charity could easily paste into their grant application, complete with clear visual snapshots and a short executive summary.

The impact was immediate. The trustees used the dashboards in their board meeting to demonstrate evidence‑based progress, and the clear, weighted insights were cited verbatim in the grant report. As a result, Riverbank Food Trust’s funding was renewed for three years, giving them the stability to continue expanding their services. The project not only delivered the required analytics but also equipped the charity with a repeatable framework for analysing future surveys, turning raw feedback into strategic advantage.
