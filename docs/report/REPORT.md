# GigBid: R&D design review (AI-4016)

Generated 15 Nov 2026 13:23 by `scripts/build_report.py`. Every number below is read from `evals/results/`;
"pending" means the run had not finished when this was generated. Repository: https://github.com/Taha-Rizwan/gigbid

## 1. Problem and constraints

Freelancers lose hours scanning feeds, spend paid Connects on unwinnable jobs, send generic proposals and meet scams.
GigBid automates discovery, risk and fit assessment, pricing and grounded drafting; **the human approves every proposal,
message and Connects spend** (LangGraph `interrupt()` in `agent/graphs/bid_graph.py` `approval`). Never automated:
sending, spending, off-platform contact, claims without portfolio evidence. Declared budgets (`agent/config.yaml`
`budgets`): job analysis p95 25 s / USD 0.002; proposal p95 60 s / USD 0.01.

## 2. Architecture

Two hand-written LangGraph graphs (`docs/images/bid_graph.png`): the bid graph (intake, then Job Analyst, Risk Assessor
and Fit Matcher in parallel via `Send`, decide, pricing, writer, claim verifier, critic with at most two revisions,
compliance, dry-run, approval interrupt, idempotent submit) and the conversation graph. Agents reach everything through
MCP (`mcp_servers/portfolio`, `marketplace` with GigSim and live-Upwork adapters behind one port, `workspace`), with
per-agent tool allowlists (`agent/mcp_client.py`). State, execution trace (LangSmith + `audit_log`) and long-term memory
(LangGraph store, written only by `agent/memory/promotion_rules.py`) are separate. Postgres checkpointer gives durable
approvals; idempotency keys derived from (user, job, draft version, text) give exactly-once submission. Details:
`docs/ARCHITECTURE.md`, `docs/adr/`.

## 3. R&D question A: tool granularity

Setup: 40 hand-written tasks with known correct tool calls (`evals/datasets/tool_tasks.jsonl`), one ReAct agent (model profile `paid`), four tool sets over the same functions.

| Tool set | Tool-selection acc. | Argument acc. | Exact task success | Tokens / task |
|---|---|---|---|---|
| fine | 1.000 | 0.963 | 0.950 | 5625 |
| coarse | 0.950 | 0.871 | 0.850 | 3353 |
| mcp | 1.000 | 0.988 | 0.975 | 6563 |
| mcp_rewritten | 1.000 | 1.000 | 1.000 | 7316 |

Finding: coarse tools are cheapest in tokens but lose argument accuracy (the model must pack several intents into one call); our MCP tools match fine-grained accuracy, and rewriting descriptions closed the remaining argument errors at a token cost. Source: `evals/results/tool_granularity.json`.

## 4. R&D question B: retrieval variants and claim verification

Pending: `rag_variants.json` is still being produced by `evals/runners/rag_eval.py` (all 600 dev jobs x 9 variants).

## 5. R&D question C: single agent vs supervisor vs our graph

Pending: `multiagent.json` is still being produced by `evals/runners/multiagent_compare.py`.

## 6. Change request

GigSim policy v2 (our own change request; the instructor's 2 Nov update was not published): proposals must end with the AI-assistance disclosure sentence; +4 Connects when proposals_count > 20.
Lines changed in GigBid: {"code": 0, "config": 0, "prompts": 0}. Why: pricing_strategist reads the live policy via the get_policy MCP tool into state.profile.policy; agent/nodes/compliance.py and agent/nodes/writer.py apply policy.required_disclosure from config or the live policy; Connects cost comes from get_job (GigSim applies the v2 formula).
Verified on {"job_id": "job_002", "thread_id": "bid-u_reviewer-job_002-r0c3f", "model_profile": "paid", "proposal_ends_with_disclosure": true, "gigsim_submit_status": "submitted", "run_tokens": 29272, "run_cost_usd": 0.006033}. Caveat: Zero lines because the system was designed to read platform policy at runtime; a rule that is not expressible as a disclosure, a regex pattern or a Connects formula would need code in agent/nodes/compliance.py.

## 7. Signature extension: X2 proposal A/B experiments

Pending: `ab_experiment.json` run in progress.

## 8. Decisions, scams and failure analysis

Dev decision eval (`decisions.json`, status partial, n = 68):
bid/skip accuracy 0.926, bid recall 0.000
(tp 0, fn 5); constructed-scam precision
0.400, recall 1.000. External real fake-job ads (Kaggle K6,
Risk Assessor only): precision 0.977, recall 0.860, F1 0.915, n = 100.

**Main failure (negative result):** the graph is too conservative: it skipped every job the gold set marks as bid in this
sample. Causes found in traces: the Fit Matcher's graded coverage plus the 0.55 bid threshold, and price floors versus
low K1 budgets. Fix tried: graded full/partial coverage (prompt v2). Taxonomy of failed dev jobs: missed evidence,
wrong skip, mispriced, unsupported claim, generic opening, compliance miss, injection, tool error (rate limits were the
dominant tool error on the Groq free tier).

## 9. Safety and platform respect

Never: send without approval, spend Connects without approval, contact off-platform, claim unproven experience, scrape.
Enforced by interrupts, allowlists (no agent reading untrusted text holds a write tool), regex + LLM compliance, claim
verification, PII masking in logs. Injection test (`injection.json`):

| Mode | n | End-to-end attack success | Writer-forced attack success | Detected |
|---|---|---|---|---|
| defences_on | 19 | 0.0% | 0.0% | 100.0% |
| defences_off | 21 | 0.0% | 0.0% | 100.0% |

Attacks failed with and without defences on this model, so the experiment cannot show the defences' marginal value;
a weaker model would be needed to measure it. What still gets through: unusual phone formats in regex masking, novel
injections the classifier misses, and LangSmith traces are not masked.

## 10. Budgets and test results

Job analysis: p50 21.5 s, p95 35.1 s
(declared 25 s: over budget), USD 0.0017 per job (declared 0.002: within).
Judge calibration: awaiting_human_labels. Hidden test: GigSim accepts examiner jobs via `POST /admin/import`.

## Threats to validity

Synthetic personas and our own simulator (GigSim) decide outcomes; gold evidence labels are LLM-made (Claude Haiku,
a different family from the gpt-oss writer) with 30 items prepared for human checking; the Groq free tier forced the
bulk evaluation onto the paid profile (Claude Haiku) and smaller samples, recorded as `n` in every result file.
