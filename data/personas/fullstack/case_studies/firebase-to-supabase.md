---
evidence_id: fullstack:case:firebase-to-supabase
title: Migrating an app from Firebase to Supabase
project: Migrating an app from Firebase to Supabase
client_industry: education
date: 2024-05
skills:
- database migration
outcome: hosting bill down 45%, zero data loss
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 998072143
---

# Migrating an app from Firebase to Supabase

**Who they were**

The client was a small online tutoring startup that ran a single‑page app for students and teachers. Their backend lived on Firebase, which was convenient at first but the monthly usage fees kept climbing as they added more users and stored more lesson recordings.

**What was hurting**

By early 2024 the team was paying nearly $2,000 a month for hosting and database storage. The cost spike was unsustainable for a boot‑strapped business, and they were also nervous about vendor lock‑in. They needed a cheaper, open‑source alternative that could handle their real‑time data sync without a massive rewrite.

**How we fixed it**

I scoped a migration plan that kept the app online while moving data. First, I exported all Firestore collections to JSON, then imported them into Supabase using its built‑in import tool. I rewrote the client‑side auth calls to use Supabase’s JWT flow and swapped the realtime listeners for Supabase’s subscription API. The only new library I added was the Supabase JavaScript client, which fit neatly into the existing React codebase. I ran the migration in a staged fashion: a copy of the production database was created, data was synced, and the new endpoints were tested on a feature branch before the final cut‑over.

**What changed**

After the switch, the monthly hosting bill dropped from $2,000 to $1,100 – a 45% reduction – while performance stayed the same or improved. The client reported zero data loss; all user accounts, lesson schedules, and chat histories were present after the migration. The team now has full control over their backend costs and can scale without fearing surprise fees.

The project was completed in four weeks, and the client was thrilled to see the savings and the smooth transition, giving them more runway to focus on product features rather than infrastructure expenses.
