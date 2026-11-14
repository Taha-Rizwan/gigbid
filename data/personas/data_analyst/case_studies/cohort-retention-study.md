---
evidence_id: data_analyst:case:cohort-retention-study
title: Retention and onboarding drop-off study
project: Lumio Apps - Retention and onboarding drop-off study
client_industry: consumer apps
date: 2023-06
skills:
- cohort analysis
- survival analysis
- product analytics
outcome: found a day-3 drop-off; week-4 retention up 5 points after the onboarding
  change
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 615328279
---

# Retention and onboarding drop-off study

## The challenge
Lumio Apps runs a suite of consumer applications that rely on a steady stream of new users becoming regular customers. Their growth team noticed that, despite strong acquisition numbers, a sizable proportion of users never made it past the first few days. The client had no clear picture of when users were disengaging, and they were unsure whether the onboarding flow was the culprit.

## My approach
I started by pulling the raw sign‑up logs into a tidy data set and constructing weekly cohorts based on the date each user first opened the app. For each cohort I plotted curves of how many sign‑ups were still active each week after joining, which gave a visual map of churn over time. To understand the exact point where the biggest attrition occurred, I built a time‑to‑churn model that compared the original onboarding sequence with a variant that introduced a short tutorial after the third day.

Using a statistical package for survival analysis, I estimated the probability of a user remaining active at each day post‑sign‑up. The model revealed a clear dip on day three – users who had not yet completed the tutorial were twice as likely to disappear.

## The solution
Armed with this insight, I worked with the product team to roll out a streamlined onboarding version that presented the tutorial earlier, on day one, and added a gentle reminder on day three for those who had skipped it. The change was A/B‑tested over a six‑week period.

## The impact
After the new flow went live, the week‑four retention metric rose by five points compared with the baseline. The early‑stage drop‑off curve flattened noticeably, indicating that users were staying engaged longer. The client could now quantify the value of a smoother onboarding experience and plan further enhancements with confidence.

## What I delivered
- A clean, repeatable pipeline that ingests sign‑up data, builds weekly cohorts and produces churn curves.
- A survival‑analysis model that isolates the day‑three churn spike and measures the effect of onboarding variations.
- A concise report and interactive visualisations that translate the technical findings into actionable business language for non‑technical stakeholders.

The work not only solved Lumio’s immediate retention puzzle but also gave them a framework for ongoing user‑behaviour monitoring, turning raw data into a strategic asset.
