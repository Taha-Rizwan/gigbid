---
evidence_id: ai_ml:case:review-topic-mining
title: Voice-of-customer topic mining on product reviews
project: Brightcart - Voice-of-customer topic mining on product reviews
client_industry: e-commerce
date: 2023-09
skills:
- topic modelling
- embeddings
- clustering
- data apps
outcome: surfaced 3 recurring product defects; returns on those SKUs down 6%
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1780532909
---

# Voice-of-customer topic mining on product reviews

I was approached by Brightcart in September 2023 to help them make sense of the growing volume of customer feedback on their online store. Their merchandising team was overwhelmed by hundreds of thousands of free‑form reviews and needed a way to surface the most important pain points without manually reading each comment. My role was to design a solution that could automatically group reviews by their underlying meaning and present the results in a format that business users could explore quickly.

The first step was to turn the raw text into a numerical representation that captured semantic similarity. I used a transformer‑based model to embed each review into a dense vector space, allowing the algorithm to recognise that phrases like “the strap broke” and “the handle snapped” are describing the same type of issue even though the wording differs. Once the reviews were represented as vectors, I applied a dimensionality‑reduction technique to make the data tractable for clustering while preserving the relationships between points.

With the reduced vectors I employed a density‑based clustering method that automatically discovers groups of reviews without needing to pre‑define the number of topics. This approach yielded 210 000 reviews organised into coherent clusters that reflected distinct product concerns rather than simple keyword matches. To make the insights actionable, I wrapped the clustering results in a lightweight web interface built with a Python framework, enabling the merchandising team to filter, search and visualise each theme on demand. The app also provided a concise summary of the most prevalent issues for each product line.

The analysis revealed three recurring product defects that were responsible for a disproportionate share of negative feedback. By highlighting these specific problems, Brightcart could prioritise corrective actions with their suppliers and adjust their quality‑control processes. Within a month of implementing the recommendations, the return rate for the affected SKUs fell by six percent, delivering a measurable improvement to both customer satisfaction and the bottom line.

Beyond the immediate impact, the solution proved scalable and reusable for future review streams. The team now has a self‑service tool that continuously ingests new feedback, updates the clusters, and surfaces emerging issues in near real‑time. This ongoing capability helps Brightcart stay ahead of potential problems and maintain a high standard of product quality.

Overall, the project combined modern semantic embedding techniques with robust clustering and a simple, user‑friendly interface to turn unstructured text into clear, business‑relevant insights. The result was a data‑driven improvement in product reliability and a tangible reduction in returns, all delivered within the tight timeline set by the client.
