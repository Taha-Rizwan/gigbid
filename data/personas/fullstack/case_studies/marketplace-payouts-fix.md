---
evidence_id: fullstack:case:marketplace-payouts-fix
title: Fixing split payouts on a two-sided marketplace
project: Fixing split payouts on a two-sided marketplace
client_industry: marketplaces
date: 2023-02
skills:
- payments integration
- debugging
outcome: payout errors from 4% to zero
synthetic: true
generator:
  model: qwen/qwen3.8-27b
  prompt_version: persona_v1
  seed: 1726915899
---

# Fixing split payouts on a two-sided marketplace

The client was a small, two-sided marketplace connecting local contractors with homeowners. They were growing fast, but their finance team was losing sleep. Every time a job was marked complete, the system attempted to split the payment between the platform’s fee and the contractor’s earnings. About four percent of those transactions were failing. The money would sit in a limbo state, and the contractors would call support, angry and confused. It was creating a lot of friction and trust issues.

I spent the first few days just reading the logs. The error messages were generic, but the pattern was clear. The issue wasn’t with the payment provider itself; it was with how our backend handled the status updates. The system was trying to process the split payout before the initial authorization had fully settled. In high-traffic moments, this race condition caused the transaction to timeout. The code was trying to be clever by optimizing for speed, but it broke the reliability of the core financial flow.

I rebuilt the payout logic. I introduced a simple, reliable lock mechanism using our existing database. Now, when a job is completed, the system marks the transaction as 'processing' and waits for a confirmation webhook. Only after that confirmation does it trigger the actual split payout. I named the key function `finalizedSplit` to make the intent clear. It wasn’t a flashy architecture change, but it forced the system to respect the order of operations.

We deployed the fix on a Tuesday. By Friday, the support tickets had stopped. The payout error rate dropped from 4% to zero. The client’s finance team could finally close their books without manual adjustments. The contractors stopped calling, which was the best sign I’ve ever seen. It was a small gig, but it solved a very painful problem. Sometimes the best engineering is just making sure things happen in the right order.
