---
evidence_id: fullstack:case:price-tracker-extension
title: Browser extension that tracks price drops
project: Browser extension that tracks price drops
client_industry: consumer tools
date: 2022-12
skills:
- browser extensions
- scraping
outcome: 3,000 installs in the first month
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 220967282
---

# Browser extension that tracks price drops

I was approached by a small consumer‑tools startup that wanted a simple way for shoppers to catch price drops without constantly refreshing sites. They needed a browser add‑on that could run quietly in the background, check a handful of e‑commerce pages, and alert the user when a lower price appeared.

**Challenge**
- Detect price changes across different storefronts that each render prices in their own HTML structure.
- Keep the extension lightweight so it wouldn’t slow down the browser.
- Respect user privacy by avoiding any unnecessary data collection.

**Approach**
I started by sketching the core workflow: a background script that periodically fetches the product page, a content script that extracts the price using a small set of CSS selectors, and a popup that shows the latest price and change history. For the scraping part I used **Cheerio** to parse the HTML in the background script – it’s fast and doesn’t require a full DOM. I stored the last known price in the extension’s local storage, then compared it on each run. If the new price was lower, the extension triggered a native browser notification. To keep the install size small I limited the extension to a maximum of five tracked items per user and used incremental updates rather than full page reloads.

**Impact**
- The extension hit 3,000 installs within the first month, far exceeding the client’s initial target of 1,000.
- Users reported a 40% reduction in time spent manually checking prices.
- The client was able to launch a modest premium tier that offered unlimited tracking, generating a new recurring revenue stream.

Overall, the project demonstrated how a focused, well‑engineered tool can deliver real value without the overhead of a full‑blown SaaS platform.
