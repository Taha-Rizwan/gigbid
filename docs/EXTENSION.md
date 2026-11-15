# Signature extension X2: proposal A/B experiments

Decision record: [ADR 0012](adr/0012-extension-x2-ab-tests.md). The task: run two proposal
strategies as an A/B test in GigSim, with a significance test on reply rate.

## 1. Question and hypothesis

Does the opening strategy of a proposal change the simulated reply rate when everything else (job,
evidence, price, length limits, verifier, Critic, Compliance) stays the same?

The two strategies are defined in `agent/config.yaml` under `proposal_strategies`, so the text
under test is configuration, not code:

| Arm | Key | Instruction given to the Writer |
|---|---|---|
| A | `evidence_first` (the `default_strategy`) | "Open by naming the client's problem in one sentence, then lead with the single most similar past project and its measured result." |
| B | `question_first` | "Open with one sharp, specific question about the client's problem that shows you understood the post, then show the most relevant evidence." |

Hypothesis, stated before running: `evidence_first` gets a higher GigSim reply rate than
`question_first`. GigSim's client model rewards concrete evidence (`specificity`), and its
personalisation rating rewards a letter about this client's problem. `question_first` spends the
opening on a question and may score lower on specificity. A null result is a real result here.

## 2. Design

- **Mechanism.** `agent/nodes/writer.py` `strategy_rule()` reads `profile["strategy"]`
  (falling back to `default_strategy`) and appends the strategy's text to the Writer's system
  prompt rules. Nothing else in the graph knows about strategies.
- **Paired.** `evals/runners/ab_experiment.py` drafts every job twice with the full bid graph, once
  per strategy, stopping at the approval interrupt. Nothing is submitted. Job difficulty cancels
  out because each job is its own control.
- **Job set.** Dev jobs spread across the three personas (`--n`, default 40). The run is recorded
  in `evals/results/ab_experiment.json`: `n_jobs_attempted` and `n_paired`.
- **Outcome.** Each draft is scored by GigSim's stateless client model (`POST /admin/score`), which
  is deterministic for the same input (ADR 0009). Reply = outcome in {replied, interview, hired}.
  The continuous `p_reply` is recorded as a secondary outcome.
- **Test.** The primary test is McNemar's exact test on the discordant pairs (A replied and B did
  not, or the reverse). A two-proportion z-test is reported for reference. Both are two-sided at
  α = 0.05.
- **Fairness checks.** Draft length per arm is recorded per row (`rows[].words`). If one arm runs
  much longer, length rather than the opening could explain a reply-rate gap.
- **Model profile.** Recorded in `model_profile`. The runner's default is `paid` (Claude Haiku),
  and the profile is the same for both arms.

```bash
make eval-gigsim                                   # eval GigSim on :8091 (or start one on :8092)
python -m evals.runners.ab_experiment --gigsim http://localhost:8092 --n 40 --profile paid
```

## 3. Results

All numbers come from `evals/results/ab_experiment.json`.

| | A: `evidence_first` | B: `question_first` |
|---|---|---|
| GigSim reply rate | `{{RESULT: ab_experiment.json → reply_rate.evidence_first}}` | `{{RESULT: ab_experiment.json → reply_rate.question_first}}` |
| Mean `p_reply` | `{{RESULT: ab_experiment.json → mean_p_reply.evidence_first}}` | `{{RESULT: ab_experiment.json → mean_p_reply.question_first}}` |
| Mean words | `{{RESULT: ab_experiment.json → mean of rows[].words where strategy = evidence_first}}` | `{{RESULT: ab_experiment.json → mean of rows[].words where strategy = question_first}}` |

- Paired jobs: `{{RESULT: ab_experiment.json → n_paired}}` of
  `{{RESULT: ab_experiment.json → n_jobs_attempted}}` attempted.
- Discordant pairs (A only / B only): `{{RESULT: ab_experiment.json → discordant.evidence_first_only}}` /
  `{{RESULT: ab_experiment.json → discordant.question_first_only}}`.
- McNemar exact p-value: `{{RESULT: ab_experiment.json → mcnemar_exact_p}}`.
- Two-proportion z-test p-value (reference only, ignores pairing):
  `{{RESULT: ab_experiment.json → two_proportion_z_p}}`.
- Cost of the experiment: `{{RESULT: ab_experiment.json → cost_usd}}` USD.
- Which GigSim score components moved (per-row `quality` and components):
  `{{RESULT: ab_experiment.json → rows, mean quality per strategy}}`.

Conclusion: `{{STUDENT: one paragraph — which arm won, whether it is significant, and the component that explains it}}`.

## 4. How to read this result

- **It measures our simulator.** GigSim's client model is code we wrote (ADR 0009). An arm that
  matches its rules (specific evidence, no generic opener) wins by construction. The test shows
  which strategy our simulated clients prefer, and through which component. It is not evidence
  about real Upwork clients.
- **Power is limited.** Free-tier limits keep the number of jobs small. With few discordant pairs,
  McNemar can only detect large differences, so a non-significant result means "no large effect
  found", not "no effect".
- **The question arm is not rewarded directly.** The client hidden preference `prefers_questions`
  only changes the wording of client replies (`gigsim/client_model.py` `client_reply_text`), not
  `p_reply`. If B wins, the cause is in the scored components, not in that preference.

## 5. What would ship

If one arm wins significantly with no loss in grounding, it becomes `default_strategy` in
`agent/config.yaml`. That is a one-line config change. If not, `evidence_first` stays and the
experiment is reported as a null result.

The outcome memory (`agent/memory/promotion_rules.py` `record_outcome`, `style` argument) is where
a per-category winning style could later be learned from real outcomes.
