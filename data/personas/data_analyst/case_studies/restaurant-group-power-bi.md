---
evidence_id: data_analyst:case:restaurant-group-power-bi
title: Sales and labour dashboard for a restaurant group
project: Sales and labour dashboard for a restaurant group
client_industry: hospitality
date: 2024-06
skills:
- dashboards
outcome: labour cost as % of sales tracked daily across 6 sites
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 641649826
---

# Sales and labour dashboard for a restaurant group

I was approached by a small restaurant group that runs six venues across the city. They wanted a simple way to see how much they were spending on staff each day compared with the money they were taking in, and to spot any sites that were slipping out of line.

**Challenge**
- Data were scattered across separate POS registers and a basic payroll spreadsheet.
- The owner only had time for a quick glance each morning; a complex report would not be used.
- They needed the information for every site, updated daily, without having to pull files manually.

**Approach**
- I linked the POS export and the payroll sheet into a single query using SQL, cleaning the dates and standardising the site codes.
- A small pipeline ran each night, loading the combined table into a lightweight database.
- Using Tableau, I created a single‑page dashboard that shows total sales, total labour cost and the labour‑cost‑as‑%‑of‑sales metric for each venue.
- The layout is deliberately plain: a bar for each site, a colour cue when the percentage exceeds the agreed threshold, and a brief note on the trend over the past week.
- I set the dashboard to refresh automatically each morning, so the owner can open it and have the latest numbers without any extra steps.

**Impact**
- The group now monitors labour cost daily, catching spikes within hours rather than weeks.
- Over the first two months, they reduced the average labour‑to‑sales ratio by 1.3 percentage points, saving roughly £4,800.
- The owner reports that the visual simplicity means the team discusses the numbers at each shift change, leading to quicker staffing adjustments.
- The solution required only a modest amount of development time and can be extended to new sites with minimal effort.
