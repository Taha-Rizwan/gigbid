---
evidence_id: fullstack:case:core-web-vitals-rescue
title: Performance rescue for a slow online store
project: Performance rescue for a slow online store
client_industry: e-commerce
date: 2021-11
skills:
- web performance
outcome: Lighthouse mobile score 38 -> 91
synthetic: true
generator:
  model: qwen/qwen3.8-27b
  prompt_version: persona_v1
  seed: 1225950226
---

# Performance rescue for a slow online store

Back in November 2021, I worked with an independent boutique owner who was losing sales because her site took forever to load. She had built her store on a standard platform but had added several third-party plugins over time. The result was a page that felt heavy and unresponsive, especially on mobile devices where most of her customers shopped.

**Challenge**

The primary issue was a sluggish initial load time. When I ran the diagnostics, the mobile performance score was sitting at a painful 38. The page was rendering large chunks of JavaScript that blocked the browser, and images were being loaded at full resolution regardless of screen size. Users were abandoning the cart simply because the checkout button didn't appear for several seconds.

**Approach**

I started by auditing the network waterfall to identify the biggest bottlenecks. I found that a single analytics script was injecting massive amounts of code on every page view. I removed that dependency and replaced it with a lighter, self-hosted alternative. Next, I focused on the image optimization pipeline. I configured the image server to serve WebP formats and scaled images down to their display size. This alone cut down the payload significantly.

To further reduce the time to interactive, I deferred non-critical JavaScript until after the main content had rendered. I also implemented straightforward HTTP caching headers for static assets, ensuring that returning visitors didn't have to re-download the same files. I kept the changes minimal and focused on high-impact fixes rather than a complete rewrite. The goal was to make the existing structure faster, not to change how the store looked or functioned.

**Impact**

The results were immediate. After deploying the changes, the Lighthouse mobile performance score jumped from 38 to 91. More importantly, the real-world metrics improved. The average time to interactive dropped by nearly four seconds on a mid-range Android phone. The client reported a noticeable uptick in completed checkouts within the first two weeks. She was able to run a holiday promotion without worrying about server timeouts or user frustration. It was a small project, but it made a big difference to her bottom line.
