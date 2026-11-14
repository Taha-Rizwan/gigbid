---
evidence_id: ai_ml:case:contract-qa-rag
title: Contract question-answering assistant with an evaluation harness
project: Briefwell - Contract question-answering assistant with an evaluation harness
client_industry: legal tech
date: 2023-05
skills:
- retrieval-augmented generation
- search relevance
- LLM evaluation
- API development
outcome: answer accuracy 61% -> 86% on the answer key; unsupported citations close
  to zero
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1900293303
---

# Contract question-answering assistant with an evaluation harness

## The challenge
Briefwell, a legal‑tech provider, struggled to offer a reliable self‑service tool for contract queries. Their existing prototype returned generic text and often cited passages that were not directly relevant, leading to low confidence among solicitors. The key performance indicator was answer accuracy against a vetted answer key of 120 questions, which lingered at just 61 %.

## My approach
I designed a retrieval‑augmented answering service that only delivers responses tied to specific contract clauses. The pipeline begins with a hybrid search that blends keyword matching with dense vector similarity, producing a short list of candidate passages. A second‑stage re‑ranking model then re‑orders this shortlist, prioritising the most contextually appropriate excerpts. I implemented the service using Python and exposed it via a lightweight web framework, enabling rapid iteration and easy integration with Briefwell’s front‑end.

Each answer is automatically graded against the lawyer‑written answer key. The evaluation harness records both the correctness of the answer and whether the citation points to the exact clause supporting it. This strict grading forced the system to learn to cite only when a clause could be unambiguously linked to the response, driving unsupported citations to near zero.

## Results
After three months of development and continuous testing with pytest, the assistant’s answer accuracy rose to 86 % on the same answer key. The citation quality improved dramatically; the system now flags any response that cannot be anchored to a clause, effectively eliminating unsupported references. Users reported a noticeable increase in trust, and Briefwell was able to market the tool as a “citation‑verified” solution.

## Impact
The project demonstrated that a disciplined evaluation loop, combined with a blended search strategy and a focused re‑ranking stage, can turn a brittle prototype into a production‑ready legal assistant. The modest engineering effort yielded a measurable uplift in both accuracy and reliability, positioning Briefwell ahead of competitors in the contract‑analysis space.
