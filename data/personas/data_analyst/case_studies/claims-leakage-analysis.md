---
evidence_id: data_analyst:case:claims-leakage-analysis
title: Claims leakage analysis
project: Meridian Mutual - Claims leakage analysis
client_industry: insurance
date: 2021-11
skills:
- data analysis
- insurance analytics
- root-cause analysis
outcome: GBP 1.2M a year of leakage flagged; two process fixes adopted
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 733058942
---

# Claims leakage analysis

I joined Meridian Mutual at a time when the claims department was concerned that they might be paying out more than they should. By digging into the data, I was able to surface hidden losses and give the business a clear view of where money was slipping through the cracks.

**Challenge**
- The existing reporting was high‑level and aggregated, making it impossible to see individual claim discrepancies.
- Policy documents were stored as PDFs and the payments data lived in a separate warehouse, so there was no automated way to compare the two.
- Senior managers needed actionable insights quickly, without a deep technical dive.

**Approach**
- I extracted every claim transaction and the corresponding policy terms, then built a step‑by‑step routine that matched each payment to the exact coverage limits defined in the wording.
- The routine flagged any instance where the amount disbursed exceeded what the policy permitted, and it grouped the results by product line, region and claim type to highlight patterns.
- To make the findings easy to explore, I built an interactive visual dashboard that let users drill down from a summary view to the individual claim level, showing the over‑payment amount, the policy clause, and a recommended action.
- I used SQL to pull and transform the raw data, and Tableau to visualise the results for the business users.

**Impact**
- The analysis identified **£1.2 M a year** of leakage that had previously gone unnoticed.
- Two of the flagged issues were turned into formal process fixes, now embedded in the claims workflow, preventing similar over‑payments.
- The dashboard is now a regular part of the monthly performance review, giving the team a simple way to monitor leakage trends and intervene early.
- Senior leadership praised the clear, non‑technical presentation, which allowed them to act confidently without needing a data science background.

Overall, the project turned a vague concern about excess payouts into a concrete, data‑driven solution that saved the company substantial money and tightened its control over claim settlements.
