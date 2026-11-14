---
evidence_id: fullstack:case:tenant-auth-service
title: Multi-tenant authentication and permissions service
project: Ledgerly - Multi-tenant authentication and permissions service
client_industry: fintech SaaS
date: 2024-02
skills:
- authentication
- authorisation
- multi-tenancy
- security
outcome: passed the SOC 2 Type I audit with no auth findings; enterprise SSO deals
  unblocked
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1286057913
---

# Multi-tenant authentication and permissions service

When Ledgerly approached me in early 2024, they needed a robust way to keep each customer’s financial data completely separate while still offering a seamless login experience. I started by redesigning the access model so that every user’s permissions were enforced directly in the database, meaning the isolation happened where the data lives, not just in the application code. This approach eliminated the risk of cross‑tenant leaks and made compliance checks much simpler.

To support the variety of identity solutions their corporate clients already used, I built a gateway that speaks the standard protocols for authentication and federation. By delegating the sign‑in flow to the customers’ own identity providers, we gave them the confidence that employees could log in with familiar credentials, and we avoided storing passwords ourselves. The gateway also translated the provider’s tokens into a consistent set of claims that our services could trust.

The core of the system runs on a type‑safe server framework that lets us define clear contracts for each endpoint, reducing runtime errors and speeding up development. For data security, I leveraged row‑level security policies in the database so that a query automatically filters rows based on the tenant identifier attached to the user’s session. This means that even a buggy query can’t accidentally pull another client’s records because the database itself enforces the wall.

Automated tests were crucial. I wrote a suite that simulates login flows from multiple identity providers and verifies that the resulting permissions match the expected tenant scopes. The tests run on every pull request, catching regressions before they reach production. This safety net gave Ledgerly’s security auditors confidence that the authentication layer behaved consistently under different scenarios.

When the SOC 2 Type I audit arrived, the auditors praised the architecture for its clear separation of data and the use of industry‑standard protocols. There were no findings related to authentication, and the clear audit trail from the database policies helped us close the review quickly. Shortly after, Ledgerly reported that the new SSO capability unblocked three enterprise deals that had previously been stalled because of security concerns. The project not only met the compliance goals but also opened new revenue streams for the client.
