---
evidence_id: fullstack:case:keystone-crm
title: Internal CRM replacing spreadsheets for an estate agency
project: Keystone Realty - Internal CRM replacing spreadsheets for an estate agency
client_industry: real estate
date: 2021-06
skills:
- CRM development
- background jobs
- back-end development
outcome: 35 agents off spreadsheets in 8 weeks; lead response time down 50%
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 681965527
---

# Internal CRM replacing spreadsheets for an estate agency

## The challenge
Keystone Realty was still juggling client information, property listings, and follow‑ups in a maze of spreadsheets. Agents spent hours copying data, updating statuses manually, and often missed timely outreach. Managers had no real‑time visibility into pipeline health, and stale leads sat untouched until someone finally noticed them. The whole process was error‑prone, slow, and made it hard to scale as the team grew.

## My approach
I designed a web‑based platform that replaced the spreadsheets with a single source of truth. The core idea was to let the system do the heavy lifting: nightly jobs that pull listings from major portals and nudge agents about stale leads, while role‑based views give each user only the data they need. Agents see their own lead list and quick actions, managers get aggregated performance charts, and admins control permissions and data imports.

I used **Python** to write the background workers that fetch new property data and calculate lead freshness. On the front end, **React** powered the interactive dashboards, making it easy for users to filter, sort, and act on leads without page reloads. The database stored everything in a relational schema, ensuring consistency and fast queries.

## What changed
Within eight weeks, all 35 agents had migrated off the spreadsheet system. The automated pulls kept listings up‑to‑date without manual entry, and the nudges cut the average lead response time by 50%. Managers now have live dashboards that show conversion rates, agent activity, and bottlenecks, enabling data‑driven coaching. The whole workflow became smoother, more reliable, and ready for future growth.

## Takeaway
A well‑crafted internal tool can turn a chaotic, manual process into a streamlined, measurable engine. By focusing on what the software should *do*—keep data fresh, prompt action, and show the right information to the right people—I delivered a solution that saved time, reduced errors, and boosted performance for Keystone Realty.
