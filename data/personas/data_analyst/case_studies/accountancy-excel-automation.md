---
evidence_id: data_analyst:case:accountancy-excel-automation
title: Automating monthly client packs for an accountancy firm
project: Hartley & Moss Accountants - Automating monthly client packs for an accountancy
  firm
client_industry: professional services
date: 2022-04
skills:
- spreadsheet automation
- reporting
outcome: 30 staff hours a month saved; errors in packs dropped to near zero
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1029593851
---

# Automating monthly client packs for an accountancy firm

## The challenge
Hartley & Moss Accountants provide a suite of monthly financial summaries to their clients. Each month a junior accountant had to open a series of Excel files, copy data from the raw ledger exports, run a handful of manual calculations and then paste the results into a client‑specific template. The process was time‑consuming, prone to copy‑and‑paste mistakes and often delayed the delivery of the packs. With a growing client roster the firm was looking for a way to free up staff time and improve reliability.

## My solution
I set up a single workbook that acts as a hub for all client data. The file contains a button that, when pressed, pulls the latest figures from each ledger export, reshapes the tables and writes the numbers into the appropriate client template. The heavy lifting is done by a small script that loops through the export files, aligns columns, calculates key performance indicators and updates the visual layout. One button refreshes every client's monthly figures from the ledger exports, so there is no need to open each file individually. I used Excel's built‑in data‑transformation engine to clean and merge the raw data, and a bit of VBA to automate the repetitive steps and to generate the final PDFs.

## The impact
The automation replaced a manual workflow that previously took roughly 30 hours of staff time each month. After deployment the firm now spends virtually no time on the data‑gathering stage and can focus on analysis and client communication. Errors in the packs, which used to appear regularly due to manual entry, have dropped to near zero. The junior accountants have been redeployed to higher‑value tasks such as client advisory, and the partners have reported a noticeable improvement in client satisfaction because the packs arrive on schedule and are consistently accurate.

## Why it matters
For a professional services firm, the ability to deliver reliable, timely information is a competitive advantage. By turning a repetitive, error‑prone chore into a single‑click operation, I helped Hartley & Moss free up capacity, reduce risk and present a more polished service to their clients. The solution is easy to maintain – a new ledger export simply drops into the designated folder and the next click incorporates it automatically. This approach demonstrates how a modest amount of data‑engineering can deliver outsized returns for small organisations.
