# ADR 0012: Signature extension X2, proposal A/B experiments

- Status: accepted
- Plan reference: D29 in `PLAN.md`

## Context

The brief asks for one signature extension (X1–X6). The time budget was 2.5 days, and the extension
needs a measured result that can carry the technical write-up.

## Decision

X2: two proposal strategies run as an A/B test in GigSim, with a significance test on reply rate.
The design is in `docs/EXTENSION.md`.

- The strategies (`evidence_first`, `question_first`) are text in `agent/config.yaml`
  `proposal_strategies`. `agent/nodes/writer.py` `strategy_rule()` injects the selected one.
- `evals/runners/ab_experiment.py` drafts each job with both strategies and scores each draft with
  GigSim's deterministic `/admin/score`. The paired binary outcomes are tested with McNemar's exact
  test.

## Alternatives rejected

- **X6 (two weeks on a real Upwork account).** Impossible in the timeframe, and outcomes are
  never graded in live mode.
- **X1 agency mode and X5 negotiation coach.** Each needs a large new sub-graph and UI.
- **X3 portfolio builder.** Good, but a second ingestion pipeline.
- **X4 client research.** Needs official company-data APIs.

## Consequences

- Cheap to run: no new UI, and it reuses the eval harness (`evals/runners/common.py`) and
  `/admin/score`.
- The result measures GigSim's client model (ADR 0009), not real clients. `docs/EXTENSION.md`
  says so.
- Results: `{{RESULT: ab_experiment.json → reply_rate.evidence_first}}` vs
  `{{RESULT: ab_experiment.json → reply_rate.question_first}}`, McNemar exact
  p = `{{RESULT: ab_experiment.json → mcnemar_exact_p}}`.
