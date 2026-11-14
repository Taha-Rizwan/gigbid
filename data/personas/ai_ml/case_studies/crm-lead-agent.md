---
evidence_id: ai_ml:case:crm-lead-agent
title: LLM lead-qualification agent inside a real-estate CRM
project: Keystone Realty - LLM lead-qualification agent inside a real-estate CRM
client_industry: real estate
date: 2024-04
skills:
- LLM agents
- workflow automation
- CRM integration
outcome: lead qualification time from 2 days to 3 hours; agents reclaimed ~6 hours
  a week each
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 348153160
---

# LLM lead-qualification agent inside a real-estate CRM

### The problem
Keystone Realty’s sales team was drowning in unstructured enquiries that arrived by email and web form. A typical prospect required two days of back‑and‑forth before an agent could confirm interest and schedule a viewing. The manual process meant that agents spent most of their week chasing incomplete information, and the latency caused many leads to go cold. The client needed a way to accelerate qualification while retaining a human checkpoint before any outbound communication.

### What I did
I designed a conversational workflow that sits between the inbound channel and the CRM. The system first parses each new enquiry to extract the known fields – property type, budget, and contact details. It then identifies the missing pieces and automatically drafts a short SMS asking the prospect for that information. Before the message is sent, the workflow pauses at a review node where a sales rep can approve, edit or reject the outbound text. Once the prospect replies, the response is parsed, the lead record is updated and, when all required data are present, the lead is marked as qualified and written back into the CRM.

To implement the logic I used Python for data handling and orchestration, and I built the step‑by‑step graph with a framework that lets me define conditional branches and human‑in‑the‑loop approvals. The system stores each interaction in PostgreSQL so that the conversation history is searchable and audit‑able. For the SMS channel I integrated Twilio’s messaging service, enabling reliable two‑way communication with prospects.

Throughout the project I focused on evaluation: I logged the time taken at each stage, measured the drop‑off rate after each question, and fine‑tuned the prompting strategy to keep replies concise. I also created a monitoring dashboard that alerts the team if a lead stalls for more than an hour, ensuring that no opportunity is lost.

### Results
The autonomous agent reduced the average lead‑qualification time from 48 hours to just three hours, a 93 % improvement. Each sales representative reclaimed roughly six hours per week that were previously spent on data‑gathering, allowing them to focus on high‑value activities such as negotiations and client relationships. The client reported a 15 % increase in conversion rate within the first month, attributing the uplift to the faster response times and higher data quality. The solution has been fully integrated into Keystone’s existing CRM and is now part of their standard sales pipeline.
