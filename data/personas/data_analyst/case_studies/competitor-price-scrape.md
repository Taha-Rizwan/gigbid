---
evidence_id: data_analyst:case:competitor-price-scrape
title: Weekly competitor price collection
project: Weekly competitor price collection
client_industry: retail
date: 2022-08
skills:
- web scraping
- scheduling
outcome: 1,500 prices collected every Monday
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 73406410
---

# Weekly competitor price collection

I was approached by a small independent retailer who wanted to keep an eye on their competitors' pricing without spending hours each week copying numbers by hand.

**Challenge**
- Collect prices from a handful of rival e‑commerce sites every Monday.
- Keep the process reliable despite occasional site layout changes.
- Deliver the data in a tidy spreadsheet that the client could open in Excel.

**Approach**
I wrote a modest Python script that used *requests* and *BeautifulSoup* to pull the price elements from each target page. The script ran on a low‑cost cloud VM and was triggered by a simple cron job at 02:00 GMT each Monday. After scraping, I normalised the values, added a timestamp, and saved the result as a CSV file in a shared folder the client could access. To guard against minor HTML tweaks, I added a handful of fallback selectors and a short log file that emailed me if the run failed.

**Impact**
- The pipeline consistently gathered about 1,500 price records every week, covering the client’s key product categories.
- Manual effort dropped from roughly eight hours of copy‑and‑paste to zero – the client now receives the ready‑to‑analyse file each Monday morning.
- With the data at hand, the retailer could spot price undercutting quickly and adjust promotions, contributing to a modest uplift in sales margin over the following quarter.

Overall, the project demonstrated how a small, well‑targeted automation can free up valuable time for a retail business and provide the data foundation needed for agile pricing decisions.
