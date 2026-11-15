# ADR 0001: Build the GigSim marketplace simulator ourselves

- Status: accepted
- Plan reference: D9, D10, Q8 in `PLAN.md`

## Context

The brief says GigSim is "provided" and "do not modify", but the starter kit contained no `gigsim/`
folder, and no simulator or instructor policy pack was released. Every graded metric (reply rate,
hire rate, the crash and exactly-once test, the change request) needs a marketplace with jobs,
clients with hidden preferences, Connects, idempotent proposals, messages, rate limits and errors.

## Decision

Write GigSim as a standalone FastAPI service with its own SQLite database (`gigsim/app.py`,
`gigsim/service.py`, `gigsim/db.py`), specified in `docs/specs/GIGSIM_SPEC.md`.

- GigBid talks to it only over HTTP, through the Marketplace MCP server and
  `mcp_servers/marketplace/adapters/gigsim.py`. GigBid code never imports `gigsim`.
- Hidden labels (`is_scam`, `has_injection`, client `hidden` preferences) are only exposed under
  `/admin`, which is protected by `X-Admin-Token`.
- Realism: a token bucket per account (`GIGSIM_RATE_PER_MIN`, 429 with `Retry-After`), seeded 5xx
  chaos (`GIGSIM_ERROR_RATE`), a simulated clock, reposts, scams and planted injections.
- Rules (Connects formula, required disclosure, the v2 change) live in `gigsim/policy.yaml`.
- Freeze: `scripts/ci_guards.py` `check_gigsim_frozen()` fails CI if anything under `gigsim/`
  changes after the tag `gigsim-v1.0`, once that tag exists.

## Alternatives rejected

- **Share the app's Postgres.** That couples the "external platform" to our app, and a crash test
  could corrupt both.
- **Mock the marketplace inside the agent code.** The port/adapter design (R1) would then prove
  nothing, and degraded mode could not be tested by killing a process.
- **Wait for an instructor simulator.** It was never published, and the deadline did not move.

## Consequences

- Evaluations are reproducible: `POST /admin/reset` re-seeds, and client verdicts are cached.
- The simulator is ours, so reply-rate results measure how well GigBid matches **our** client
  model, not real clients. The report says this in its threats to validity.
- We wrote both the exam and the answers. `scripts/ci_guards.py` and the no-import rule are what
  keep the two apart. The examiner should treat GigSim results as internal evidence.
