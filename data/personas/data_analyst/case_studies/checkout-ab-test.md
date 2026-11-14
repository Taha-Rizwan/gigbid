---
evidence_id: data_analyst:case:checkout-ab-test
title: Checkout redesign experiment analysis
project: Brightcart - Checkout redesign experiment analysis
client_industry: e-commerce
date: 2020-07
skills:
- A/B testing
- statistics
- experiment design
outcome: +3.1% conversion confirmed; a false-positive launch avoided
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 774264420
---

# Checkout redesign experiment analysis

### The problem
Brightcart was planning a major checkout redesign and wanted to run an A/B test to see if the new flow would increase sales. The stakes were high – a launch based on a misleading result could have hurt revenue and customer trust. Early on I noticed that the raw conversion numbers were noisy because shopper behaviour varied widely across the week, and the initial test plan didn’t account for this variability. There was also a risk of "peeking" – checking the results before the experiment had run its full course – which could have led us to ship a variant that actually performed worse.

### What I did
I built a custom analysis routine that first pulled the relevant transaction data from our warehouse and then applied a variance‑reduction technique. By using each user’s activity in the weeks before the experiment as a covariate, I could adjust the conversion metric and cut the noise dramatically, meaning we needed far fewer weeks of data to reach a reliable conclusion. I also wrote a monitoring script that flagged any premature looks at the data, catching a peeking problem that would have otherwise prompted us to roll out a losing version. The core calculations were performed in Python, while the data extraction relied on SQL queries that joined behavioural logs with purchase records.

### Results
The adjusted analysis showed a clear uplift of **+3.1% conversion**, which was statistically confirmed after only three weeks of running. Because the variance‑reduction step trimmed the required sample size, we saved both time and the cost of keeping the test live longer than necessary. Most importantly, the peeking safeguard prevented a false‑positive launch, protecting Brightcart from deploying a change that would have reduced revenue. The final recommendation was to roll out the redesign, backed by solid evidence and a clear understanding of the underlying shopper dynamics.
