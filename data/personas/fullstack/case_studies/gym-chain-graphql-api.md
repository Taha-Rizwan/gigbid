---
evidence_id: fullstack:case:gym-chain-graphql-api
title: GraphQL API for a gym chain's member app
project: GraphQL API for a gym chain's member app
client_industry: fitness
date: 2023-10
skills:
- GraphQL
- API design
outcome: one API serving web and mobile for 22 gyms
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1494480119
---

# GraphQL API for a gym chain's member app

**Who they were**

The client runs a regional gym chain with 22 locations. Their existing system was a patchwork of legacy REST services, each gym maintaining its own database. The mobile app and website had to call multiple endpoints, handle inconsistent data formats, and often returned stale information. This caused frustration for members trying to book classes, check schedules, or update their profiles.

**What was hurting**

The biggest pain points were:
- Duplicate logic across the front‑ends, leading to bugs.
- Slow response times because the app had to stitch together several calls.
- Frequent outages when one gym’s service went down, affecting the whole chain.

**How we fixed it**

I designed a single GraphQL API that sits in front of all the existing services. By defining a clear schema, the front‑ends now request exactly the data they need in one round‑trip. I used Node with Apollo Server to orchestrate calls to the legacy endpoints and a Postgres store for shared reference data. Authentication was handled via JWT, keeping the implementation lightweight.

**What changed**

After launch, the mobile app and website saw a 45% reduction in average request time. Developers no longer write repetitive fetch code; they simply query the GraphQL endpoint. The unified API also provides a single point of monitoring, so when a gym’s backend fails, the API returns a graceful error instead of breaking the whole app. The client reports happier members and a smoother rollout of new features across all 22 gyms.

*The project wrapped up in October 2023, delivering a maintainable, performant API that scales with the chain’s growth.*
