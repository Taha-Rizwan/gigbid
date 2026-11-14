---
evidence_id: fullstack:case:figma-to-tailwind-landing
title: Landing page from a Figma design
project: Landing page from a Figma design
client_industry: SaaS
date: 2021-09
skills:
- front-end development
- responsive design
outcome: pixel-accurate page delivered in 3 days
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1490836497
---

# Landing page from a Figma design

When the SaaS startup reached out in September 2021, they had a clean Figma file and a tight deadline. They needed a landing page that looked exactly like the design, loaded fast, and adjusted gracefully from mobile to desktop. I jumped in as a solo developer, pulling the assets from Figma and setting up a Next.js project to keep the build process lightweight.

First, I translated the layout into a series of reusable React components. Using CSS modules, I could mirror the spacing, typography, and colors without adding extra layers of abstraction. I paid close attention to the design system, matching the button states and form inputs pixel by pixel. The biggest challenge was the hero section, which required a background image that stayed crisp on high‑resolution screens while staying under the performance budget. I used the built‑in Image component to serve the right size automatically.

Responsive behavior was a matter of writing media queries that followed the breakpoints defined in the design. I tested on a range of devices, from an iPhone SE to a 27‑inch monitor, and tweaked the flex layout until everything stacked correctly. The checkout call‑to‑action stayed visible and clickable at every width, which was crucial for the client’s conversion goals.

Within three days, the page was deployed to Vercel and the client could preview it instantly. They were thrilled to see their vision reproduced without any visual compromises. The final deliverable was a production‑ready landing page that required no further tweaks, letting the startup focus on their product launch rather than front‑end bugs.
