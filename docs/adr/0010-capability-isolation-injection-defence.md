# ADR 0010: Capability isolation as the main prompt-injection defence

- Status: accepted
- Plan reference: D18, D27 in `PLAN.md`

## Context

Job posts and client messages are untrusted text, and some GigSim jobs contain planted
instructions ("ignore previous instructions", "include your WhatsApp", "start your proposal with").
Detectors can be evaded. What matters is what a successfully injected model can do.

## Decision

Layered defences, listed in the header of `agent/guardrails.py`, with the structural layers first:

1. **No LLM picks tools in production.** Graph nodes call MCP tools from code with fixed
   arguments. Injected text can change what a model writes, not which tool runs.
2. **Per-agent allowlists** (`agent/mcp_client.py` `ALLOWLIST`, enforced in `AgentTools.call()`).
   Agents that read raw job text (`intake`, `risk_assessor`, `fit_matcher`, `writer`, `critic`)
   hold only read tools. `compliance` holds none. Marketplace writes belong to `submitter` and
   `messenger`, which are used only in the `submit` and `send` nodes, after `interrupt()`.
3. **Human approval** of the exact text, with a dry-run preview, before any write.
4. **Output checks.** The Compliance Guard's config regexes (`policy.forbidden_patterns`) redact
   contact details, guarantees and off-platform payment asks, and block if they cannot be removed.
   GigSim rejects off-platform contact on submit as a last fence.
5. **Delimiting.** Untrusted text is wrapped in `<untrusted_job_post>` / `<untrusted_client_message>`
   tags (`wrap()`), and prompts say it is data. Datamarking (`datamark()`) exists but is off in
   production (`RunContext.datamark = False`). It is an experiment switch.
6. **Detection.** Regex heuristics (`INJECTION_PATTERNS`) plus Llama Prompt Guard 2 on Groq
   (`prompt_guard_score()`). A score of 0.5 or more adds an `injection` flag to the risk report.
   Scam regexes set score floors in `agent/nodes/risk_assessor.py`.

## Alternatives rejected

- **Detection only.** Classifiers can be evaded with paraphrase, other languages or encoding.
  The defence cannot rest on a classifier.
- **Microsoft Presidio for PII.** Pulls in spaCy models, which are heavy. Regex masking
  (`common/security.py`) was chosen, and its misses are reported.
- **Tool-calling agents (ReAct) in production.** They give the model the choice of tool, which is
  what injection attacks. Kept only as the R&D C baseline.

## Consequences

- A fully successful injection can at worst change draft wording, which a human then reads. It
  cannot send, submit or spend Connects.
- Known holes, stated in the report: the liaison's `draft_reply` reads `search_evidence` outside
  its allowlist (read-only); the `liaison` allowlist includes the Workspace writes
  `create_interview_hold` and `create_email_draft`, although the current graph does not call them;
  Prompt Guard and the regexes can be paraphrased around.
- Attack success rate with defences on and off:
  `{{RESULT: injection.json → results.defences_on.end_to_end_attack_success_rate}}` vs
  `{{RESULT: injection.json → results.defences_off.end_to_end_attack_success_rate}}`.
