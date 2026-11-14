---
evidence_id: ai_ml:case:shopify-faq-bot
title: FAQ chatbot for a small online store
project: FAQ chatbot for a small online store
client_industry: e-commerce
date: 2023-11
skills:
- embeddings
- chatbots
outcome: answered 60% of chat questions without staff
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 368182333
---

# FAQ chatbot for a small online store

I was approached in November 2023 by a boutique online retailer that struggled with a growing volume of routine questions about shipping, returns and product details. Their existing support channel was a simple email inbox, and the owner estimated that roughly half of the incoming messages were repetitive and could be automated. I scoped a modest solution that would sit on their website, answer common queries, and hand over only the more complex cases to a human agent.

My first step was to collect the client’s existing FAQ documents, product descriptions and policy pages. After cleaning the text, I generated sentence‑level embeddings using a pre‑trained language model and stored them in a small FAISS index. The index allowed fast similarity searches, so when a visitor typed a question the system could retrieve the most relevant answer in under a second.

The chat front‑end was built with a simple JavaScript widget that sent the user’s query to a Flask API I hosted on a modest cloud instance. The API performed the similarity lookup, applied a confidence threshold and returned the top answer if it exceeded the threshold; otherwise it responded with a polite hand‑off message directing the user to the support email. I added a tiny logging layer to capture unanswered questions, which the client could later review to expand the FAQ set.

During a four‑week pilot the chatbot handled roughly 60 % of incoming queries, cutting the owner’s email workload by half. The remaining 40 % of questions were flagged for human follow‑up, and the client used the logs to enrich the knowledge base, further improving coverage. The solution required only a few hundred dollars in cloud spend and demonstrated how a lightweight RAG‑style system can deliver tangible savings for a small e‑commerce operation.
