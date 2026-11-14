---
evidence_id: fullstack:case:lumen-design-system
title: Shared component library and accessibility pass
project: Lumen Health - Shared component library and accessibility pass
client_industry: healthcare
date: 2020-08
skills:
- design systems
- accessibility
- front-end architecture
outcome: WCAG 2.1 AA across the patient app; UI bugs down a third
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1216372908
---

# Shared component library and accessibility pass

### The problem
Our patient portal was a patchwork of interfaces built by four separate product squads. Each team maintained its own set of buttons, forms and tables, which led to inconsistent look‑and‑feel, duplicated code, and frequent accessibility oversights. The app regularly failed screen‑reader checks and keyboard navigation tests, and we were tracking a steady stream of UI bugs that slowed releases.

### What I did
I spearheaded the creation of a unified component library that all squads could consume. First, I audited every existing UI element and extracted the core patterns into reusable modules. I then rewrote these modules in a type‑safe language to catch errors early and to make future extensions straightforward. To ensure every piece worked for all users, I integrated an automated accessibility checker into our CI pipeline and ran manual tests with a screen‑reader tool. I also set up a visual documentation system so designers and developers could see usage examples and accessibility notes in one place. Throughout the process I coordinated with the four teams, gathering their specific needs and iterating on the components until they met both functional and compliance requirements.

### Results
By the time we rolled out the new library, the patient app passed WCAG 2.1 AA standards across the board. Every button, form and table was verified for screen‑reader compatibility and full keyboard operability. The standardized components eliminated duplicated code, which reduced UI‑related bugs by roughly 33 %. Teams reported faster development cycles because they no longer had to rebuild common elements, and the consistent UI boosted user confidence in the platform. Overall, the project delivered a more accessible, maintainable, and efficient product experience for both our internal teams and the patients using the app.
