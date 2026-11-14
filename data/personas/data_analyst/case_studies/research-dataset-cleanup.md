---
evidence_id: data_analyst:case:research-dataset-cleanup
title: Cleaning a research dataset before publication
project: Cleaning a research dataset before publication
client_industry: academia
date: 2024-01
skills:
- data cleaning
- pandas
outcome: dataset passed the journal's reproducibility check
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 2068974066
---

# Cleaning a research dataset before publication

I was approached by a university research team in January 2024 who needed their raw experimental data prepared for submission to a peer‑reviewed journal. The dataset was collected over several months, stored in a mixture of CSV files, and contained numerous inconsistencies that would have caused the journal’s reproducibility check to fail.

**Challenge**
- Inconsistent column headings and mixed date formats.
- Missing values scattered across key variables.
- Duplicate rows and out‑of‑range entries that distorted the analysis.
- The team required a clear audit trail so they could explain the cleaning steps in their methods section.

**Approach**
I imported the files into pandas and:
- Standardised all column names to a single convention.
- Parsed dates using a unified format and corrected any invalid entries.
- Applied a systematic missing‑value strategy: imputed where appropriate and flagged records that needed expert review.
- Removed exact duplicate rows and flagged near‑duplicates for the researchers to inspect.
- Generated a concise cleaning log in plain English, detailing each transformation for inclusion in the manuscript.

**Impact**
- The final dataset passed the journal’s reproducibility check on the first attempt.
- The research team saved several weeks of manual data wrangling, allowing them to focus on the interpretation of results.
- The cleaning log was cited in the paper, demonstrating transparency and satisfying the reviewers’ concerns.
- Feedback from the client highlighted the clarity of the documentation and the ease with which they could reproduce the steps in future projects.

Overall, the project turned a tangled collection of files into a clean, well‑documented dataset ready for publication, reinforcing the importance of meticulous data preparation in academic research.
