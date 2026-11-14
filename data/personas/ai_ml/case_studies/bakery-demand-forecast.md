---
evidence_id: ai_ml:case:bakery-demand-forecast
title: Daily demand forecast for a bakery chain
project: Daily demand forecast for a bakery chain
client_industry: food retail
date: 2022-01
skills:
- time series forecasting
outcome: waste down 12% across 9 shops
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 325489184
---

# Daily demand forecast for a bakery chain

### The problem
The bakery chain operates nine locations and produces a variety of fresh items each day. Production is based on historical sales, but seasonal spikes and local events often cause over‑baking, leading to waste. The client wanted a simple, accurate forecast that could be updated each morning and integrated into their existing ordering system, without a large overhaul of their IT stack.

### What I did
I collected two years of point‑of‑sale data, cleaned it for missing entries and outliers, and added calendar features such as day‑of‑week and public‑holiday flags. Using a modest ARIMA model tuned by grid search, I generated daily demand predictions for each product line. To keep the pipeline lightweight, I wrapped the model in a scheduled Python script that runs on the client’s on‑premise server and writes the forecasts to a CSV file that the ordering software reads. I also produced a short validation report showing mean absolute percentage error (MAPE) of 6.3% across the nine shops, which satisfied the client’s requirement for transparency.

### Results
After a three‑month pilot, the bakeries adjusted their daily bake‑lists according to the forecasts. Waste, measured as unsold baked goods at the end of each day, fell from an average of 15 kg per shop to 13.2 kg – a 12 % reduction overall. The client reported smoother staff schedules and a modest increase in profit margins due to lower disposal costs. The solution required only a single weekly maintenance check, fitting the client’s limited technical resources.
