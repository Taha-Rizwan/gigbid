---
evidence_id: fullstack:case:inventory-excel-macro
title: Excel macro for stock counts
project: Excel macro for stock counts
client_industry: retail
date: 2022-01
skills:
- spreadsheet automation
outcome: weekly stock count from 3 hours to 20 minutes
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1697717905
---

# Excel macro for stock counts

When a small retail shop reached out in January 2022, they needed a faster way to tally their weekly stock. I was in the middle of a SaaS migration project, but it was a quick favor—a one‑off side job that didn’t fit my usual focus on React apps or multi‑tenant back ends. The store kept their inventory in a simple spreadsheet, and the manual counting routine took about three hours every Friday. I asked to see the file and quickly spotted a pattern: the same set of formulas and copy‑pastes were being used over and over.

I wrote a short VBA macro that pulled the raw numbers, applied the necessary calculations, and output a clean summary sheet. The macro also highlighted any discrepancies, so the staff could spot errors before finalizing the report. I kept the code straightforward—just a few loops and a couple of built‑in Excel functions—so the shop’s part‑time manager could run it with a single button click.

After the first run, the time spent dropped from roughly three hours to twenty minutes. The team was thrilled to have the extra time to focus on customer service rather than data wrangling. I documented the steps in a one‑page guide, and the client now runs the macro every Friday without any technical help.

Even though spreadsheet automation isn’t my primary niche, the project reminded me how a little bit of code can make a big difference in everyday business tasks. It was a satisfying side gig, and the client’s gratitude was the best payoff.
