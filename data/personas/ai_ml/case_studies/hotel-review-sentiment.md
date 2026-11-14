---
evidence_id: ai_ml:case:hotel-review-sentiment
title: Guest review sentiment dashboard
project: Guest review sentiment dashboard
client_industry: hospitality
date: 2022-11
skills:
- sentiment analysis
- dashboards
outcome: weekly sentiment report for 14 hotels
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1177627648
---

# Guest review sentiment dashboard

### The problem
The hospitality client managed fourteen boutique hotels and received hundreds of guest reviews each week across multiple platforms. Their existing process involved manually reading a subset of comments and compiling ad‑hoc notes, which was time‑consuming and prone to bias. They needed a reliable way to see, at a glance, how sentiment was changing over time and to identify any sudden shifts that might indicate service issues.

### What I did
I set up a pipeline that collected the latest reviews via the hotels' API and stored them in a secure database. Using a pre‑trained language model fine‑tuned on a small set of labelled examples, I performed sentiment classification into positive, neutral and negative categories. The model’s performance was measured on a hold‑out set, achieving an F1 score of 0.87. I then aggregated the daily counts and calculated a rolling weekly average for each hotel. For visualisation I used **Tableau** to create a single dashboard that displayed a heat‑map of sentiment scores, trend lines for each property and a table of the top five most frequently mentioned topics. The dashboard refreshed automatically each night, and I scheduled an email that attached a one‑page PDF summary to the client’s weekly operations meeting.

### Results
The client began receiving a consistent weekly sentiment report for all fourteen hotels from the first week of deployment. They reported a 30 % reduction in the time staff spent preparing review summaries and were able to address negative trends within 48 hours on average. The clear visualisation also helped senior management spot seasonal patterns, informing staffing and service adjustments that improved overall guest satisfaction scores.
