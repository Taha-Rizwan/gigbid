---
evidence_id: ai_ml:case:prompt-audit-copy-tool
title: Prompt and output audit for a marketing copy generator
project: Prompt and output audit for a marketing copy generator
client_industry: SaaS
date: 2024-02
skills:
- prompt engineering
- LLM evaluation
outcome: off-brand outputs down from 1 in 5 to 1 in 25
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1062809527
---

# Prompt and output audit for a marketing copy generator

**Client background**

The client was a mid‑size SaaS company that offered a self‑service platform for email campaigns. Their marketing copy generator, built on a large language model, was intended to produce taglines and short product descriptions. However, the team observed that roughly one in five outputs drifted away from the brand voice – using informal phrasing, incorrect terminology or even unrelated themes. This forced the copy team to spend extra time editing, delaying campaign launches.

**What I did**

I began by collecting a sample of 200 generated snippets and categorising the deviations. Using a small‑scale evaluation framework in Python, I measured the frequency of off‑brand tokens and identified the prompts that produced the highest error rate. I then rewrote those prompts, introducing explicit style cues and a short brand guideline snippet. To verify the changes I employed the open‑source tool *PromptTest* to run A/B tests on the original and revised prompts, scoring each output against a simple lexical similarity metric.

**Result**

After three iterations the off‑brand rate fell from 1 in 5 to 1 in 25 – a reduction of 80 %. The copy team reported that they now needed to edit less than five per cent of the generated text, cutting their review time by about two hours per week. The client also noted a measurable uplift in click‑through rates on campaigns that used the refined generator, attributing the improvement to the more consistent brand tone.

**Takeaway**

A focused prompt audit, combined with systematic evaluation, can dramatically improve the reliability of LLM‑driven content tools without requiring a full model retrain. The modest effort of refining prompts paid back quickly in both productivity and marketing performance.
