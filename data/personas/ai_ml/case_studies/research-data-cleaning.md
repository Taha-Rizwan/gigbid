---
evidence_id: ai_ml:case:research-data-cleaning
title: Cleaning a messy survey dataset for a PhD researcher
project: Cleaning a messy survey dataset for a PhD researcher
client_industry: academia
date: 2022-03
skills:
- data cleaning
- pandas
outcome: 18 files merged into one tidy table with a data dictionary
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1308683038
---

# Cleaning a messy survey dataset for a PhD researcher

I was approached by a doctoral candidate in sociology who had accumulated eighteen CSV files from a longitudinal survey. The files varied in column order, contained numerous missing placeholders, and used inconsistent date formats, making any direct analysis impossible.

**Challenge**
- Merge disparate files without losing metadata.
- Standardise column names and data types.
- Document the final schema for future reference.
- Deliver the work within a two‑week window.

**Approach**
I began by writing a small script in **pandas** to read each file, normalise the header row and coerce dates to ISO format. A series of conditional checks replaced placeholder strings (e.g., "NA", "-", "?") with proper null values. After concatenating the dataframes, I performed a deduplication step based on the respondent identifier and timestamp. The resulting table was then sorted and exported as a single CSV. To aid reproducibility, I compiled a data dictionary in a markdown file, listing each column, its type, permissible values and any transformations applied.

**Impact**
- The researcher now works with one clean dataset of 12 342 rows instead of juggling multiple inconsistent files.
- The data dictionary reduced the time required to understand the schema by an estimated 30 %.
- The cleaned data has already been used to generate preliminary descriptive statistics for a conference paper.
- The client praised the transparent workflow and the clear documentation, which will support future extensions of the survey.

Overall, the project demonstrated how a disciplined, script‑driven approach to data cleaning can turn a chaotic collection of files into a reliable analytical resource.
