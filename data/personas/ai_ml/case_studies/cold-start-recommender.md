---
evidence_id: ai_ml:case:cold-start-recommender
title: Cold-start recommendations for a reading app
project: Cold-start recommendations for a reading app
client_industry: media
date: 2023-03
skills:
- recommender systems
- matrix factorisation
outcome: day-1 click-through up 9%
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1429088167
---

# Cold-start recommendations for a reading app

### The client and the problem
The client was a mid‑size media company that had launched a new reading app in early 2023. Their catalogue contained thousands of articles, but they had no data on new users, so the recommendation engine could only show generic popular items. As a result, the day‑one click‑through rate (CTR) was low and user engagement dropped off after the first session.

### My approach
I proposed a lightweight cold‑start recommender based on matrix factorisation. Using the limited interaction data we had – article metadata, category tags and a small set of explicit user preferences collected at sign‑up – I built a latent factor model in Python with the *surprise* library. The model was trained on the existing user‑article matrix and then extended to infer embeddings for new users from their initial preference vectors. I wrapped the model in a simple Flask API so it could be called from the app’s backend with negligible latency.

### The outcome
The system went live in March 2023. Within the first week the day‑one CTR increased by 9 % compared with the previous generic list. Because the model relied only on sparse metadata, it required no extensive retraining and could be updated monthly as new articles were added. The client reported higher retention on the second day and was able to roll the approach out to other language editions with only minor adjustments.

### Reflections
The project demonstrated that a modest matrix‑factorisation approach can deliver measurable gains in a cold‑start scenario without the complexity of deep learning pipelines. It also highlighted the importance of aligning the recommendation logic with the client’s existing data collection practices, allowing a smooth hand‑over to their engineering team.
