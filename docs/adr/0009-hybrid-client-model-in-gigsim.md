# ADR 0009: A hybrid rule + LLM client model in GigSim

- Status: accepted
- Plan reference: D10 in `PLAN.md`

## Context

Reply and hire rate are the end metrics. Simulated clients must react to proposal quality, have
hidden preferences, and compare against competing bids. A/B tests (X2) and CI need the same
proposal to get the same verdict every time.

## Decision

`gigsim/client_model.py` scores each proposal from seven components:

- skill coverage of the client's hidden must-have skills;
- price fit against a hidden budget ceiling;
- generic-opening penalty, weighted double if the client dislikes generic proposals;
- length fit against the client's `max_words`;
- rule-based specificity;
- an LLM personalisation rating;
- the account's success score.

The weights are in `WEIGHTS`. The combined quality is ranked against competitor qualities sampled
from the K5-derived `competitors.json`, then
`p_reply = sigmoid(8 * (quality - 0.55)) * (0.4 + 0.6 * rank_pct) * responsiveness`. A seeded RNG
(seed, job, account, hash of the text) draws the outcome.

- The LLM call (Groq, `GIGSIM_LLM_MODEL`, default `openai/gpt-oss-20b` in `gigsim/config.py`) is
  cached in SQLite `llm_cache` by request hash (`gigsim/llm.py`). Without a key, or with
  `GIGSIM_LLM_DISABLED=1` (CI), it falls back to `personalisation_heuristic()`.
- `POST /admin/score` is stateless and deterministic. It is used to label past proposals and for
  fast reply-rate evals.

## Alternatives rejected

- **Pure LLM client.** Slow and costly, and it gives different answers on reruns, which ruins A/B
  tests.
- **Pure rule client.** Easy to game (keyword stuffing wins), and it does not reward personalisation.

## Consequences

- Reruns are deterministic, so paired comparisons between variants are meaningful.
- The model encodes our own beliefs about what clients like: specific evidence, no generic
  opener, a fair price. A strategy that matches those rules will "win" in GigSim whether or not
  real clients agree. Reply-rate gains may not transfer to Upwork. The report treats GigSim
  outcomes as internal evidence.
- Past-proposal outcome labels come from the same model, so V4 (outcome-aware retrieval) learns
  GigSim's taste.
