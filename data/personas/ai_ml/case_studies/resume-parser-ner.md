---
evidence_id: ai_ml:case:resume-parser-ner
title: CV parsing for an HR start-up
project: CV parsing for an HR start-up
client_industry: HR tech
date: 2022-09
skills:
- named entity recognition
- information extraction
outcome: field accuracy 91% on 500 CVs
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1089750040
---

# CV parsing for an HR start-up

### The problem
The start‑up approached me with a need to automatically extract structured data from a large influx of CVs. Their existing manual process was slow and error‑prone, leading to delays in shortlisting candidates. They required a system that could reliably pull out names, contact details, education, work experience and skill keywords from a diverse set of CV formats, and they needed a quantitative measure of accuracy before committing to a full rollout.

### What I did
I designed a lightweight pipeline centred on a fine‑tuned named entity recogniser built with spaCy. The model was trained on a curated corpus of 1,200 annotated CVs, focusing on the six target fields. After the NER step, I applied a set of deterministic rules to normalise dates, consolidate multi‑line entries and resolve ambiguous tokens. The entire workflow was wrapped in a simple Flask API, allowing the client to submit PDFs or DOCX files and receive a JSON payload with the extracted fields. I also wrote a small validation script that compared the output against a manually labelled validation set of 500 CVs, reporting per‑field precision, recall and F1‑score.

### Results
On the validation set the pipeline achieved an overall field accuracy of 91%, with the highest performance on contact details (96%) and the lowest on skill extraction (84%). Processing time averaged 2.3 seconds per CV on a modest cloud instance, comfortably meeting the client’s latency requirements. The start‑up integrated the API into their applicant tracking system, reducing manual data entry effort by approximately 70% and shortening the initial screening phase from days to hours. The client was satisfied with the transparent evaluation metrics and the ease of extending the rule set for future field additions.
