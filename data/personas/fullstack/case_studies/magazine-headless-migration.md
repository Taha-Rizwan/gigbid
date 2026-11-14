---
evidence_id: fullstack:case:magazine-headless-migration
title: Moving a magazine off WordPress to a headless stack
project: Northbound Magazine - Moving a magazine off WordPress to a headless stack
client_industry: media
date: 2023-08
skills:
- CMS migration
- web performance
- SEO
outcome: page load (LCP) 4.1s -> 1.6s; organic traffic up 19% in three months
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 613393714
---

# Moving a magazine off WordPress to a headless stack

I was brought in by Northbound Magazine to give their digital home a serious performance upgrade and protect their SEO equity during a full platform migration.

**Challenge**
- Their legacy WordPress install was slow, hard to scale, and caused editors to wrestle with clunky plugins.
- Over 4,000 published URLs needed to stay reachable so search rankings wouldn’t evaporate.
- The editorial team required a writing environment that felt like the classic WordPress editor they loved, without sacrificing the new speed gains.

**Approach**
- I set up a content hub that stores articles in a structured database and serves them via an API, then connected the front‑end to pull that data on demand. *Next.js* was used to generate static pages at build time and automatically refresh them in the background when content changes, so readers always get a fast, up‑to‑date experience.
- To keep the newsroom comfortable, I integrated a headless CMS that mimics the familiar drafting screen, letting writers publish without learning a new tool.
- A comprehensive redirect map was created for every legacy URL, ensuring search bots and visitors were seamlessly sent to the new locations.
- Hosting on a global edge platform gave us instant caching and instant roll‑outs, cutting server response times dramatically.

**Impact**
- Core Web Vitals improved dramatically: the largest contentful paint dropped from 4.1 seconds to 1.6 seconds, delivering a buttery‑smooth load for readers.
- Because all old URLs were correctly rerouted, the site retained its search authority and organic traffic climbed 19 % within the first three months.
- Editors reported a 30 % reduction in publishing friction, citing the familiar editing screen and instant preview as game‑changers.
- The client now runs a scalable, low‑maintenance stack that can handle traffic spikes during breaking news without a hiccup.

Overall, the project turned a sluggish, legacy‑bound site into a high‑performance, SEO‑friendly platform while keeping the editorial workflow intuitive and familiar.
