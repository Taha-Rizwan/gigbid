# ADR 0011: Verify claims against evidence before the Critic sees the draft

- Status: accepted
- Plan reference: D23 in `PLAN.md`

## Context

R5: no sentence may claim experience the portfolio does not support, and the unsupported-claim
rate is measured before and after verification (B3). A Critic that judges grounding from the
draft alone tends to accept fluent, specific-sounding claims.

## Decision

A `claim_verifier` node between `proposal_writer` and `critic` (`agent/graphs/bid_graph.py`),
implemented in `rag/verify.py` `verify_draft()`:

1. `split_claims()`: the `verifier` model splits the letter and answers into atomic claims
   (prompt `agent/prompts/claim_splitter.md`). Inline citations `[persona:type:slug]` are attached.
2. `label_claims()`: each claim is labelled `supported`, `partly_supported` or `unsupported`
   against the evidence the Writer used (`agent/prompts/claim_verifier.md`). A non-unsupported
   label must cite an evidence id that exists in the pool, or it is downgraded to unsupported.
3. If any claim is unsupported or partly supported, `agent/prompts/claim_rewriter.md` removes or
   rewrites them, and the result is split and labelled again.
4. The node records `before`, `after` and `first_before` in `state["verification"]`. The Critic
   fails any draft with `after > 0`, and the Compliance Guard blocks a draft whose claims are
   still unsupported.

## Alternatives rejected

- **Critic-only grounding.** That is the failure mode described above.
- **An NLI model (DeBERTa-MNLI) on CPU.** Cheaper per claim, but it handles paraphrase and partial
  support across several evidence items poorly, and it would add PyTorch to the image. Left as an
  optional comparison.
- **Verifying after Compliance.** Compliance would then redact text that the verifier later rewrites.

## Consequences

- Viva Q3 ("delete the evidence and regenerate") has a defined behaviour: with the evidence gone,
  the claim has nothing to cite, so it is labelled unsupported and rewritten or removed. If it
  survives, the Critic sends the draft back and Compliance blocks it.
- Two small-model calls per draft revision (split, label), or five when a rewrite is needed
  (split, label, rewrite, split, label), counted in the `verifier` node's usage.
- Measured effect: `{{RESULT: proposals.json → results.<best variant>.unsupported_before_mean}}` →
  `{{RESULT: proposals.json → results.<best variant>.unsupported_after_mean}}` unsupported claims
  per proposal.
