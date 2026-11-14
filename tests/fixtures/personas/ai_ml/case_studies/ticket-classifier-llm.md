---
evidence_id: ai_ml:case:ticket-classifier-llm
title: Support ticket routing with a fine-tuned small language model
project: ticket-classifier-llm
client_industry: saas
date: '2025-06'
skills: ["Transformers", "LoRA", "Python"]
outcome: delivered
synthetic: true
---
Fine-tuned a 1B-parameter model with LoRA on 40k historical tickets to route them to 14 queues. Macro-F1 0.87 vs 0.71 for the old rules; deployed behind a queue worker with nightly retraining.
