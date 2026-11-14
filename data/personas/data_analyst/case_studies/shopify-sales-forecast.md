---
evidence_id: data_analyst:case:shopify-sales-forecast
title: Simple sales forecast for a Shopify store
project: Simple sales forecast for a Shopify store
client_industry: e-commerce
date: 2023-08
skills:
- forecasting
outcome: stock orders planned 8 weeks ahead
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1185561234
---

# Simple sales forecast for a Shopify store

I was approached by a small e‑commerce shop owner who wanted a clearer view of future demand so they could order stock more efficiently. They ran a Shopify store selling niche home accessories and relied on gut feeling and ad‑hoc spreadsheets to decide when to reorder. 

**Challenge**
- Limited historical sales data (only two years) and occasional promotional spikes.
- No existing forecasting process; the owner manually adjusted orders each month.
- Need for a solution that could be maintained without deep technical knowledge.

**Approach**
I started by exporting the order data from Shopify and cleaning it in a spreadsheet, then moved the tidy dataset into a modest SQLite database for reproducibility. Using a basic seasonal ARIMA model I captured the weekly pattern and the modest yearly trend. I added a simple rule‑based adjustment for known promotional periods, which the owner supplied. The model was wrapped in a short Python script that could be run with a single command each month. I documented the steps in plain language and included a one‑page guide on how to update the data and interpret the forecast chart. 

**Impact**
- The forecast provided a clear picture of expected sales for the next eight weeks, allowing the owner to place stock orders with confidence.
- Stock‑out incidents dropped by roughly 30 % in the first two months, while excess inventory was reduced by about 15 %.
- The owner now runs the script themselves, spending less than an hour each month on forecasting instead of the previous half‑day of guesswork.

Overall, the project gave the shop a reliable, low‑cost tool to align purchasing with demand, freeing up time for the owner to focus on product development and marketing.
