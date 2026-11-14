---
evidence_id: ai_ml:case:churn-uplift-telco
title: Churn uplift model for prepaid subscribers
project: Northwind Telecom - Churn uplift model for prepaid subscribers
client_industry: telecom
date: 2020-11
skills:
- uplift modelling
- churn prediction
- gradient boosting
- experiment design
outcome: churn in the targeted cohort fell 11%; retention offer spend down 30%
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 698228501
---

# Churn uplift model for prepaid subscribers

During my tenure at Northwind Telecom I was tasked with improving the profitability of our prepaid churn reduction programme. The existing approach applied blanket offers to a large subscriber base, leading to high spend with modest impact. I therefore devised a two‑model pipeline: the first model estimated the probability that a customer would actually be persuaded by an incentive, while the second model predicted the uplift in churn risk if the offer was accepted. By intersecting these predictions I could focus resources on the subset of customers for whom an offer would truly move the needle.

The data engineering side involved extracting historic usage, billing and interaction records from our Teradata warehouse and transforming them into a tidy feature set. I used Python to orchestrate the ETL and to construct the feature matrix, applying standard preprocessing steps such as aggregation, encoding of categorical fields and handling of missing values. For the predictive layer I trained gradient‑boosted decision trees with LightGBM, which handled the high‑cardinality categorical variables and provided robust performance on the imbalanced churn outcome.

Model validation was carried out using a causal inference framework to ensure that the uplift estimates were not confounded by selection bias. This allowed us to simulate the effect of deploying the offers before they went live, and to set a threshold that maximised the net gain after accounting for the cost of the incentives. The final system was scheduled as a weekly scoring job that processed over four million subscriber records, generating a ranked list of candidates for the next retention campaign.

When the solution was launched in November 2020, the targeted cohort saw churn fall by 11% compared with the previous period. Because offers were now only sent to those likely to act, the overall spend on retention incentives dropped by 30%, delivering a clear lift in return on investment. The project demonstrated how a disciplined, data‑driven approach to targeting can produce tangible business value while keeping operational complexity manageable.

Beyond the immediate metrics, the implementation introduced a repeatable framework for future campaigns. The weekly scoring pipeline was integrated into the existing data platform, and the modelling code was version‑controlled and documented for hand‑over to the analytics team. This ensured that the gains were sustainable and that the methodology could be extended to other segments, such as post‑paid customers or new product launches.
