---
evidence_id: data_analyst:case:attribution-dbt-models
title: Marketing attribution models for a subscription app
project: Lumio Apps - Marketing attribution models for a subscription app
client_industry: consumer apps
date: 2023-02
skills:
- analytics engineering
- marketing attribution
- SQL modelling
outcome: 18% of ad spend moved to cheaper channels; CAC down 11%
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1407735338
---

# Marketing attribution models for a subscription app

I was approached by Lumio Apps, a developer of consumer subscription apps, to help them understand which marketing channels were really driving sign‑ups and how much each new user was costing them.

**Challenge**
- Their existing reports were a mix of manual spreadsheets and static dashboards that barely scratched the surface of the data they collected. 
- They needed a way to see, every morning, how much they were spending on each channel and what the true cost per acquisition was, without having to pull raw GA4 exports by hand.
- The team was uncomfortable with complex SQL, so any solution had to be transparent and easy to audit.

**Approach**
- I started by extracting the raw event stream from their GA4 export and loading it into a cloud data warehouse. Using a transformation framework, I wrote and documented SQL steps that turned the noisy event table into a tidy channel table, mapping each install event to the last‑click marketing source.
- The transformation logic was version‑controlled and tested with a suite of checks that flagged missing or duplicate records. I scheduled the pipeline to run each night, so the next morning the channel table was already refreshed.
- To keep the client in the loop, I built a simple Looker Studio dashboard that pulled the daily channel table and calculated acquisition cost per channel on the fly. The dashboard showed trends, spent vs. spend‑efficiency, and highlighted any channel where the cost per acquisition deviated from the norm.
- Throughout the project I kept the documentation plain and visual, using flow diagrams and comment‑rich SQL so the non‑technical marketing team could follow the logic.

**Impact**
- With daily, reliable numbers in hand, Lumio’s marketing manager shifted 18% of the ad budget from high‑cost display ads to a lower‑cost social platform that delivered comparable sign‑up volumes.
- This re‑allocation reduced the overall cost per acquisition by 11%, delivering a noticeable lift in the app’s profitability.
- The automated pipeline saved the team roughly eight hours of manual work each week and gave them confidence to experiment with new channels, knowing the financial impact would be measured instantly.
- Finally, the clear documentation meant the client could hand over the system to a new analyst without a steep learning curve, ensuring the solution would continue to add value long after my engagement ended.
