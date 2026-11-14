---
evidence_id: data_analyst:case:brightcart-kpi-dashboard
title: Trading KPI dashboard for an online retailer
project: Brightcart - Trading KPI dashboard for an online retailer
client_industry: e-commerce
date: 2019-05
skills:
- dashboards
- KPI design
- data modelling
outcome: weekly reporting went from two days of spreadsheets to automatic; 120 regular
  users
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 2028228092
---

# Trading KPI dashboard for an online retailer

### The problem
Brightcart relied on a patchwork of Excel files that traders had to update every Monday. The process took two full days, involved copying data from the sales database, manually calculating margins, and then distributing the sheets by email. Errors were common, and the lag meant decisions were based on outdated information. Management wanted a single view that anyone on the trading team could open at the start of the week and instantly see the key performance indicators they needed to steer inventory and pricing.

### What I did
I mapped the required metrics to the underlying data model and created a set of reusable calculations for margin, sell‑through and stock cover. By pulling the raw transaction data directly from the warehouse, the calculations were performed on the server side, eliminating the need for manual formulas. I then designed a one‑page report that each trader opens on Monday morning; the page automatically refreshes with the latest figures and presents the numbers in clear visual tiles and a concise table. To keep the solution maintainable, I built the data queries using SQL and layered the business logic with a small amount of DAX. The report was published to the corporate portal, and access rights were set so that all 120 regular users could view it without additional steps.

### Results
The weekly reporting time collapsed from two days of spreadsheet fiddling to a fully automated process that runs overnight. Traders now start their week with a single, reliable view of the most important metrics, freeing up time for analysis rather than data preparation. Adoption is high – 120 regular users regularly consult the dashboard – and feedback highlights the clarity of the margin and stock‑cover measures, which are built once and reused across the team. The new workflow has also reduced errors dramatically, giving senior management confidence that the numbers they see each Monday truly reflect the latest trading activity.
