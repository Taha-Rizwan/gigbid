---
evidence_id: ai_ml:case:call-intent-classifier
title: Intent classification for call-centre transcripts
project: Northwind Telecom - Intent classification for call-centre transcripts
client_industry: telecom
date: 2021-03
skills:
- NLP
- text classification
- active learning
outcome: macro-F1 0.87 across 14 intents; routing errors halved
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 522288282
---

# Intent classification for call-centre transcripts

I was part of the analytics team at Northwind Telecom when the call‑centre struggled with mis‑routed enquiries. The existing rule‑based router could not keep up with the growing variety of customer queries, leading to delays and dissatisfied clients.

**Challenge**
- Over 200 k calls per month, each needing to be assigned to one of 14 service categories.
- Manual tagging was costly and the long‑tail intents were poorly represented in the training data.
- The business required a solution that could be deployed quickly and integrated into the live routing pipeline.

**Approach**
- Collected 40 k call summaries that had already been annotated by senior agents; each summary was linked to a single intent.
- Applied active learning to surface the rare intents, presenting the most uncertain examples to annotators and expanding the labelled set by 12 %.
- Fine‑tuned a pretrained transformer model on the curated dataset, letting the model learn contextual cues that differentiate intents such as *billing dispute* and *service upgrade*.
- Used Python to orchestrate data preprocessing, model training and evaluation.
- Employed spaCy to normalise the transcript text, handling tokenisation, lemmatisation and entity masking before feeding it to the model.
- Implemented a confidence‑threshold gating mechanism: high‑confidence predictions were routed automatically, while borderline cases were sent to a human triage queue.
- Deployed the model as a micro‑service behind the existing routing engine, exposing a lightweight REST endpoint for real‑time inference.

**Impact**
- Macro‑F1 rose to 0.87 across all 14 intents, a substantial improvement over the previous rule‑based system which hovered around 0.60.
- The number of mis‑routed calls dropped by 50 %, cutting average handling time by roughly 1.2 minutes per call.
- The active‑learning loop continued to enrich the training set, reducing the need for large manual labelling bursts.
- The micro‑service architecture allowed the model to scale with call volume, handling peak loads without latency spikes.
- Business stakeholders reported a measurable uplift in customer satisfaction scores within the first quarter after rollout.

Overall, the project demonstrated how a targeted fine‑tuning effort, combined with strategic data augmentation, can transform a legacy routing workflow into an intelligent, data‑driven system.
