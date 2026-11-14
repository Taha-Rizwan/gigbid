---
evidence_id: ai_ml:case:legal-rag-assistant
title: Contract search assistant for a law firm
project: legal-rag-assistant
client_industry: legal
date: '2025-03'
skills: ["RAG", "LangChain", "pgvector", "FastAPI"]
outcome: delivered
synthetic: true
---
A 40-lawyer firm needed answers from 6,000 scanned contracts. I built an OCR + chunking pipeline, embedded clauses into pgvector and served a FastAPI chat endpoint with citations to the source page. Answer accuracy on a 120-question test set went from 61% with keyword search to 89%. Lawyers now get cited answers in seconds.
