---
evidence_id: ai_ml:case:support-ticket-triage
title: Automatic support-ticket routing
project: Quillstack - Automatic support-ticket routing
client_industry: SaaS (helpdesk software)
date: 2022-06
skills:
- text classification
- model compression
- background processing
outcome: 72% of tickets routed automatically; first-response time down 40%
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1936405822
---

# Automatic support-ticket routing

I was approached by Quillstack, a SaaS provider of helpdesk software, to improve the efficiency of their support desk. Their agents were overwhelmed by a growing backlog of tickets, and they needed a solution that could triage requests without slowing down the live inbox.

**Challenge**
- The existing workflow required manual assignment of every ticket, leading to inconsistent handling and long waiting periods.
- The volume of incoming queries was rising by roughly 15 % month‑on‑month, making manual scaling untenable.
- Any solution had to integrate seamlessly with their existing queueing system and operate on modest CPU resources.

**Approach**
- I trained a small distilled language model on a labelled corpus of historical tickets, teaching it to recognise categories such as billing, technical issue, feature request and churn risk.
- Python was used to preprocess the text and orchestrate the training pipeline.
- The model was exported to a fast CPU runtime and deployed as a background worker that pulls tickets from a Redis‑backed queue, classifies them and updates the database.
- Celery workers continuously processed the queue so the inbox never blocked, and the predictions were stored alongside each ticket for downstream routing rules.
- Regular evaluation cycles measured precision and recall, allowing incremental fine‑tuning as new ticket types emerged.

**Impact**
- 72 % of tickets were routed automatically, freeing agents to focus on complex cases.
- First‑response time fell by 40 %, improving customer satisfaction scores.
- The system handled peak loads without additional hardware, thanks to the lightweight model and efficient CPU inference.
- Ongoing monitoring showed a stable F1‑score above 0.85, confirming the model’s reliability in production.

Overall, the project delivered a robust, scalable triage layer that turned a manual bottleneck into an automated, data‑driven workflow, directly contributing to faster service and higher client retention.
