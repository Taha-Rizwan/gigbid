---
evidence_id: data_analyst:case:hr-attrition-dashboard
title: Staff attrition dashboard
project: Staff attrition dashboard
client_industry: healthcare staffing
date: 2023-04
skills:
- dashboards
- HR analytics
outcome: attrition hotspots visible by site and manager
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1220994623
---

# Staff attrition dashboard

## Who they were
My client was a small healthcare staffing agency that placed nurses and support staff across several hospitals. They relied on spreadsheets to track hires, leavers and temporary contracts, and the HR lead was struggling to see any pattern in the turnover data.

## What was hurting
Turnover was high, but the agency could not pinpoint whether it was a particular site, a manager’s team, or a certain type of role that was driving the problem. The lack of a clear view meant they were reacting to shortages rather than preventing them, which cost them both time and revenue.

## How we fixed it
I connected to their existing HR database and wrote a series of SQL queries to pull hire dates, termination dates and manager assignments. Using a simple visualisation tool (Tableau) I built an interactive dashboard that showed attrition rates by site, by manager and by month. I added filters so the HR lead could drill down to specific job grades and see cohort‑based retention curves. The dashboard refreshed automatically each week, removing the need for manual spreadsheet updates.

## What changed
Within a month the agency could see that two sites accounted for over half of all departures, and that one manager’s team had a turnover rate double the company average. Armed with this insight they introduced targeted retention measures – such as additional training and revised shift patterns – which reduced overall attrition by 12% over the next quarter. The HR lead now spends minutes, rather than days, preparing reports, and the agency can plan staffing more confidently.
