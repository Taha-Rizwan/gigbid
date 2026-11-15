# ADR 0006: Open models on Groq by default, Claude Haiku as the paid profile and judge

- Status: accepted
- Plan reference: D12, D13, Q4, Q5 in `PLAN.md` §0

## Context

The deployed link must work on open-weight models. The laptop has a 6 GB GPU and too little disk
for Ollama models, and free hosts have no GPU. The brief asks for small models on cheap, frequent
nodes and the strongest affordable model on the Writer and Critic, every node's model set in
config, and at least two open configurations compared by measurement. An LLM judge must come from
a different family than the writer and must be calibrated.

## Decision

Profiles in `agent/config.yaml` `models.profiles`, resolved per node through `models.nodes`
(`agent/settings.py` `model_spec()`, `agent/llm.py` `get_model()`):

| Profile | small | strong | judge |
|---|---|---|---|
| `open` (default, deployed) | Groq `openai/gpt-oss-20b` | Groq `openai/gpt-oss-120b` | `claude-haiku-5-5` (eval only) |
| `open_alt` (comparison) | Groq `qwen/qwen3.8-27b` | same | Groq `openai/gpt-oss-120b` |
| `open_local` | Ollama `qwen3:4b` | Ollama `qwen3:8b` | `claude-haiku-5-5` |
| `paid` (optional) | `claude-haiku-5-5`, effort low | `claude-haiku-5-5`, effort medium | `claude-haiku-5-5` |

- Fallbacks on errors: small → `fallback_small`, strong → `fallback_strong`. In `open` the two
  gpt-oss models back each other up, because they are separate Groq rate-limit buckets.
- Claude is called through the official `anthropic` SDK (`agent/llm.py` `AnthropicModel`) with
  structured output via `messages.parse`.
- Embeddings and the reranker are open models on CPU in every profile: fastembed ONNX
  `BAAI/bge-small-en-v1.5` (alternative `nomic-ai/nomic-embed-text-v1.5`) and
  `Xenova/ms-marco-MiniLM-L-6-v2`. This replaces the planned BGE-M3 and `bge-reranker-v2-m3`,
  for disk and CPU reasons.
- Per-model USD prices for cost accounting live in `models.prices`.

## Alternatives rejected

- **Local Ollama as the default.** No disk for the models, and no GPU in deployment. Kept as
  `open_local` for compose.
- **OpenRouter as a fallback provider.** Dropped in review (Q5). One provider is enough when two
  of its models back each other up.
- **A paid model as default.** The brief says open first.
- **Judging with gpt-oss.** Same family as the writer, so it risks self-preference. Haiku is a
  different family and cheap.

## Consequences

- The deployed system costs nothing but is bound by Groq free-tier limits. Eval runners throttle
  (`evals/runners/common.py`, `EVAL_TPM_BUDGET`, `EVAL_MODEL_CONCURRENCY`) and write partial
  results when a daily quota runs out (`DailyLimitReached`). This forced smaller samples (see the
  report's threats to validity).
- The judge costs real money. Eval spend is capped by `EVAL_ANTHROPIC_CAP_USD`.
- Measured comparison of `open` vs `open_alt`:
  `{{RESULT: model_profiles.json → profiles.open vs profiles.open_alt: decisions.bid_skip.f1, proposals.judge_overall_mean, proposals.latency.p95_s, proposals.usage_per_proposal.cost_usd_mean}}`.
- The eval Makefile defaults to `EVAL_PROFILE=paid` (Claude Haiku on every tier).
  `EVAL_PROFILE=open` runs the same evals on Groq. The deployed app runs `open`. Every results file
  records its `model_profile`, so check it before comparing a measured number with the deployed
  configuration. {{STUDENT: why the evals ran on the profile they did}}
