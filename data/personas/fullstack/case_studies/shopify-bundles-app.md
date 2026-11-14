---
evidence_id: fullstack:case:shopify-bundles-app
title: Product-bundle builder app for a Shopify store
project: Oak & Ember - Product-bundle builder app for a Shopify store
client_industry: e-commerce (home goods)
date: 2023-04
skills:
- Shopify app development
- e-commerce
- GraphQL
outcome: average order value up 14% in the first quarter
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1711421029
---

# Product-bundle builder app for a Shopify store

When Oak & Ember approached me in early 2023, they wanted a way for customers to mix and match home‑goods items into a single, beautifully packaged offering. The goal was to keep the experience seamless inside their existing storefront while giving the team a simple way to define which products could be combined and at what discount. I started by mapping out the shopper journey: a visitor clicks a “Create Your Bundle” button, selects from curated categories, and watches the total adjust instantly as each item is added or removed. This real‑time feedback turned the selection process into a mini‑shopping experience that felt both playful and purposeful.

To make the price react instantly, I set up a lightweight data layer that watches the cart state and recalculates the subtotal on every change. The logic respects the bundle rules the staff creates—minimum quantities, maximum spend, and exclusive product pairings—so the system never lets an invalid combination slip through. On the backend, I used a small relational store to keep the rule definitions tidy and fast to query, which meant the admin interface could pull the latest settings without a page reload.

The admin side lives right inside the Shopify dashboard. Staff members open an embedded screen where they can drag‑and‑drop products into rule groups, set discount percentages, and preview how a typical bundle would look. All changes are saved instantly, and the next time a shopper opens the builder they see the fresh configuration. This gave the merch team full control without needing a developer to push updates.

I leveraged a Shopify Remix app template to scaffold the front‑end and a GraphQL Admin API call to fetch product data efficiently. The result was a smooth, responsive UI that feels native to the store and a reliable admin panel that empowers non‑technical staff.

Since launching the bundle builder in April 2023, Oak & Ember has reported a 14% increase in average order value during the first quarter alone. Customers love the ability to curate their own gift sets, and the staff appreciates the low‑maintenance way to tweak bundles for seasonal promotions. The project not only boosted revenue but also deepened brand engagement, turning a simple checkout into an interactive experience.
