---
evidence_id: fullstack:case:tallyhub-billing
title: Subscription billing and plan management for a B2B SaaS
project: Tallyhub - Subscription billing and plan management for a B2B SaaS
client_industry: SaaS
date: 2022-03
skills:
- payments integration
- SaaS billing
- full-stack development
outcome: failed-payment recovery up 22%; finance stopped reconciling by hand
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1338394797
---

# Subscription billing and plan management for a B2B SaaS

When Tallyhub approached me in early 2022 they were struggling with a clunky billing flow that forced their finance crew to chase every missed payment manually. Their customers could switch plans at any time, but the system only applied changes at the next billing cycle, causing revenue leakage and frustrated users. I started by mapping out the entire subscription lifecycle, focusing on the moments that actually mattered: a user decides to upgrade or downgrade, a payment attempt happens, and the outcome needs to be recorded without duplication.

The first big win was re‑architecting the plan change logic so that any upgrade or downgrade is charged pro‑rata mid‑cycle. Instead of waiting for the next invoice, the system calculates the remaining value of the current period and immediately creates a charge for the difference. This not only aligns with what customers expect—instant access to new features—but also smooths out revenue spikes for the business. I built a tiny service that listens for these events and writes the adjustments to the database in a single transaction, guaranteeing that the new entitlement and the corresponding charge are always in sync.

Next, I tackled the messy problem of payment retries. The payment processor can fire the same webhook multiple times when a transaction is in limbo, and without careful handling you end up double‑charging or double‑recording. I introduced an idempotent handler that checks a unique identifier for each payment event before persisting anything. If the event has already been processed, the handler simply acknowledges it and moves on. This approach made sure that every payment event was handled exactly once, even when the provider retried several times.

For the front‑end, I used a modern React‑based framework to give the product team a clean, responsive admin panel where they could see subscription status, upcoming invoices and a log of all payment attempts. The UI lets support agents manually adjust plans or apply coupons, and all changes flow through the same backend logic, so there’s never a shortcut that could break the accounting.

The results were immediate. Within the first month after launch, Tallyhub reported a 22% increase in recovered failed payments because the system automatically retried and captured payments that previously fell through the cracks. Finance stopped reconciling by hand, freeing up several hours each week for strategic work. The client praised the simplicity of the new workflow and the confidence that comes from knowing every charge is recorded only once, no matter how many times the gateway pings the webhook.
