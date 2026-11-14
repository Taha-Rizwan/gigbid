---
evidence_id: ai_ml:case:invoice-field-extraction
title: Invoice and bill-of-lading field extraction
project: Cargoline Freight - Invoice and bill-of-lading field extraction
client_industry: logistics
date: 2023-01
skills:
- document AI
- OCR
- information extraction
- data validation
outcome: 9,000 documents a month processed; manual keying down 80%
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1436047196
---

# Invoice and bill-of-lading field extraction

### The problem
Cargoline Freight receives a steady stream of freight documents – both scanned and native PDFs – that contain critical shipping details such as consignee, vessel name, cargo weight and customs codes. Historically the team relied on manual data entry, which was slow, error‑prone and costly. They needed a solution that could handle high volume, maintain data quality, and reduce the burden on their clerical staff.

### What I did
I began by analysing a representative sample of the files to understand layout variation and the quality of the optical character recognition (OCR) output. I then set up a pipeline that first converts each page to text using a high‑accuracy OCR engine. Python was used to orchestrate the flow, read the PDFs and manage the downstream steps. For the OCR step I employed a robust open‑source recogniser that can cope with low‑resolution scans and mixed fonts.

Once the raw text was available, I prompted a large language model to extract 18 predefined fields – everything from invoice number to freight charge – and to return the values in a structured format. The model’s output was immediately checked against a Pydantic schema that enforces type, range and pattern constraints. Any field that fell below the confidence threshold was flagged, and the entire document was placed in a human‑review queue for final verification. The validation step ensures that only high‑certainty items reach operators, dramatically reducing their workload.

To keep the system maintainable I wrapped the extraction logic in reusable functions and logged each stage for auditability. The pipeline runs on a modest virtual machine, scaling horizontally if the document volume spikes. I also implemented a simple monitoring dashboard that tracks processing counts, error rates and the proportion of documents routed to manual review.

### Results
Within the first month of deployment the solution was handling roughly 9,000 documents each month. Manual keying time fell by 80%, freeing the operations team to focus on exception handling rather than routine entry. Accuracy of the extracted fields consistently met the client’s quality threshold, and the human‑review queue stayed below 5% of total volume, confirming that the confidence‑based routing was effective. The client reported a measurable reduction in invoice processing turnaround time and a clear improvement in data reliability across their logistics workflow.
